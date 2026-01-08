# Document MCP Server

MCP server for semantic search across documents using Ollama embeddings and ChromaDB.

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| PDF | `.pdf` | PDF documents |
| Word | `.docx`, `.doc` | Microsoft Word |
| Excel | `.xlsx`, `.xls` | Microsoft Excel |
| PowerPoint | `.pptx` | Microsoft PowerPoint |
| OpenDocument | `.odt`, `.ods`, `.odp` | LibreOffice/OpenOffice |
| Text | `.txt`, `.md` | Plain text, Markdown |
| Web | `.html`, `.htm` | HTML pages |
| Data | `.csv`, `.json`, `.xml` | Structured data |

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

### 3. Index Your Documents

```bash
# Index all supported documents in a folder
python index_documents.py /path/to/docs

# Index specific file types only
python index_documents.py /path/to/docs --ext pdf docx xlsx

# Add individual files
python add_document.py report.pdf data.xlsx presentation.pptx

# Force re-index
python add_document.py --force updated_doc.pdf
```

**Legacy scripts still available:**
```bash
python index_pdfs.py ./pdfs      # PDF only
python add_pdf.py doc.pdf        # PDF only
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
>
> To understand the vector embedding system behind the scenes, see [behind_the_scenes.md](behind_the_scenes.md)

## Usage

### CLI Tools

```bash
# Index all documents in a directory
python index_documents.py ./docs

# Index only specific formats
python index_documents.py ./docs --ext pdf docx xlsx

# Add specific documents (skips duplicates)
python add_document.py report.docx data.xlsx notes.md

# Force re-index
python add_document.py --force updated_doc.pdf

# Manage index
python manage_index.py list              # List all documents
python manage_index.py stats             # Show statistics
python manage_index.py search "query"    # Search from CLI
python manage_index.py remove doc.pdf    # Remove a document
python manage_index.py clear             # Clear entire index

# Test document extraction
python document_extractor.py myfile.docx
```

### In Claude CLI

Once configured, ask Claude:
- "Search the documents for DMA configuration"
- "What do my documents say about clock topology?"
- "List all indexed documents"
- "Search for budget data in the spreadsheets"

## Do I Need to Restart Claude Code?

**No restart needed** after indexing new documents. The MCP server queries ChromaDB dynamically on each search request.

| Action | Restart Required? |
|--------|-------------------|
| Add new documents | No |
| Update existing documents (re-index) | No |
| Remove documents | No |
| Change MCP server config | **Yes** |
| Change MCP server code | **Yes** |

New/updated documents are searchable immediately after indexing:
```bash
python add_document.py new_report.docx
# Immediately searchable - no restart needed
```

## Index Limits & Maintenance

There's **no hard limit** on documents, but consider these factors:

| Factor | Consideration |
|--------|---------------|
| ChromaDB capacity | Can handle millions of chunks |
| Disk space | `chroma_db/` folder grows with each document |
| Embedding speed | ~2-5 seconds per chunk during indexing |
| Query speed | Stays fast (efficient vector indexing) |

### Check Current Usage

```bash
# See index statistics
python manage_index.py stats

# Check database size on disk
du -sh chroma_db/
```

### Maintenance Tips

```bash
# Remove old/outdated documents
python manage_index.py remove old_doc.pdf

# Re-index updated files
python add_document.py --force updated_doc.docx

# Clear and rebuild entire index (if needed)
python manage_index.py clear
python index_documents.py ./docs
```

For typical use (hundreds to a few thousand documents), you won't hit any issues.

## MCP Tools Exposed

| Tool | Description |
|------|-------------|
| `search_pdfs` | Semantic search across all indexed documents |
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
├── document_extractor.py # Multi-format text extraction (NEW)
├── pdf_extractor.py      # PDF text extraction (legacy)
├── chunker.py            # Text chunking
├── vector_store.py       # ChromaDB + Ollama embeddings
├── index_documents.py    # Bulk indexing - all formats (NEW)
├── index_pdfs.py         # Bulk indexing - PDF only (legacy)
├── add_document.py       # Incremental indexing - all formats (NEW)
├── add_pdf.py            # Incremental indexing - PDF only (legacy)
├── manage_index.py       # Index management
├── mcp_pdf_server.py     # MCP server
├── requirements.txt
├── chroma_db/            # Vector database (auto-created)
└── docs/                 # Put documents here
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama connection refused | Run `ollama serve` |
| Model not found | Run `ollama pull nomic-embed-text` |
| MCP not showing in `/mcp` | Run `claude mcp list` to verify, then restart Claude Code |
| Import errors | Ensure PYTHONPATH is set in env config |
| Unsupported format | Check supported formats above |
| .doc files not extracting | Install `antiword` or `catdoc` for legacy Word support |

See [local_mcp_server_claude_integration_guide.md](local_mcp_server_claude_integration_guide.md) for detailed troubleshooting.

## Adding New Format Support

To add support for a new file format:

1. Edit `document_extractor.py`
2. Add extension to `SUPPORTED_EXTENSIONS` dict
3. Create `_extract_<format>()` function
4. Add to `extractors` dict in `extract_text()`


## TODOs
1. since we support multiple file formats instead of pdf-mcp-server can be rename it as ldoc-mcp-server and also update claude mcp as ldoc-mcp so that nothing breaks.
2. add progress bar and time taken while embedding files. (for each files and also overall)
3. how to use this standalone without claude?
4. how to make this the chromadb and mcp-server available to my entire team, I dont want them to know about how to add embeddings, i just want them to use with whatever I have trained and stored in db at any point in time?
5. I understand where are limitation to how big the db can be? So in large system as it grows how do we scale this?
6. I have more budget what all can I improve in this project to make it even better or the best?