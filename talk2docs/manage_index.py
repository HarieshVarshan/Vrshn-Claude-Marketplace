#!/usr/bin/env python3
"""
Index Management Script
List, remove, and manage indexed documents.
"""

import os
import sys
import argparse

from vector_store import DocumentVectorStore


def list_documents(persist_dir: str = "./chroma_db"):
    """List all indexed documents."""
    store = DocumentVectorStore(persist_dir)
    docs = store.list_documents()

    if not docs:
        print("No documents indexed.")
        return

    print(f"{'Document':<50} {'Chunks':<10}")
    print("-" * 60)

    for doc, count in sorted(docs.items()):
        print(f"{doc:<50} {count:<10}")

    stats = store.get_stats()
    print("-" * 60)
    print(f"Total: {stats['total_documents']} documents, {stats['total_chunks']} chunks")
    print(f"Database: {persist_dir}")


def remove_document(doc_name: str, persist_dir: str = "./chroma_db"):
    """Remove a document from the index."""
    store = DocumentVectorStore(persist_dir)

    if not store.is_document_indexed(doc_name):
        print(f"'{doc_name}' not found in index")
        return False

    removed = store.remove_document(doc_name)
    return removed > 0


def rename_document(old_name: str, new_name: str, persist_dir: str = "./chroma_db"):
    """Rename a document in the index without re-embedding."""
    store = DocumentVectorStore(persist_dir)
    renamed = store.rename_document(old_name, new_name)
    return renamed > 0


def search_index(query: str, persist_dir: str = "./chroma_db", n_results: int = 5):
    """Search the index."""
    store = DocumentVectorStore(persist_dir)

    results = store.search(query, n_results)

    if not results:
        print("No results found.")
        return

    print(f"Search results for: '{query}'\n")
    print("=" * 70)

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['source']} (score: {r['score']})")
        print("-" * 70)
        text = r['text']
        # Truncate long results
        if len(text) > 500:
            text = text[:500] + "..."
        print(text)

    print("\n" + "=" * 70)


def show_stats(persist_dir: str = "./chroma_db"):
    """Show index statistics."""
    store = DocumentVectorStore(persist_dir)
    stats = store.get_stats()

    print("Index Statistics")
    print("-" * 30)
    print(f"Documents: {stats['total_documents']}")
    print(f"Chunks:    {stats['total_chunks']}")
    print(f"Model:     {stats['model']}")
    print(f"Database:  {stats['persist_dir']}")


def clear_index(persist_dir: str = "./chroma_db", confirm: bool = False):
    """Clear all documents from the index."""
    if not confirm:
        response = input("Are you sure you want to clear all documents? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return

    store = DocumentVectorStore(persist_dir)
    docs = store.list_documents()

    for doc_name in docs:
        store.remove_document(doc_name)

    print(f"Cleared {len(docs)} documents from index.")


def main():
    parser = argparse.ArgumentParser(
        description="Manage the document vector index"
    )
    parser.add_argument(
        "--db", "-d",
        default="./chroma_db",
        help="Vector database directory (default: ./chroma_db)"
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
