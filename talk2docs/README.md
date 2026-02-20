# talk2docs

An MCP server that lets you talk to your documents using natural language. Index your files into a local vector database and search them semantically from Claude Code.

Under the hood, talk2docs extracts text from 16+ file formats, chunks it, embeds it via Ollama, and stores everything in ChromaDB. When you ask Claude a question, it searches the vector database and returns the most relevant passages with source references.

## Supported Formats

| Format | Extensions |
|--------|------------|
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| Excel | `.xlsx`, `.xls` |
| PowerPoint | `.pptx` |
| OpenDocument | `.odt`, `.ods`, `.odp` |
| Text | `.txt`, `.md` |
| Web | `.html`, `.htm` |
| Data | `.csv`, `.json`, `.xml` |

## Prerequisites

- **Python 3.10+**
- **Ollama** running locally with the `nomic-embed-text` model

## Setup

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text
ollama serve
```

### 2. Install Dependencies

```bash
cd talk2docs
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

# Index only certain file types
python index.py ./docs --ext pdf docx xlsx

# Force re-index already indexed files
python index.py --force ./docs
```

### 4. Register with Claude Code

```bash
claude mcp add --transport stdio --scope user talk2docs \
  --env CHROMA_DB_PATH=$(pwd)/chroma_db \
  --env OLLAMA_MODEL=nomic-embed-text \
  -- $(pwd)/venv/bin/python $(pwd)/mcp_server.py
```

### 5. Verify

Restart Claude Code, then check:

```bash
claude mcp list    # Should show talk2docs
/mcp               # Inside Claude Code, should list talk2docs
```

## Usage

### Talking to Your Documents in Claude Code

Once configured, just ask Claude questions about your documents:

- *"Search my documents for DMA configuration"*
- *"What do my documents say about clock topology?"*
- *"List all indexed documents"*
- *"Index the files in ~/new-specs/"*

No restart is needed after indexing new documents. The vector database is queried live on each search.

### MCP Tools

| Tool | Description |
|------|-------------|
| `search_documents` | Semantic search across all indexed documents |
| `search_pdfs` | Alias for `search_documents` (backward compatible) |
| `list_indexed_documents` | List all indexed documents with chunk counts |
| `get_index_stats` | Index statistics (document count, chunk count, model info) |
| `index_documents` | Index new documents directly from a Claude conversation |

### CLI Tools

```bash
# Indexing
python index.py ./docs                        # Index a folder
python index.py file1.pdf file2.docx          # Index specific files
python index.py ./docs --ext pdf docx         # Filter by extension
python index.py --force ./docs                # Force re-index

# Index management
python manage_index.py list                   # List all indexed documents
python manage_index.py stats                  # Show index statistics
python manage_index.py search "query"         # Search from the terminal
python manage_index.py remove doc.pdf         # Remove a document
python manage_index.py rename old.pdf new.pdf # Rename without re-embedding
python manage_index.py clear                  # Clear entire index

# Test extraction
python document_extractor.py myfile.docx
```

## Extraction Engines

talk2docs supports two extraction engines:

| Engine | Description | Formats |
|--------|-------------|---------|
| `library` (default) | Local libraries (PyMuPDF, python-docx, etc.) | All 16+ formats |
| `tiparse` | LLM-powered extraction via TiParse | PDF, HTML, TXT, MD (auto-falls back to `library` for others) |

```bash
# Use the default library engine
python index.py ./docs

# Use TiParse for higher-quality extraction
python index.py --engine tiparse report.pdf

# TiParse with a specific model
python index.py --engine tiparse --tiparse-model gpt-4o report.pdf
```

TiParse requires `pip install tiparse>=1.1.0` and an OpenAI-compatible API key (`OPENAI_API_KEY`, `OPENAI_BASE_URL`).

## Performance & Parallelism

| Option | Description | Default |
|--------|-------------|---------|
| `-w, --workers` | Parallel embedding requests per document | 8 |
| `-p, --parallel` | Documents to process simultaneously | 1 |
| `-b, --batch` | Batched embedding mode (accumulate chunks across documents) | off |
| `-B, --batch-size` | Chunks per batch in batched mode | 5000 |

```bash
# More embedding workers (good for single large files)
python index.py large_doc.pdf -w 16

# Multiple documents in parallel (good for many small files)
python index.py ./docs -p 4

# Combined: 4 docs x 8 workers = 32 concurrent Ollama requests
python index.py ./docs -p 4 -w 8

# Batched embedding (efficient for large document sets)
python index.py ./docs --batch
python index.py ./docs -b -B 10000
```

| Scenario | Recommended |
|----------|-------------|
| Single large document | `-w 16` |
| Many small documents | `-p 4` |
| Mixed documents | `-p 2 -w 8` |
| 100+ files | `--batch` or `-b -B 10000` |
| Limited CPU/RAM | `-w 4 -p 1` |

If Ollama starts timing out or the system becomes unresponsive, reduce the parallelism.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_DB_PATH` | `./chroma_db` | Vector database directory |
| `OLLAMA_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `OLLAMA_WORKERS` | `8` | Parallel embedding requests |
| `OPENAI_API_KEY` | — | API key for TiParse engine (optional) |
| `OPENAI_BASE_URL` | — | API base URL for TiParse engine (optional) |

## Do I Need to Restart Claude Code?

| Action | Restart? |
|--------|----------|
| Index new documents | No |
| Re-index / remove / rename documents | No |
| Change MCP server config or code | Yes |

New documents are searchable immediately after indexing.

## Project Structure

```
talk2docs/
├── mcp_server.py          # MCP server (Talk2DocsServer)
├── index.py               # Indexing CLI
├── manage_index.py        # Index management CLI
├── config.py              # Centralized constants
├── models.py              # Data types (SearchResult, IndexingResult, IndexStats)
├── extraction_engine.py   # Engine abstraction (LibraryEngine, TiParseEngine)
├── document_extractor.py  # Multi-format text extraction
├── chunker.py             # Paragraph-aware text chunking
├── vector_store.py        # ChromaDB + Ollama embedding client
├── requirements.txt
├── tests/                 # Test suite
├── dev_docs/              # Development documentation
├── chroma_db/             # Vector database (auto-created)
└── mcp-servers.json       # MCP server configuration
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama connection refused | Run `ollama serve` |
| Model not found | Run `ollama pull nomic-embed-text` |
| MCP not showing in `/mcp` | Run `claude mcp list` to verify, then restart Claude Code |
| Import errors | Ensure `PYTHONPATH` is set in MCP env config |
| Unsupported format | Check supported formats table above |
| `.doc` files not extracting | Install `antiword` or `catdoc` for legacy Word |

See [dev_docs/local_mcp_server_claude_integration_guide.md](dev_docs/local_mcp_server_claude_integration_guide.md) for detailed setup and troubleshooting.

## TODOs

1. How to use talk2docs standalone without Claude?
2. How to share the ChromaDB across a team without requiring everyone to index?
3. Scaling strategy as the database grows.
