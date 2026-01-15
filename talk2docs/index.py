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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from document_extractor import extract_text, is_supported, get_supported_extensions, get_file_type
from chunker import chunk_by_paragraphs
from vector_store import DocumentVectorStore, check_ollama_connection, check_model_available

# Lock for thread-safe printing
print_lock = Lock()


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
    force: bool = False,
    quiet: bool = False
) -> tuple[bool, str, float, int]:
    """
    Index a single file to the vector store.

    Args:
        file_path: Path to the file
        store: Vector store instance
        chunk_size: Maximum chunk size
        force: Re-index if already exists
        quiet: Suppress progress output (for parallel processing)

    Returns:
        Tuple of (success, status_message, time_taken, num_chunks)
    """
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}", 0.0, 0

    if not is_supported(file_path):
        return False, f"Unsupported format: {Path(file_path).suffix}", 0.0, 0

    doc_id = os.path.basename(file_path)
    file_type = get_file_type(file_path)

    # Check if already indexed
    if store.is_document_indexed(doc_id):
        if force:
            if not quiet:
                with print_lock:
                    print(f"  Re-indexing: {doc_id}")
            store.remove_document(doc_id)
        else:
            chunks = store.get_document_chunks(doc_id)
            return False, f"Already indexed ({len(chunks)} chunks). Use --force to re-index.", 0.0, 0

    try:
        start_time = time.time()

        # Extract text
        text = extract_text(file_path)
        if not text.strip():
            return False, "No text extracted", 0.0, 0

        # Chunk text
        chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)

        # Add to store (quiet mode disables per-chunk progress)
        metadata = {
            "file_path": os.path.abspath(file_path),
            "file_type": file_type
        }
        num_added, embed_time = store.add_document(doc_id, chunks, metadata, show_progress=not quiet)
        total_time = time.time() - start_time
        return True, f"Indexed {num_added} chunks in {format_time(total_time)}", total_time, num_added

    except Exception as e:
        return False, f"Error: {e}", 0.0, 0


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
    extensions: list[str] | None = None,
    parallel_docs: int = 1
) -> dict:
    """
    Index files or directories to the vector store.

    Args:
        paths: List of file or directory paths
        persist_dir: Vector database directory
        chunk_size: Maximum chunk size in characters
        force: Re-index existing documents
        extensions: Only index specific extensions (for directories)
        parallel_docs: Number of documents to process in parallel

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
    if parallel_docs > 1:
        print(f"Parallel document processing: {parallel_docs} workers")
    print("-" * 50)

    stats = {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0, "total_time": 0.0}
    overall_start = time.time()

    if parallel_docs > 1:
        # Parallel document processing
        # Note: When processing docs in parallel, we use sequential embedding per doc
        # to avoid nested thread pool issues. Total concurrency = parallel_docs.
        from tqdm import tqdm
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        # Force sequential embedding when parallel doc processing is on
        original_workers = os.environ.get("OLLAMA_WORKERS")
        os.environ["OLLAMA_WORKERS"] = "1"

        def process_file(file_info):
            idx, file_path = file_info
            doc_name = os.path.basename(file_path)
            try:
                success, message, elapsed, num_chunks = index_file(
                    file_path, store, chunk_size, force, quiet=True
                )
                return idx, file_path, doc_name, success, message, elapsed, num_chunks
            except Exception as e:
                import traceback
                return idx, file_path, doc_name, False, f"Error: {e}\n{traceback.format_exc()}", 0.0, 0

        try:
            with ThreadPoolExecutor(max_workers=parallel_docs) as executor:
                futures = {executor.submit(process_file, (i, f)): (i, f)
                          for i, f in enumerate(unique_files, 1)}

                with tqdm(total=len(unique_files), desc="Indexing", unit="doc") as pbar:
                    for future in as_completed(futures):
                        try:
                            _, file_path, doc_name, success, message, elapsed, num_chunks = future.result(timeout=3600)
                        except FuturesTimeoutError:
                            _, file_path = futures[future]
                            doc_name = os.path.basename(file_path)
                            success, message, elapsed, num_chunks = False, "Timeout (>1hr)", 0.0, 0
                        except Exception as e:
                            _, file_path = futures[future]
                            doc_name = os.path.basename(file_path)
                            success, message, elapsed, num_chunks = False, f"Error: {e}", 0.0, 0

                        if success:
                            stats["indexed"] += 1
                            stats["total_time"] += elapsed
                            stats["total_chunks"] += num_chunks
                            with print_lock:
                                tqdm.write(f"  ✓ {doc_name}: {num_chunks} chunks in {format_time(elapsed)}")
                        elif "Already indexed" in message:
                            stats["skipped"] += 1
                            with print_lock:
                                tqdm.write(f"  → {doc_name}: {message}")
                        else:
                            stats["failed"] += 1
                            with print_lock:
                                tqdm.write(f"  ✗ {doc_name}: {message}")

                        pbar.update(1)
        finally:
            # Restore original workers setting
            if original_workers is not None:
                os.environ["OLLAMA_WORKERS"] = original_workers
            elif "OLLAMA_WORKERS" in os.environ:
                del os.environ["OLLAMA_WORKERS"]
    else:
        # Sequential processing (original behavior)
        for i, file_path in enumerate(unique_files, 1):
            doc_name = os.path.basename(file_path)
            file_type = get_file_type(file_path)
            print(f"\n[{i}/{len(unique_files)}] {doc_name} ({file_type})")

            success, message, elapsed, num_chunks = index_file(file_path, store, chunk_size, force)

            if success:
                print(f"  ✓ {message}")
                stats["indexed"] += 1
                stats["total_time"] += elapsed
                stats["total_chunks"] += num_chunks
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

Parallelism (for faster indexing):
  python index.py ./docs -w 16              # 16 embedding workers (default: 8)
  python index.py ./docs -p 4               # 4 documents in parallel
  python index.py ./docs -p 4 -w 4          # 4 docs × 4 workers = 16 total requests

Environment variables:
  OLLAMA_WORKERS=16 python index.py ./docs  # Set default embedding workers
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
    parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=1,
        help="Number of documents to process in parallel (default: 1, sequential)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of embedding workers per document (default: 8, or OLLAMA_WORKERS env)"
    )

    args = parser.parse_args()

    # Set embedding workers if specified
    if args.workers:
        os.environ["OLLAMA_WORKERS"] = str(args.workers)

    index(
        paths=args.paths,
        persist_dir=args.db,
        chunk_size=args.chunk_size,
        force=args.force,
        extensions=args.ext,
        parallel_docs=args.parallel
    )


if __name__ == "__main__":
    main()
