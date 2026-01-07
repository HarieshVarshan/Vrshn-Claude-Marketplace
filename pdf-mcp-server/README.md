# PDF MCP Server

MCP server for semantic search across PDF documents using Ollama embeddings and ChromaDB.

## Prerequisites

1. **Python 3.10+**
2. **Ollama** - for local embeddings

## Setup

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text

# Verify
ollama list
```

### 2. Create Virtual Environment

```bash
cd /home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Index Your PDFs

```bash
# Bulk index a folder
python index_pdfs.py /path/to/pdfs

# Or add individual files
python add_pdf.py document1.pdf document2.pdf
```

### 4. Configure Claude Code

```bash
claude mcp add --transport stdio --scope user pdf-search \
  --env CHROMA_DB_PATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server/chroma_db \
  --env PYTHONPATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server \
  -- /home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server/venv/bin/python \
  /home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server/mcp_pdf_server.py
```

### 5. Verify & Restart Claude Code

```bash
# Verify MCP server is registered
claude mcp list

# Restart Claude Code and check /mcp
/exit
claude
/mcp
```

> For detailed setup instructions, troubleshooting, and what happens after reboot, see [local_mcp_server_claude_integration_guide.md](local_mcp_server_claude_integration_guide.md)

## Usage

### CLI Tools

```bash
# Index all PDFs in a directory
python index_pdfs.py ./pdfs

# Add specific PDFs (skips duplicates)
python add_pdf.py new_doc.pdf another.pdf

# Force re-index
python add_pdf.py --force updated_doc.pdf

# Manage index
python manage_index.py list              # List all documents
python manage_index.py stats             # Show statistics
python manage_index.py search "query"    # Search from CLI
python manage_index.py remove doc.pdf    # Remove a document
python manage_index.py clear             # Clear entire index
```

### In Claude CLI

Once configured, ask Claude:
- "Search the PDFs for DMA configuration"
- "What do my documents say about clock topology?"
- "List all indexed documents"

## MCP Tools Exposed

| Tool | Description |
|------|-------------|
| `search_pdfs` | Semantic search across all indexed PDFs |
| `list_indexed_documents` | List all indexed documents with chunk counts |
| `get_index_stats` | Get index statistics |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_DB_PATH` | `./chroma_db` | Vector database directory |
| `OLLAMA_MODEL` | `nomic-embed-text` | Ollama embedding model |

## Project Structure

```
pdf-mcp-server/
├── pdf_extractor.py      # PDF text extraction
├── chunker.py            # Text chunking
├── vector_store.py       # ChromaDB + Ollama embeddings
├── index_pdfs.py         # Bulk indexing script
├── add_pdf.py            # Incremental indexing
├── manage_index.py       # Index management
├── mcp_pdf_server.py     # MCP server
├── requirements.txt
├── chroma_db/            # Vector database (auto-created)
└── pdfs/                 # Put PDFs here
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama connection refused | Run `ollama serve` |
| Model not found | Run `ollama pull nomic-embed-text` |
| MCP not showing in `/mcp` | Run `claude mcp list` to verify, then restart Claude Code |
| Import errors | Ensure PYTHONPATH is set in env config |

See [local_mcp_server_claude_integration_guide.md](local_mcp_server_claude_integration_guide.md) for detailed troubleshooting.
