#!/usr/bin/env python3
"""
Bulk PDF Indexing Script
Index all PDFs in a directory to the vector store.
"""

import glob
import os
import sys
from pathlib import Path

from pdf_extractor import extract_text_from_pdf
from chunker import chunk_by_paragraphs
from vector_store import PDFVectorStore, check_ollama_connection, check_model_available


def index_pdf_directory(
    pdf_dir: str,
    persist_dir: str = "./chroma_db",
    chunk_size: int = 500,
    skip_existing: bool = True
) -> dict:
    """
    Index all PDFs in a directory.

    Args:
        pdf_dir: Directory containing PDF files
        persist_dir: Directory to persist vector database
        chunk_size: Maximum chunk size in characters
        skip_existing: Skip already indexed files

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

    # Find PDF files
    pdf_patterns = [
        os.path.join(pdf_dir, "*.pdf"),
        os.path.join(pdf_dir, "*.PDF"),
        os.path.join(pdf_dir, "**/*.pdf"),  # Recursive
        os.path.join(pdf_dir, "**/*.PDF"),
    ]

    pdf_files = set()
    for pattern in pdf_patterns:
        pdf_files.update(glob.glob(pattern, recursive=True))

    pdf_files = sorted(pdf_files)

    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        return {"indexed": 0, "skipped": 0, "failed": 0}

    print(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    print("-" * 50)

    stats = {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0}

    for i, pdf_path in enumerate(pdf_files, 1):
        doc_id = os.path.basename(pdf_path)
        print(f"\n[{i}/{len(pdf_files)}] Processing: {doc_id}")

        # Skip if already indexed
        if skip_existing and store.is_document_indexed(doc_id):
            print(f"  Already indexed, skipping...")
            stats["skipped"] += 1
            continue

        try:
            # Extract text
            text = extract_text_from_pdf(pdf_path)
            if not text.strip():
                print(f"  No text extracted, skipping...")
                stats["skipped"] += 1
                continue

            # Chunk text
            chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)
            print(f"  Extracted {len(chunks)} chunks")

            # Add to store
            metadata = {"file_path": pdf_path}
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
        description="Index PDF files into vector database"
    )
    parser.add_argument(
        "pdf_dir",
        nargs="?",
        default="./pdfs",
        help="Directory containing PDF files (default: ./pdfs)"
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

    args = parser.parse_args()

    if not os.path.isdir(args.pdf_dir):
        print(f"ERROR: Directory not found: {args.pdf_dir}")
        sys.exit(1)

    index_pdf_directory(
        pdf_dir=args.pdf_dir,
        persist_dir=args.db,
        chunk_size=args.chunk_size,
        skip_existing=not args.force
    )


if __name__ == "__main__":
    main()
