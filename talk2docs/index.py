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
    python index.py --engine tiparse file.pdf   # Use TiParse LLM extraction
"""

import glob
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from document_extractor import extract_text, is_supported, get_supported_extensions, get_file_type
from chunker import chunk_by_paragraphs
from config import DEFAULT_CHUNK_SIZE, DEFAULT_PERSIST_DIR, CHROMA_BATCH_SIZE
from extraction_engine import create_engine
from models import IndexingResult
from vector_store import DocumentVectorStore, BatchedDocumentVectorStore, check_ollama_connection, check_model_available

logger = logging.getLogger(__name__)

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
    store,  # DocumentVectorStore or BatchedDocumentVectorStore
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force: bool = False,
    quiet: bool = False,
    engine=None,
) -> IndexingResult:
    """
    Index a single file to the vector store.

    Args:
        file_path: Path to the file
        store: Vector store instance
        chunk_size: Maximum chunk size
        force: Re-index if already exists
        quiet: Suppress progress output (for parallel processing)
        engine: Extraction engine (LibraryEngine or TiParseEngine). None = default library.

    Returns:
        IndexingResult with success status, message, timing, and chunk count.
    """
    doc_id = os.path.basename(file_path)
    engine_name = getattr(engine, "name", "library") if engine else "library"

    if not os.path.isfile(file_path):
        return IndexingResult(
            success=False, doc_id=doc_id,
            message=f"File not found: {file_path}", engine=engine_name,
        )

    if not is_supported(file_path):
        return IndexingResult(
            success=False, doc_id=doc_id,
            message=f"Unsupported format: {Path(file_path).suffix}", engine=engine_name,
        )

    file_type = get_file_type(file_path)

    # Check if already indexed
    if store.is_document_indexed(doc_id):
        if force:
            if not quiet:
                with print_lock:
                    logger.info("  Re-indexing: %s", doc_id)
            store.remove_document(doc_id)
        else:
            chunks = store.get_document_chunks(doc_id)
            return IndexingResult(
                success=False, doc_id=doc_id,
                message=f"Already indexed ({len(chunks)} chunks). Use --force to re-index.",
                engine=engine_name,
            )

    try:
        start_time = time.time()

        if engine is not None:
            # Use the provided extraction engine
            result = engine.extract_and_chunk(file_path)
            chunks = result.chunks
            metadata = result.metadata
            engine_name = result.engine  # may differ if fallback occurred
        else:
            # Default: library-based extraction
            text = extract_text(file_path)
            if not text.strip():
                return IndexingResult(
                    success=False, doc_id=doc_id,
                    message="No text extracted", engine=engine_name,
                )
            chunks = chunk_by_paragraphs(text, max_chunk_size=chunk_size)
            metadata = {
                "file_path": os.path.abspath(file_path),
                "file_type": file_type,
            }

        if not chunks:
            return IndexingResult(
                success=False, doc_id=doc_id,
                message="No text extracted", engine=engine_name,
            )

        # Add to store (quiet mode disables per-chunk progress)
        num_added, embed_time = store.add_document(doc_id, chunks, metadata, show_progress=not quiet)
        total_time = time.time() - start_time
        return IndexingResult(
            success=True, doc_id=doc_id,
            message=f"Indexed {num_added} chunks in {format_time(total_time)}",
            elapsed_seconds=total_time, num_chunks=num_added, engine=engine_name,
        )

    except Exception as e:
        return IndexingResult(
            success=False, doc_id=doc_id,
            message=f"Error: {e}", engine=engine_name, error=str(e),
        )


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
    persist_dir: str = DEFAULT_PERSIST_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force: bool = False,
    extensions: list[str] | None = None,
    parallel_docs: int = 1,
    batch_mode: bool = False,
    batch_size: int = CHROMA_BATCH_SIZE,
    engine_name: str = "library",
    tiparse_model: str | None = None,
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
        batch_mode: Batch chunks and embed only after reaching batch_size (more efficient)
        batch_size: Number of chunks to accumulate before embedding
        engine_name: Extraction engine name ("library" or "tiparse")
        tiparse_model: Model name for TiParse engine (optional)

    Returns:
        Statistics dictionary
    """
    # Check Ollama
    if not check_ollama_connection():
        logger.error("ERROR: Ollama is not running!")
        logger.error("Start Ollama with: ollama serve")
        sys.exit(1)

    if not check_model_available("nomic-embed-text"):
        logger.error("ERROR: nomic-embed-text model not found!")
        logger.error("Pull it with: ollama pull nomic-embed-text")
        sys.exit(1)

    # Create extraction engine
    engine_kwargs = {"chunk_size": chunk_size}
    if engine_name == "tiparse" and tiparse_model:
        engine_kwargs["model"] = tiparse_model
        engine_kwargs["library_chunk_size"] = chunk_size
    engine = create_engine(engine_name, **engine_kwargs)
    logger.info("Extraction engine: %s", engine.name)

    # Use batched store for more efficient embedding when processing many documents
    if batch_mode:
        store = BatchedDocumentVectorStore(persist_dir, batch_size=batch_size)
        logger.info("Batched embedding mode: will embed every %d chunks", batch_size)
    else:
        store = DocumentVectorStore(persist_dir)

    # Collect all files to index
    all_files = []
    for path in paths:
        files = find_documents(path, extensions)
        if not files:
            if os.path.isfile(path):
                logger.warning("Unsupported file: %s", path)
            elif os.path.isdir(path):
                logger.warning("No supported documents in: %s", path)
            else:
                logger.warning("Path not found: %s", path)
        all_files.extend(files)

    # Remove duplicates, preserve order
    seen = set()
    unique_files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    if not unique_files:
        logger.info("\nNo documents to index.")
        logger.info("Supported formats: %s", ', '.join(get_supported_extensions()))
        return {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0}

    logger.info("Found %d document(s) to process", len(unique_files))
    if parallel_docs > 1:
        logger.info("Parallel document processing: %d workers", parallel_docs)
    logger.info("-" * 50)

    stats = {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0, "total_time": 0.0}
    overall_start = time.time()

    if parallel_docs > 1:
        # Parallel document processing
        from tqdm import tqdm
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        # Force sequential embedding when parallel doc processing is on
        original_workers = os.environ.get("OLLAMA_WORKERS")
        os.environ["OLLAMA_WORKERS"] = "1"

        def process_file(file_info):
            idx, file_path = file_info
            doc_name = os.path.basename(file_path)
            try:
                result = index_file(
                    file_path, store, chunk_size, force, quiet=True, engine=engine,
                )
                return idx, file_path, doc_name, result
            except Exception as e:
                import traceback
                return idx, file_path, doc_name, IndexingResult(
                    success=False, doc_id=doc_name,
                    message=f"Error: {e}\n{traceback.format_exc()}",
                    engine=engine.name, error=str(e),
                )

        try:
            with ThreadPoolExecutor(max_workers=parallel_docs) as executor:
                futures = {executor.submit(process_file, (i, f)): (i, f)
                          for i, f in enumerate(unique_files, 1)}

                with tqdm(total=len(unique_files), desc="Indexing", unit="doc") as pbar:
                    for future in as_completed(futures):
                        try:
                            _, file_path, doc_name, result = future.result(timeout=3600)
                        except FuturesTimeoutError:
                            _, file_path = futures[future]
                            doc_name = os.path.basename(file_path)
                            result = IndexingResult(
                                success=False, doc_id=doc_name,
                                message="Timeout (>1hr)", engine=engine.name,
                            )
                        except Exception as e:
                            _, file_path = futures[future]
                            doc_name = os.path.basename(file_path)
                            result = IndexingResult(
                                success=False, doc_id=doc_name,
                                message=f"Error: {e}", engine=engine.name, error=str(e),
                            )

                        if result.success:
                            stats["indexed"] += 1
                            stats["total_time"] += result.elapsed_seconds
                            stats["total_chunks"] += result.num_chunks
                            with print_lock:
                                tqdm.write(f"  \u2713 {doc_name}: {result.num_chunks} chunks in {format_time(result.elapsed_seconds)}")
                        elif "Already indexed" in result.message:
                            stats["skipped"] += 1
                            with print_lock:
                                tqdm.write(f"  \u2192 {doc_name}: {result.message}")
                        else:
                            stats["failed"] += 1
                            with print_lock:
                                tqdm.write(f"  \u2717 {doc_name}: {result.message}")

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
            logger.info("\n[%d/%d] %s (%s)", i, len(unique_files), doc_name, file_type)

            result = index_file(file_path, store, chunk_size, force, engine=engine)

            if result.success:
                logger.info("  \u2713 %s", result.message)
                stats["indexed"] += 1
                stats["total_time"] += result.elapsed_seconds
                stats["total_chunks"] += result.num_chunks
            elif "Already indexed" in result.message:
                logger.info("  \u2192 %s", result.message)
                stats["skipped"] += 1
            else:
                logger.info("  \u2717 %s", result.message)
                stats["failed"] += 1

    overall_time = time.time() - overall_start

    # Flush any remaining chunks in batched mode
    if batch_mode and hasattr(store, 'flush'):
        pending = store.get_pending_count()
        if pending > 0:
            logger.info("\nFlushing final %d chunks...", pending)
            flushed, flush_time = store.flush()
            stats["total_chunks"] += flushed
            stats["total_time"] += flush_time

    overall_time = time.time() - overall_start

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Indexing Complete!")
    logger.info("  Indexed: %d documents (%d chunks)", stats['indexed'], stats['total_chunks'])
    logger.info("  Skipped: %d documents", stats['skipped'])
    logger.info("  Failed:  %d documents", stats['failed'])
    logger.info("  Time:    %s", format_time(overall_time))
    logger.info("  Database: %s", persist_dir)
    logger.info("  Engine:  %s", engine.name)
    if batch_mode:
        batch_stats = store.get_stats()
        logger.info("  Batches: %d embedding batches", batch_stats['flush_count'])

    return stats


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
  python index.py --engine tiparse file.pdf # Use TiParse LLM extraction

Parallelism (for faster indexing):
  python index.py ./docs -w 16              # 16 embedding workers (default: 8)
  python index.py ./docs -p 4               # 4 documents in parallel
  python index.py ./docs -p 4 -w 4          # 4 docs x 4 workers = 16 total requests

Batched embedding (more efficient for large document sets):
  python index.py ./docs --batch            # Batch mode (embed every 5000 chunks)
  python index.py ./docs -b -B 10000        # Custom batch size of 10000 chunks
  python index.py ./docs -b -w 16           # Batch mode with 16 workers

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
        default=DEFAULT_PERSIST_DIR,
        help=f"Vector database directory (default: {DEFAULT_PERSIST_DIR})"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Maximum chunk size in characters (default: {DEFAULT_CHUNK_SIZE})"
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
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Enable batched embedding mode (accumulate chunks, embed in batches)"
    )
    parser.add_argument(
        "--batch-size", "-B",
        type=int,
        default=CHROMA_BATCH_SIZE,
        help=f"Number of chunks to accumulate before embedding (default: {CHROMA_BATCH_SIZE})"
    )
    parser.add_argument(
        "--engine",
        choices=["library", "tiparse"],
        default="library",
        help="Extraction engine (default: library)"
    )
    parser.add_argument(
        "--tiparse-model",
        default=None,
        help="Model name for TiParse engine (optional)"
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
        parallel_docs=args.parallel,
        batch_mode=args.batch,
        batch_size=args.batch_size,
        engine_name=args.engine,
        tiparse_model=args.tiparse_model,
    )


if __name__ == "__main__":
    main()
