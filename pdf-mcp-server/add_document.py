#!/usr/bin/env python3
"""
Incremental Document Indexing Script
Add individual document files to an existing index.

Supported formats: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML
"""

import os
import sys
from pathlib import Path

from document_extractor import extract_text, is_supported, get_supported_extensions, get_file_type
from chunker import chunk_by_paragraphs
from vector_store import PDFVectorStore, check_ollama_connection, check_model_available


def add_single_document(
    doc_path: str,
    persist_dir: str = "./chroma_db",
    chunk_size: int = 1000,
    force: bool = False
) -> bool:
    """
    Add a single document to the existing index.

    Args:
        doc_path: Path to the document file
        persist_dir: Vector database directory
        chunk_size: Maximum chunk size
        force: Re-index if already exists

    Returns:
        True if successfully indexed, False otherwise
    """
    # Check if file type is supported
    if not is_supported(doc_path):
        print(f"Unsupported file type: {Path(doc_path).suffix}")
        print(f"Supported formats: {', '.join(get_supported_extensions())}")
        return False

    store = PDFVectorStore(persist_dir)
    doc_id = os.path.basename(doc_path)
    file_type = get_file_type(doc_path)

    # Check if already indexed
    if store.is_document_indexed(doc_id):
        if force:
            print(f"'{doc_id}' exists, removing for re-index...")
            store.remove_document(doc_id)
        else:
            print(f"'{doc_id}' already indexed ({len(store.get_document_chunks(doc_id))} chunks). Use --force to re-index.")
            return False

    try:
        print(f"Indexing: {doc_path} ({file_type})")

        # Extract text
        text = extract_text(doc_path)
        if not text.strip():
            print(f"  No text extracted from '{doc_id}'")
            return False

        # Chunk text
        chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)
        print(f"  Extracted {len(chunks)} chunks")

        # Add to store
        metadata = {
            "file_path": os.path.abspath(doc_path),
            "file_type": file_type
        }
        store.add_document(doc_id, chunks, metadata)
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def add_multiple_documents(
    doc_paths: list[str],
    persist_dir: str = "./chroma_db",
    chunk_size: int = 1000,
    force: bool = False
) -> dict:
    """
    Add multiple documents to existing index.

    Args:
        doc_paths: List of document file paths
        persist_dir: Vector database directory
        chunk_size: Maximum chunk size
        force: Re-index existing documents

    Returns:
        Statistics dictionary
    """
    stats = {"added": 0, "skipped": 0, "failed": 0}

    for path in doc_paths:
        if not os.path.isfile(path):
            print(f"File not found: {path}")
            stats["failed"] += 1
            continue

        result = add_single_document(path, persist_dir, chunk_size, force)
        if result:
            stats["added"] += 1
        elif result is False:
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

    print(f"\nTotal: Added {stats['added']}, Skipped {stats['skipped']}, Failed {stats['failed']}")
    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Add document files to existing vector index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Supported formats:
  {', '.join(get_supported_extensions())}

Examples:
  python add_document.py document.pdf
  python add_document.py report.docx data.xlsx presentation.pptx
  python add_document.py --force updated_doc.pdf
"""
    )
    parser.add_argument(
        "documents",
        nargs="+",
        help="Document file(s) to add"
    )
    parser.add_argument(
        "--db", "-d",
        default="./chroma_db",
        help="Vector database directory (default: ./chroma_db)"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=1000,
        help="Maximum chunk size in characters (default: 1000)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-index existing documents"
    )

    args = parser.parse_args()

    # Check Ollama
    if not check_ollama_connection():
        print("ERROR: Ollama is not running!")
        print("Start Ollama with: ollama serve")
        sys.exit(1)

    if not check_model_available("nomic-embed-text"):
        print("ERROR: nomic-embed-text model not found!")
        print("Pull it with: ollama pull nomic-embed-text")
        sys.exit(1)

    add_multiple_documents(
        doc_paths=args.documents,
        persist_dir=args.db,
        chunk_size=args.chunk_size,
        force=args.force
    )


if __name__ == "__main__":
    main()
