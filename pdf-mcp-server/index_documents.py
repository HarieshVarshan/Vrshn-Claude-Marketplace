#!/usr/bin/env python3
"""
Bulk Document Indexing Script
Index all supported documents in a directory to the vector store.

Supported formats: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML
"""

import glob
import os
import sys
from pathlib import Path

from document_extractor import extract_text, is_supported, get_supported_extensions, get_file_type
from chunker import chunk_by_paragraphs
from vector_store import PDFVectorStore, check_ollama_connection, check_model_available


def index_document_directory(
    doc_dir: str,
    persist_dir: str = "./chroma_db",
    chunk_size: int = 500,
    skip_existing: bool = True,
    extensions: list[str] = None
) -> dict:
    """
    Index all supported documents in a directory.

    Args:
        doc_dir: Directory containing document files
        persist_dir: Directory to persist vector database
        chunk_size: Maximum chunk size in characters
        skip_existing: Skip already indexed files
        extensions: List of extensions to index (None = all supported)

    Returns:
        Dictionary with indexing statistics
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

    store = PDFVectorStore(persist_dir)

    # Determine which extensions to look for
    if extensions:
        search_extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
    else:
        search_extensions = get_supported_extensions()

    # Find document files
    doc_files = set()
    for ext in search_extensions:
        # Both lowercase and uppercase
        patterns = [
            os.path.join(doc_dir, f"*{ext}"),
            os.path.join(doc_dir, f"*{ext.upper()}"),
            os.path.join(doc_dir, f"**/*{ext}"),  # Recursive
            os.path.join(doc_dir, f"**/*{ext.upper()}"),
        ]
        for pattern in patterns:
            doc_files.update(glob.glob(pattern, recursive=True))

    doc_files = sorted(doc_files)

    if not doc_files:
        print(f"No supported documents found in {doc_dir}")
        print(f"Supported formats: {', '.join(search_extensions)}")
        return {"indexed": 0, "skipped": 0, "failed": 0}

    print(f"Found {len(doc_files)} documents in {doc_dir}")
    print("-" * 50)

    stats = {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0}

    for i, doc_path in enumerate(doc_files, 1):
        doc_id = os.path.basename(doc_path)
        file_type = get_file_type(doc_path)
        print(f"\n[{i}/{len(doc_files)}] Processing: {doc_id} ({file_type})")

        # Skip if already indexed
        if skip_existing and store.is_document_indexed(doc_id):
            print(f"  Already indexed, skipping...")
            stats["skipped"] += 1
            continue

        try:
            # Extract text
            text = extract_text(doc_path)
            if not text.strip():
                print(f"  No text extracted, skipping...")
                stats["skipped"] += 1
                continue

            # Chunk text
            chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)
            print(f"  Extracted {len(chunks)} chunks")

            # Add to store
            metadata = {
                "file_path": doc_path,
                "file_type": file_type
            }
            num_added = store.add_document(doc_id, chunks, metadata)
            stats["indexed"] += 1
            stats["total_chunks"] += num_added

        except Exception as e:
            print(f"  ERROR: {e}")
            stats["failed"] += 1

    print("\n" + "=" * 50)
    print("Indexing Complete!")
    print(f"  Indexed: {stats['indexed']} documents ({stats['total_chunks']} chunks)")
    print(f"  Skipped: {stats['skipped']} documents")
    print(f"  Failed:  {stats['failed']} documents")
    print(f"  Database: {persist_dir}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Index document files into vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Supported formats:
  {', '.join(get_supported_extensions())}

Examples:
  python index_documents.py ./docs
  python index_documents.py ./docs --ext pdf docx xlsx
  python index_documents.py ./docs --force
"""
    )
    parser.add_argument(
        "doc_dir",
        nargs="?",
        default="./docs",
        help="Directory containing documents (default: ./docs)"
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

    if not os.path.isdir(args.doc_dir):
        print(f"ERROR: Directory not found: {args.doc_dir}")
        sys.exit(1)

    index_document_directory(
        doc_dir=args.doc_dir,
        persist_dir=args.db,
        chunk_size=args.chunk_size,
        skip_existing=not args.force,
        extensions=args.ext
    )


if __name__ == "__main__":
    main()
