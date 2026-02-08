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

**Important:** Ollama must be running for both indexing and searching (it converts text to embeddings).

**Start Ollama:**
```bash
# Option 1: Run manually (foreground) - Ctrl+C to stop
ollama serve

# Option 2: Run as background process
nohup ollama serve > /dev/null 2>&1 &

# Option 3: Run as systemd service (recommended for always-on)
sudo systemctl enable ollama
sudo systemctl start ollama
```

**Stop Ollama:**
```bash
# For Option 1: Press Ctrl+C in the terminal

# For Option 2: Kill background process
pkill ollama
# or find and kill specific PID
pgrep ollama && kill $(pgrep ollama)

# For Option 3: Stop systemd service
sudo systemctl stop ollama
# To disable auto-start on boot
sudo systemctl disable ollama

# Verify no ollama processes remain
pgrep -a ollama
```

### 2. Create Virtual Environment

```bash
cd /home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Index Your Documents

```bash
# Index all supported documents in a folder
python index.py ./docs

# Index specific files
python index.py report.pdf data.xlsx presentation.pptx

# Index specific file types only
python index.py ./docs --ext pdf docx xlsx

# Force re-index
python index.py --force updated_doc.pdf
python index.py --force ./docs

# Faster indexing with parallelism (see Performance section below)
python index.py ./docs -w 16              # 16 embedding workers
python index.py ./docs -p 4               # 4 documents in parallel
python index.py ./docs -p 4 -w 8          # Combined: 4 docs × 8 workers

# Batched embedding (more efficient for large document sets)
python index.py ./docs --batch            # Batch mode: embed every 5000 chunks
python index.py ./docs -b -B 10000        # Custom batch size of 10000 chunks
```

### 4. Configure Claude Code

```bash
claude mcp add --transport stdio --scope user ldoc-search \
  --env CHROMA_DB_PATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/chroma_db \
  --env PYTHONPATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server \
  -- /home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/venv/bin/python \
  /home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/mcp_server.py
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
# Index files or directories (unified interface)
python index.py ./docs                        # Index all documents in folder
python index.py file1.pdf file2.docx          # Index specific files
python index.py ./docs --ext pdf docx         # Index only specific formats
python index.py --force updated_doc.pdf       # Force re-index a file
python index.py --force ./docs                # Force re-index entire folder

# Manage index
python manage_index.py list              # List all documents
python manage_index.py stats             # Show statistics
python manage_index.py search "query"    # Search from CLI
python manage_index.py remove doc.pdf    # Remove a document
python manage_index.py rename old.pdf new.pdf  # Rename (no re-embedding)
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
| Rename documents | No |
| Change MCP server config | **Yes** |
| Change MCP server code | **Yes** |

New/updated documents are searchable immediately after indexing:
```bash
python index.py new_report.docx
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

# Rename a document (no re-embedding needed)
python manage_index.py rename old_name.pdf new_name.pdf

# Re-index updated files
python index.py --force updated_doc.docx

# Clear and rebuild entire index (if needed)
python manage_index.py clear
python index.py ./docs
```

For typical use (hundreds to a few thousand documents), you won't hit any issues.

## Performance & Parallelism

Indexing can be slow for large documents. Use these options to speed it up:

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-w, --workers` | Parallel embedding requests per document | 8 |
| `-p, --parallel` | Number of documents to process simultaneously | 1 |
| `-b, --batch` | Enable batched embedding mode (accumulate chunks) | off |
| `-B, --batch-size` | Number of chunks to accumulate before embedding | 5000 |

### Examples

```bash
# Default: 8 workers, 1 document at a time
python index.py ./docs

# More embedding workers (good for single large files)
python index.py large_doc.pdf -w 16

# Multiple documents in parallel (good for many small files)
python index.py ./docs -p 4

# Maximum parallelism (4 docs × 8 workers = 32 concurrent requests)
python index.py ./docs -p 4 -w 8

# Batched embedding (efficient for large document sets)
python index.py ./docs --batch            # Embed every 5000 chunks
python index.py ./docs -b -B 10000        # Custom batch size
python index.py ./docs -b -w 16           # Batch mode with more workers

# Using environment variable
OLLAMA_WORKERS=16 python index.py ./docs
```

### Recommendations

| Scenario | Recommended Settings |
|----------|---------------------|
| Single large document (>10K chunks) | `-w 16` or higher |
| Many small documents | `-p 4` with default workers |
| Mixed documents | `-p 2 -w 8` |
| Large document sets (100+ files) | `--batch` or `-b -B 10000` |
| Limited CPU/RAM | `-w 4 -p 1` (reduce parallelism) |

### Performance Comparison

| Setting | Concurrent Ollama Requests | Use Case |
|---------|---------------------------|----------|
| Default (`-w 8 -p 1`) | 8 | Balanced |
| `-w 16` | 16 | Large single file |
| `-p 4` | 32 (4 × 8) | Many files |
| `-p 4 -w 4` | 16 | Memory constrained |
| `--batch` | 8 (batched) | Large document sets |
| `-b -w 16` | 16 (batched) | Optimal for 100+ files |

**Note:** If Ollama starts timing out or your system becomes unresponsive, reduce the parallelism.

### Batched Embedding Mode

The `--batch` flag enables a more efficient embedding strategy for large document sets:

- **Without batch mode**: Each document's chunks are embedded immediately after extraction
- **With batch mode**: Chunks are accumulated across documents and embedded in batches of 5000 (configurable with `-B`)

This reduces overhead when indexing many documents, as embedding is a costly operation. The batch is automatically flushed at the end of indexing.

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
| `OLLAMA_WORKERS` | `8` | Parallel embedding requests to Ollama |

## Project Structure

```
ldoc-mcp-server/
├── index.py              # Unified indexing (files, folders, updates)
├── document_extractor.py # Multi-format text extraction
├── chunker.py            # Text chunking
├── vector_store.py       # ChromaDB + Ollama embeddings
├── manage_index.py       # Index management (list, search, remove)
├── mcp_server.py         # MCP server
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
1. ~~since we support multiple file formats instead of pdf-mcp-server can be rename it as ldoc-mcp-server and also update claude mcp as ldoc-mcp so that nothing breaks.~~ ✅ Done
2. ~~add progress bar and time taken while embedding files. (for each files and also overall)~~ ✅ Done
3. how to use this standalone without claude?
4. how to make this the chromadb and mcp-server available to my entire team, I dont want them to know about how to add embeddings, i just want them to use with whatever I have trained and stored in db at any point in time?
5. I understand where are limitation to how big the db can be? So in large system as it grows how do we scale this?
6. I have more budget what all can I improve in this project to make it even better or the best?