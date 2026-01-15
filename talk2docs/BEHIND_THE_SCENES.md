# How It Works - Behind the Scenes

This document explains the vector embedding-based search system powering the Document MCP Server.

---

## Overview

The system uses **vector embeddings** for semantic search - the same technology behind RAG (Retrieval Augmented Generation) systems.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Document   │ --> │   Extract   │ --> │    Chunk    │ --> │    Embed    │
│ (PDF/DOCX)  │     │    Text     │     │    Text     │     │   (Ollama)  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                                                                   v
                                                            ┌─────────────┐
                                                            │   ChromaDB  │
                                                            │  (Vectors)  │
                                                            └─────────────┘
```

---

## Indexing Pipeline

When you run `python index_documents.py ./docs`:

### Step 1: Extract Text

```
document_extractor.py
```

| Format | Library Used |
|--------|--------------|
| PDF | PyMuPDF (fitz) |
| DOCX | python-docx |
| XLSX | openpyxl |
| PPTX | python-pptx |
| ODT/ODS/ODP | odfpy |
| HTML | BeautifulSoup |
| TXT/MD/CSV | Built-in Python |

### Step 2: Chunk Text

```
chunker.py
```

Large documents are split into smaller chunks (~500-1000 characters) because:
- Embedding models have token limits
- Smaller chunks = more precise search results
- Each chunk becomes a searchable unit

**Example:**
```
Original: 10,000 character document
   ↓
Chunks: 15-20 chunks of ~500-700 chars each
```

### Step 3: Generate Embeddings

```
vector_store.py → Ollama API
```

Each text chunk is converted to a **768-dimensional vector** using Ollama's `nomic-embed-text` model.

```
"DMA transfers data directly between memory and peripherals"
                           ↓
              Ollama (nomic-embed-text)
                           ↓
     [0.023, -0.156, 0.089, ..., 0.045]  (768 numbers)
```

**Why vectors?**
- Similar meanings → Similar vectors
- "DMA transfer" and "direct memory access" have similar vectors
- Enables semantic search, not just keyword matching

### Step 4: Store in ChromaDB

```
chroma_db/
```

ChromaDB stores:
- The original text chunk
- Its vector embedding
- Metadata (source file, chunk index)

---

## Search Pipeline

When you search in Claude: "What is DMA configuration?"

### Step 1: Embed the Query

```
Query: "What is DMA configuration?"
                ↓
        Ollama (same model)
                ↓
   [0.018, -0.142, 0.095, ..., 0.038]  (768-dim vector)
```

### Step 2: Find Similar Vectors

ChromaDB performs **cosine similarity search**:

```
Query Vector ←──compare──→ All Stored Vectors
                               ↓
                    Return top N most similar
```

### Step 3: Return Results

```
┌────────────────────────────────────────────────────┐
│ Result 1: spec.pdf (similarity: 0.89)              │
│ "The DMA controller handles data transfers..."     │
├────────────────────────────────────────────────────┤
│ Result 2: manual.pdf (similarity: 0.82)            │
│ "Configure DMA channels using the following..."    │
└────────────────────────────────────────────────────┘
```

---

## Key Components

| Component | File | Role |
|-----------|------|------|
| **Document Extractor** | `document_extractor.py` | Extract text from various formats |
| **Chunker** | `chunker.py` | Split text into searchable chunks |
| **Vector Store** | `vector_store.py` | Manage ChromaDB + Ollama embeddings |
| **MCP Server** | `mcp_pdf_server.py` | Expose search to Claude Code |

---

## Why Vector Embeddings?

### Traditional Keyword Search
```
Query: "DMA transfer"
Result: Only finds documents containing exact words "DMA" and "transfer"
```

### Vector Semantic Search
```
Query: "DMA transfer"
Result: Finds documents about:
  - "direct memory access"
  - "data movement without CPU"
  - "peripheral to memory copying"
  - AND exact matches
```

**Vectors capture meaning, not just words.**

---

## The Embedding Model

**Model:** `nomic-embed-text` (via Ollama)

| Property | Value |
|----------|-------|
| Dimensions | 768 |
| Context Length | ~8,000 tokens |
| Type | Sentence/passage embeddings |
| Runs on | Local (Ollama) |

**Why local?**
- Privacy - documents never leave your machine
- Speed - no API latency
- Cost - no per-query charges

---

## Data Flow Diagram

```
                    INDEXING
                    ========

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  Files   │───>│ Extract  │───>│  Chunk   │───>│  Embed   │
  │ PDF/DOCX │    │   Text   │    │  (~500c) │    │ (Ollama) │
  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                       │
                                                       v
                                                 ┌──────────┐
                                                 │ ChromaDB │
                                                 │ (Vectors)│
                                                 └────┬─────┘
                                                      │
                    SEARCHING                         │
                    =========                         │
                                                      │
  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
  │  Query   │───>│  Embed   │───>│ Cosine   │<──────┘
  │  Text    │    │ (Ollama) │    │ Search   │
  └──────────┘    └──────────┘    └────┬─────┘
                                       │
                                       v
                                 ┌──────────┐
                                 │ Results  │
                                 │ (Chunks) │
                                 └──────────┘
```

---

## Storage Structure

```
chroma_db/
├── chroma.sqlite3      # Metadata & mappings
└── [uuid]/
    ├── data_level0.bin # Vector data
    ├── header.bin      # Index header
    ├── index_metadata.json
    └── length.bin
```

Each indexed document creates entries with:
- **ID:** `{filename}_chunk_{n}`
- **Document:** Original text chunk
- **Embedding:** 768-dim vector
- **Metadata:** `{source: filename, chunk_index: n, file_type: ...}`

---

## Performance Characteristics

| Operation | Speed | Notes |
|-----------|-------|-------|
| Embedding (indexing) | ~2-5 sec/chunk | Depends on chunk size & CPU/GPU |
| Search query | ~100-500ms | Fast vector lookup |
| Adding documents | Linear | Each doc processed independently |
| Search at scale | Sub-linear | ChromaDB uses HNSW indexing |

---

## Summary

1. **Documents** are converted to **text**
2. **Text** is split into **chunks**
3. **Chunks** become **768-dimensional vectors** via Ollama
4. **Vectors** are stored in **ChromaDB**
5. **Queries** are embedded and compared using **cosine similarity**
6. **Similar chunks** are returned as search results

This enables **semantic search** - finding relevant content based on meaning, not just keywords.
