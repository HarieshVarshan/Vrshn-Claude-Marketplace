#!/usr/bin/env python3
"""
Index Management Script
List, remove, and manage indexed documents.
"""

import argparse
import logging

from config import DEFAULT_PERSIST_DIR
from vector_store import DocumentVectorStore

logger = logging.getLogger(__name__)


def list_documents(persist_dir: str = DEFAULT_PERSIST_DIR):
    """List all indexed documents."""
    store = DocumentVectorStore(persist_dir)
    docs = store.list_documents()

    if not docs:
        logger.info("No documents indexed.")
        return

    logger.info("%-50s %-10s", "Document", "Chunks")
    logger.info("-" * 60)

    for doc, count in sorted(docs.items()):
        logger.info("%-50s %-10d", doc, count)

    stats = store.get_stats()
    logger.info("-" * 60)
    logger.info("Total: %d documents, %d chunks", stats.total_documents, stats.total_chunks)
    logger.info("Database: %s", persist_dir)


def remove_document(doc_name: str, persist_dir: str = DEFAULT_PERSIST_DIR):
    """Remove a document from the index."""
    store = DocumentVectorStore(persist_dir)

    if not store.is_document_indexed(doc_name):
        logger.info("'%s' not found in index", doc_name)
        return False

    removed = store.remove_document(doc_name)
    return removed > 0


def rename_document(old_name: str, new_name: str, persist_dir: str = DEFAULT_PERSIST_DIR):
    """Rename a document in the index without re-embedding."""
    store = DocumentVectorStore(persist_dir)
    renamed = store.rename_document(old_name, new_name)
    return renamed > 0


def search_index(query: str, persist_dir: str = DEFAULT_PERSIST_DIR, n_results: int = 5):
    """Search the index."""
    store = DocumentVectorStore(persist_dir)

    results = store.search(query, n_results)

    if not results:
        logger.info("No results found.")
        return

    logger.info("Search results for: '%s'\n", query)
    logger.info("=" * 70)

    for i, r in enumerate(results, 1):
        logger.info("\n[%d] %s (score: %s)", i, r.source, r.score)
        logger.info("-" * 70)
        text = r.text
        if len(text) > 500:
            text = text[:500] + "..."
        logger.info(text)

    logger.info("\n" + "=" * 70)


def show_stats(persist_dir: str = DEFAULT_PERSIST_DIR):
    """Show index statistics."""
    store = DocumentVectorStore(persist_dir)
    stats = store.get_stats()

    logger.info("Index Statistics")
    logger.info("-" * 30)
    logger.info("Documents: %d", stats.total_documents)
    logger.info("Chunks:    %d", stats.total_chunks)
    logger.info("Model:     %s", stats.model)
    logger.info("Database:  %s", stats.persist_dir)


def clear_index(persist_dir: str = DEFAULT_PERSIST_DIR, confirm: bool = False):
    """Clear all documents from the index."""
    if not confirm:
        response = input("Are you sure you want to clear all documents? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Aborted.")
            return

    store = DocumentVectorStore(persist_dir)
    docs = store.list_documents()

    for doc_name in docs:
        store.remove_document(doc_name)

    logger.info("Cleared %d documents from index.", len(docs))


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Manage the document vector index"
    )
    parser.add_argument(
        "--db", "-d",
        default=DEFAULT_PERSIST_DIR,
        help=f"Vector database directory (default: {DEFAULT_PERSIST_DIR})"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    subparsers.add_parser("list", help="List all indexed documents")

    # remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a document")
    remove_parser.add_argument("document", help="Document name to remove")

    # rename command
    rename_parser = subparsers.add_parser("rename", help="Rename a document (no re-embedding)")
    rename_parser.add_argument("old_name", help="Current document name")
    rename_parser.add_argument("new_name", help="New document name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search the index")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("-n", type=int, default=5, help="Number of results")

    # stats command
    subparsers.add_parser("stats", help="Show index statistics")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all documents")
    clear_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    if args.command is None or args.command == "list":
        list_documents(args.db)
    elif args.command == "remove":
        remove_document(args.document, args.db)
    elif args.command == "rename":
        rename_document(args.old_name, args.new_name, args.db)
    elif args.command == "search":
        search_index(args.query, args.db, args.n)
    elif args.command == "stats":
        show_stats(args.db)
    elif args.command == "clear":
        clear_index(args.db, args.yes)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
