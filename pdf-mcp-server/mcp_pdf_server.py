#!/usr/bin/env python3
"""
MCP Server for Document Search
Exposes document vector search capabilities to Claude CLI via MCP protocol.
Supports: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from vector_store import PDFVectorStore, check_ollama_connection

# Configuration from environment variables
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")

# Initialize server
server = Server("pdf-search")

# Initialize vector store (lazy loading)
_store = None


def get_store() -> PDFVectorStore:
    """Get or create the vector store instance."""
    global _store
    if _store is None:
        _store = PDFVectorStore(
            persist_dir=CHROMA_DB_PATH,
            model=OLLAMA_MODEL
        )
    return _store


@server.list_tools()
async def list_tools():
    """List available MCP tools."""
    return [
        Tool(
            name="search_pdfs",
            description="Search through indexed documents using semantic search. Supports PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV, and more. Returns relevant text chunks with source documents and relevance scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query - can be a question or keywords"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_indexed_documents",
            description="List all documents that have been indexed and are searchable (PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV, etc.).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_index_stats",
            description="Get statistics about the document index including document count, chunk count, and model info.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "search_pdfs":
        query = arguments.get("query", "")
        num_results = min(arguments.get("num_results", 5), 20)

        if not query:
            return [TextContent(type="text", text="Error: Query is required")]

        try:
            store = get_store()
            results = store.search(query, num_results)

            if not results:
                return [TextContent(
                    type="text",
                    text=f"No results found for: '{query}'\n\nTip: Make sure documents have been indexed using: python index_documents.py <folder>"
                )]

            # Format results
            output = f"## Search Results for: '{query}'\n\n"

            for i, r in enumerate(results, 1):
                output += f"### [{i}] {r['source']} (relevance: {r['score']})\n"
                output += f"{r['text']}\n\n"
                output += "---\n\n"

            output += f"*Found {len(results)} relevant chunks*"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error searching: {str(e)}")]

    elif name == "list_indexed_documents":
        try:
            store = get_store()
            docs = store.list_documents()

            if not docs:
                return [TextContent(
                    type="text",
                    text="No documents indexed.\n\nUse `python index_documents.py <folder>` to index documents.\nSupported: PDF, DOCX, XLSX, PPTX, ODT, TXT, MD, HTML, CSV"
                )]

            output = "## Indexed Documents\n\n"
            output += "| Document | Chunks |\n"
            output += "|----------|--------|\n"

            for doc, count in sorted(docs.items()):
                output += f"| {doc} | {count} |\n"

            stats = store.get_stats()
            output += f"\n**Total:** {stats['total_documents']} documents, {stats['total_chunks']} chunks"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error listing documents: {str(e)}")]

    elif name == "get_index_stats":
        try:
            store = get_store()
            stats = store.get_stats()

            output = "## Index Statistics\n\n"
            output += f"- **Documents:** {stats['total_documents']}\n"
            output += f"- **Total Chunks:** {stats['total_chunks']}\n"
            output += f"- **Embedding Model:** {stats['model']}\n"
            output += f"- **Database Path:** {stats['persist_dir']}\n"

            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error getting stats: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Main entry point for the MCP server."""

    # Check Ollama connection at startup
    if not check_ollama_connection():
        print("WARNING: Ollama is not running. Start with: ollama serve", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
