#!/usr/bin/env python3
"""
MCP Server for Document Search
Exposes document vector search capabilities to Claude CLI via MCP protocol.
Supports: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML

Tools:
  - search_documents  (primary search)
  - search_pdfs       (deprecated alias, backward compatible)
  - list_indexed_documents
  - get_index_stats
  - index_documents   (in-conversation indexing)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_PERSIST_DIR, DEFAULT_EMBEDDING_MODEL, DEFAULT_SEARCH_RESULTS, MAX_SEARCH_RESULTS, DEFAULT_CHUNK_SIZE
from vector_store import DocumentVectorStore, check_ollama_connection

# Log to stderr only — stdout is MCP transport
logger = logging.getLogger(__name__)

# Configuration from environment variables
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", DEFAULT_PERSIST_DIR)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", DEFAULT_EMBEDDING_MODEL)


class Talk2DocsServer:
    """MCP server exposing document search and indexing tools."""

    def __init__(self):
        self.server = Server("talk2docs")
        self._store = None
        self._register_handlers()

    @property
    def store(self) -> DocumentVectorStore:
        """Lazy-load the vector store on first access."""
        if self._store is None:
            self._store = DocumentVectorStore(
                persist_dir=CHROMA_DB_PATH,
                model=OLLAMA_MODEL,
            )
        return self._store

    def _register_handlers(self):
        """Register MCP tool list and call handlers."""

        @self.server.list_tools()
        async def list_tools():
            return self._list_tools()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            return await self._call_tool(name, arguments)

    def _list_tools(self) -> list[Tool]:
        """Return the list of available MCP tools."""
        search_schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query - can be a question or keywords",
                },
                "num_results": {
                    "type": "integer",
                    "description": f"Number of results to return (default: {DEFAULT_SEARCH_RESULTS}, max: {MAX_SEARCH_RESULTS})",
                    "default": DEFAULT_SEARCH_RESULTS,
                    "minimum": 1,
                    "maximum": MAX_SEARCH_RESULTS,
                },
            },
            "required": ["query"],
        }

        return [
            Tool(
                name="search_documents",
                description=(
                    "Search through indexed documents using semantic search. "
                    "Supports PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV, and more. "
                    "Returns relevant text chunks with source documents and relevance scores."
                ),
                inputSchema=search_schema,
            ),
            Tool(
                name="search_pdfs",
                description=(
                    "Search through indexed documents using semantic search. "
                    "Supports PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV, and more. "
                    "Returns relevant text chunks with source documents and relevance scores."
                ),
                inputSchema=search_schema,
            ),
            Tool(
                name="list_indexed_documents",
                description=(
                    "List all documents that have been indexed and are searchable "
                    "(PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV, etc.)."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_index_stats",
                description=(
                    "Get statistics about the document index including document count, "
                    "chunk count, and model info."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="index_documents",
                description=(
                    "Index documents into the vector store for searching. "
                    "Accepts file or directory paths. Supports PDF, DOCX, XLSX, PPTX, ODT, "
                    "TXT, MD, HTML, CSV, and more."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file or directory paths to index",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Re-index documents that are already indexed (default: false)",
                            "default": False,
                        },
                        "engine": {
                            "type": "string",
                            "enum": ["library", "tiparse"],
                            "description": "Extraction engine to use (default: library)",
                            "default": "library",
                        },
                    },
                    "required": ["paths"],
                },
            ),
        ]

    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        """Route tool calls to the appropriate handler."""
        if name in ("search_documents", "search_pdfs"):
            return self._handle_search(arguments)
        elif name == "list_indexed_documents":
            return self._handle_list()
        elif name == "get_index_stats":
            return self._handle_stats()
        elif name == "index_documents":
            return await self._handle_index(arguments)

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # ---- Search ----

    def _handle_search(self, arguments: dict) -> list[TextContent]:
        query = arguments.get("query", "")
        num_results = min(arguments.get("num_results", DEFAULT_SEARCH_RESULTS), MAX_SEARCH_RESULTS)

        if not query:
            return [TextContent(type="text", text="Error: Query is required")]

        try:
            results = self.store.search(query, num_results)

            if not results:
                return [TextContent(
                    type="text",
                    text=f"No results found for: '{query}'\n\nTip: Make sure documents have been indexed using: python index.py <folder>",
                )]

            output = f"## Search Results for: '{query}'\n\n"
            for i, r in enumerate(results, 1):
                output += f"### [{i}] {r.source} (relevance: {r.score})\n"
                output += f"{r.text}\n\n"
                output += "---\n\n"
            output += f"*Found {len(results)} relevant chunks*"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            logger.error("Search error: %s", e)
            return [TextContent(type="text", text=f"Error searching: {str(e)}")]

    # ---- List ----

    def _handle_list(self) -> list[TextContent]:
        try:
            docs = self.store.list_documents()

            if not docs:
                return [TextContent(
                    type="text",
                    text="No documents indexed.\n\nUse `python index.py <folder>` to index documents.\nSupported: PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV",
                )]

            output = "## Indexed Documents\n\n"
            output += "| Document | Chunks |\n"
            output += "|----------|--------|\n"
            for doc, count in sorted(docs.items()):
                output += f"| {doc} | {count} |\n"

            stats = self.store.get_stats()
            output += f"\n**Total:** {stats.total_documents} documents, {stats.total_chunks} chunks"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            logger.error("List error: %s", e)
            return [TextContent(type="text", text=f"Error listing documents: {str(e)}")]

    # ---- Stats ----

    def _handle_stats(self) -> list[TextContent]:
        try:
            stats = self.store.get_stats()

            output = "## Index Statistics\n\n"
            output += f"- **Documents:** {stats.total_documents}\n"
            output += f"- **Total Chunks:** {stats.total_chunks}\n"
            output += f"- **Embedding Model:** {stats.model}\n"
            output += f"- **Database Path:** {stats.persist_dir}\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            logger.error("Stats error: %s", e)
            return [TextContent(type="text", text=f"Error getting stats: {str(e)}")]

    # ---- Index ----

    async def _handle_index(self, arguments: dict) -> list[TextContent]:
        raw_paths = arguments.get("paths", [])
        force = arguments.get("force", False)
        engine_name = arguments.get("engine", "library")

        if not raw_paths:
            return [TextContent(type="text", text="Error: At least one path is required")]

        try:
            from index import find_documents, index_file
            from extraction_engine import create_engine

            engine = create_engine(engine_name, chunk_size=DEFAULT_CHUNK_SIZE)

            all_files = []
            for p in raw_paths:
                expanded = os.path.expanduser(p)
                all_files.extend(find_documents(expanded))

            if not all_files:
                return [TextContent(type="text", text=f"No supported documents found in: {', '.join(raw_paths)}")]

            results = []
            indexed = 0
            skipped = 0
            failed = 0

            for file_path in all_files:
                result = index_file(file_path, self.store, engine=engine, force=force, quiet=True)
                results.append(result)
                if result.success:
                    indexed += 1
                elif "Already indexed" in result.message:
                    skipped += 1
                else:
                    failed += 1

            # Build markdown summary
            output = "## Indexing Results\n\n"
            output += f"- **Indexed:** {indexed} documents\n"
            output += f"- **Skipped:** {skipped} documents\n"
            output += f"- **Failed:** {failed} documents\n"
            output += f"- **Engine:** {engine_name}\n\n"

            if results:
                output += "| Document | Status | Chunks |\n"
                output += "|----------|--------|--------|\n"
                for r in results:
                    status = "Indexed" if r.success else ("Skipped" if "Already indexed" in r.message else "Failed")
                    output += f"| {r.doc_id} | {status} | {r.num_chunks} |\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            logger.error("Index error: %s", e)
            return [TextContent(type="text", text=f"Error indexing documents: {str(e)}")]

    async def run(self):
        """Start the MCP server."""
        if not check_ollama_connection():
            logger.warning("Ollama is not running. Start with: ollama serve")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point for the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    app = Talk2DocsServer()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
