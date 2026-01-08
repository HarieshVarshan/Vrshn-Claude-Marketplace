#!/usr/bin/env python3
"""
Unified Document Indexing Script
Index files or folders to the vector store with support for incremental updates.

Supported formats: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML

Usage:
    python index.py file.pdf                    # Index a single file
    python index.py file1.pdf file2.docx        # Index multiple files
    python index.py ./docs                      # Index all documents in folder
    python index.py ./docs --ext pdf docx       # Index only specific formats
    python index.py --force file.pdf            # Force re-index existing file
    python index.py --force ./docs              # Force re-index entire folder
"""

import glob
import os
import sys
import time
from pathlib import Path

from document_extractor import extract_text, is_supported, get_supported_extensions, get_file_type
from chunker import chunk_by_paragraphs
from vector_store import DocumentVectorStore, check_ollama_connection, check_model_available


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def index_file(
    file_path: str,
    store: DocumentVectorStore,
    chunk_size: int = 500,
    force: bool = False
) -> tuple[bool, str, float]:
    """
    Index a single file to the vector store.

    Args:
        file_path: Path to the file
        store: Vector store instance
        chunk_size: Maximum chunk size
        force: Re-index if already exists

    Returns:
        Tuple of (success, status_message, time_taken)
    """
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}", 0.0

    if not is_supported(file_path):
        return False, f"Unsupported format: {Path(file_path).suffix}", 0.0

    doc_id = os.path.basename(file_path)
    file_type = get_file_type(file_path)

    # Check if already indexed
    if store.is_document_indexed(doc_id):
        if force:
            print(f"  Re-indexing: {doc_id}")
            store.remove_document(doc_id)
        else:
            chunks = store.get_document_chunks(doc_id)
            return False, f"Already indexed ({len(chunks)} chunks). Use --force to re-index.", 0.0

    try:
        start_time = time.time()

        # Extract text
        text = extract_text(file_path)
        if not text.strip():
            return False, "No text extracted", 0.0

        # Chunk text
        chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)

        # Add to store
        metadata = {
            "file_path": os.path.abspath(file_path),
            "file_type": file_type
        }
        num_added, embed_time = store.add_document(doc_id, chunks, metadata)
        total_time = time.time() - start_time
        return True, f"Indexed {num_added} chunks in {format_time(total_time)}", total_time

    except Exception as e:
        return False, f"Error: {e}", 0.0


def find_documents(path: str, extensions: list[str] | None = None) -> list[str]:
    """
    Find all supported documents in a path.

    Args:
        path: File or directory path
        extensions: List of extensions to filter (None = all supported)

    Returns:
        List of file paths
    """
    path = os.path.abspath(path)

    # Single file
    if os.path.isfile(path):
        if is_supported(path):
            return [path]
        return []

    # Directory
    if not os.path.isdir(path):
        return []

    # Determine extensions to search for
    if extensions:
        search_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
    else:
        search_exts = get_supported_extensions()

    # Find files
    files = set()
    for ext in search_exts:
        patterns = [
            os.path.join(path, f"*{ext}"),
            os.path.join(path, f"*{ext.upper()}"),
            os.path.join(path, f"**/*{ext}"),
            os.path.join(path, f"**/*{ext.upper()}"),
        ]
        for pattern in patterns:
            files.update(glob.glob(pattern, recursive=True))

    return sorted(files)


def index(
    paths: list[str],
    persist_dir: str = "./chroma_db",
    chunk_size: int = 500,
    force: bool = False,
    extensions: list[str] | None = None
) -> dict:
    """
    Index files or directories to the vector store.

    Args:
        paths: List of file or directory paths
        persist_dir: Vector database directory
        chunk_size: Maximum chunk size in characters
        force: Re-index existing documents
        extensions: Only index specific extensions (for directories)

    Returns:
        Statistics dictionary
    """
    # Check Ollama
    if not check_ollama_connection():
        print("ERROR: Ollama is not running!")
        print("Start Ollama with: ollama serve")
        sys.exit(1)

    if not check_model_available("nomic-embed-text"):
        print("ERROR: nomic-embed-text model not found!")
        print("Pull it with: ollama pull nomic-embed-text")
        sys.exit(1)

    store = DocumentVectorStore(persist_dir)

    # Collect all files to index
    all_files = []
    for path in paths:
        files = find_documents(path, extensions)
        if not files:
            if os.path.isfile(path):
                print(f"Unsupported file: {path}")
            elif os.path.isdir(path):
                print(f"No supported documents in: {path}")
            else:
                print(f"Path not found: {path}")
        all_files.extend(files)

    # Remove duplicates, preserve order
    seen = set()
    unique_files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    if not unique_files:
        print("\nNo documents to index.")
        print(f"Supported formats: {', '.join(get_supported_extensions())}")
        return {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0}

    print(f"Found {len(unique_files)} document(s) to process")
    print("-" * 50)

    stats = {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0, "total_time": 0.0}
    overall_start = time.time()

    for i, file_path in enumerate(unique_files, 1):
        doc_name = os.path.basename(file_path)
        file_type = get_file_type(file_path)
        print(f"\n[{i}/{len(unique_files)}] {doc_name} ({file_type})")

        success, message, elapsed = index_file(file_path, store, chunk_size, force)

        if success:
            print(f"  ✓ {message}")
            stats["indexed"] += 1
            stats["total_time"] += elapsed
            # Extract chunk count from message
            try:
                num_chunks = int(message.split()[1])
                stats["total_chunks"] += num_chunks
            except (ValueError, IndexError):
                pass
        elif "Already indexed" in message:
            print(f"  → {message}")
            stats["skipped"] += 1
        else:
            print(f"  ✗ {message}")
            stats["failed"] += 1

    overall_time = time.time() - overall_start

    # Summary
    print("\n" + "=" * 50)
    print("Indexing Complete!")
    print(f"  Indexed: {stats['indexed']} documents ({stats['total_chunks']} chunks)")
    print(f"  Skipped: {stats['skipped']} documents")
    print(f"  Failed:  {stats['failed']} documents")
    print(f"  Time:    {format_time(overall_time)}")
    print(f"  Database: {persist_dir}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Index documents to vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Supported formats:
  {', '.join(get_supported_extensions())}

Examples:
  python index.py document.pdf              # Single file
  python index.py report.docx data.xlsx     # Multiple files
  python index.py ./docs                    # Entire directory
  python index.py ./docs --ext pdf docx     # Only PDF and DOCX
  python index.py --force updated.pdf       # Force re-index
  python index.py --force ./docs            # Re-index entire folder
"""
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="File(s) or directory to index"
    )
    parser.add_argument(
        "--db", "-d",
        default="./chroma_db",
        help="Vector database directory (default: ./chroma_db)"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=500,
        help="Maximum chunk size in characters (default: 500)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-index existing documents"
    )
    parser.add_argument(
        "--ext", "-e",
        nargs="+",
        help="Only index specific extensions (e.g., --ext pdf docx)"
    )

    args = parser.parse_args()

    index(
        paths=args.paths,
        persist_dir=args.db,
        chunk_size=args.chunk_size,
        force=args.force,
        extensions=args.ext
    )


if __name__ == "__main__":
    main()
