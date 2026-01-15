"""
Vector Store Module
ChromaDB wrapper with Ollama embeddings for storing and searching document chunks.
"""

import chromadb
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from tqdm import tqdm

# Default parallel workers for embedding requests
DEFAULT_EMBEDDING_WORKERS = 8


def get_embedding_workers() -> int:
    """Get the number of embedding workers (reads env var at call time)."""
    return int(os.environ.get("OLLAMA_WORKERS", DEFAULT_EMBEDDING_WORKERS))

# Lock for thread-safe ChromaDB operations
_chroma_lock = Lock()


class DocumentVectorStore:
    """Vector store using ChromaDB with Ollama embeddings."""

    def __init__(
        self,
        persist_dir: str = "./chroma_db",
        model: str = "nomic-embed-text",
        ollama_url: str = "http://localhost:11434"
    ):
        """
        Initialize the vector store.

        Args:
            persist_dir: Directory to persist ChromaDB data
            model: Ollama embedding model name
            ollama_url: Ollama API URL
        """
        self.model = model
        self.ollama_url = ollama_url
        self.persist_dir = persist_dir

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

    def _get_single_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text from Ollama."""
        # Truncate text if too long (nomic-embed-text has ~8k token limit)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]

        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.exceptions.RequestException as e:
            # Return None on failure, handle in caller
            print(f"    Warning: Embedding failed for chunk ({len(text)} chars): {e}")
            return None

    def _get_embeddings_parallel(
        self,
        texts: list[str],
        max_workers: int = None,
        show_progress: bool = True
    ) -> list[list[float]]:
        """Get embeddings for multiple texts in parallel with progress bar."""
        if max_workers is None:
            max_workers = get_embedding_workers()

        embeddings = [None] * len(texts)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._get_single_embedding, text): i
                      for i, text in enumerate(texts)}

            iterator = as_completed(futures)
            if show_progress:
                iterator = tqdm(iterator, total=len(texts), desc="    Embedding",
                               unit="chunk", leave=False)

            for future in iterator:
                idx = futures[future]
                embeddings[idx] = future.result()

        return embeddings

    def add_document(
        self,
        doc_id: str,
        chunks: list[str],
        metadata: dict = None,
        show_progress: bool = True
    ) -> tuple[int, float]:
        """
        Add document chunks to the vector store.

        Args:
            doc_id: Unique document identifier (usually filename)
            chunks: List of text chunks
            metadata: Optional metadata to attach to chunks
            show_progress: Show progress bar during embedding

        Returns:
            Tuple of (number of chunks added, time taken in seconds)
        """
        if not chunks:
            return 0, 0.0

        start_time = time.time()
        embeddings = self._get_embeddings_parallel(chunks, show_progress=show_progress)

        # Filter out failed embeddings (None values)
        valid_data = [
            (chunk, emb, i)
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
            if emb is not None
        ]

        if not valid_data:
            elapsed = time.time() - start_time
            return 0, elapsed

        valid_chunks = [d[0] for d in valid_data]
        valid_embeddings = [d[1] for d in valid_data]
        valid_indices = [d[2] for d in valid_data]

        ids = [f"{doc_id}_chunk_{i}" for i in valid_indices]
        metadatas = [
            {"source": doc_id, "chunk_index": i, **(metadata or {})}
            for i in valid_indices
        ]

        # ChromaDB has a max batch size limit (~5461), so batch inserts
        # Use lock for thread-safe writes when parallel document processing is enabled
        BATCH_SIZE = 5000
        total_items = len(ids)

        with _chroma_lock:
            for batch_start in range(0, total_items, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_items)
                self.collection.add(
                    ids=ids[batch_start:batch_end],
                    embeddings=valid_embeddings[batch_start:batch_end],
                    documents=valid_chunks[batch_start:batch_end],
                    metadatas=metadatas[batch_start:batch_end]
                )
                if total_items > BATCH_SIZE and show_progress:
                    print(f"    Stored batch {batch_start//BATCH_SIZE + 1}/{(total_items + BATCH_SIZE - 1)//BATCH_SIZE}")

        elapsed = time.time() - start_time
        return len(valid_chunks), elapsed

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Search for relevant chunks.

        Args:
            query: Search query
            n_results: Number of results to return

        Returns:
            List of results with text, source, and score
        """
        query_embedding = [self._get_single_embedding(query)]

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {
                "text": doc,
                "source": meta["source"],
                "chunk_index": meta["chunk_index"],
                "score": round(1 - dist, 4)  # Convert distance to similarity
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]

    def is_document_indexed(self, doc_id: str) -> bool:
        """Check if a document is already indexed."""
        with _chroma_lock:
            existing = self.collection.get(where={"source": doc_id})
            return len(existing["ids"]) > 0

    def get_document_chunks(self, doc_id: str) -> list[dict]:
        """Get all chunks for a specific document."""
        with _chroma_lock:
            results = self.collection.get(where={"source": doc_id})
            return [
                {"id": id, "text": doc, "metadata": meta}
                for id, doc, meta in zip(
                    results["ids"],
                    results["documents"],
                    results["metadatas"]
                )
            ]

    def remove_document(self, doc_id: str) -> int:
        """
        Remove a document from the index.

        Args:
            doc_id: Document identifier to remove

        Returns:
            Number of chunks removed
        """
        with _chroma_lock:
            existing = self.collection.get(where={"source": doc_id})
            if existing["ids"]:
                # Batch deletions to avoid ChromaDB limits
                BATCH_SIZE = 5000
                ids_to_delete = existing["ids"]
                total_ids = len(ids_to_delete)

                for batch_start in range(0, total_ids, BATCH_SIZE):
                    batch_end = min(batch_start + BATCH_SIZE, total_ids)
                    self.collection.delete(ids=ids_to_delete[batch_start:batch_end])

                print(f"Removed '{doc_id}' ({total_ids} chunks)")
                return total_ids
            else:
                print(f"'{doc_id}' not found in index")
                return 0

    def rename_document(self, old_doc_id: str, new_doc_id: str) -> int:
        """
        Rename a document in the index without re-embedding.

        Updates chunk IDs and metadata source field.

        Args:
            old_doc_id: Current document identifier
            new_doc_id: New document identifier

        Returns:
            Number of chunks renamed, or 0 if failed
        """
        with _chroma_lock:
            # Check if old doc exists
            existing = self.collection.get(
                where={"source": old_doc_id},
                include=["embeddings", "documents", "metadatas"]
            )

            if not existing["ids"]:
                print(f"'{old_doc_id}' not found in index")
                return 0

            # Check if new name already exists
            conflict = self.collection.get(where={"source": new_doc_id})
            if conflict["ids"]:
                print(f"'{new_doc_id}' already exists in index")
                return 0

            old_ids = existing["ids"]
            embeddings = existing["embeddings"]
            documents = existing["documents"]
            metadatas = existing["metadatas"]

            # Create new IDs and update metadata
            new_ids = []
            new_metadatas = []
            for old_id, meta in zip(old_ids, metadatas):
                chunk_idx = meta["chunk_index"]
                new_ids.append(f"{new_doc_id}_chunk_{chunk_idx}")
                new_meta = {**meta, "source": new_doc_id}
                new_metadatas.append(new_meta)

            # Batch operations to avoid limits
            BATCH_SIZE = 5000
            total_items = len(old_ids)

            # Delete old entries
            for batch_start in range(0, total_items, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_items)
                self.collection.delete(ids=old_ids[batch_start:batch_end])

            # Add with new IDs (preserving embeddings)
            for batch_start in range(0, total_items, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_items)
                self.collection.add(
                    ids=new_ids[batch_start:batch_end],
                    embeddings=embeddings[batch_start:batch_end],
                    documents=documents[batch_start:batch_end],
                    metadatas=new_metadatas[batch_start:batch_end]
                )

            print(f"Renamed '{old_doc_id}' -> '{new_doc_id}' ({total_items} chunks)")
            return total_items

    def list_documents(self) -> dict[str, int]:
        """
        List all indexed documents with chunk counts.

        Returns:
            Dictionary mapping document names to chunk counts
        """
        all_docs = self.collection.get()
        sources = {}
        for meta in all_docs["metadatas"]:
            src = meta["source"]
            sources[src] = sources.get(src, 0) + 1
        return sources

    def get_stats(self) -> dict:
        """Get index statistics."""
        docs = self.list_documents()
        total_chunks = sum(docs.values())
        return {
            "total_documents": len(docs),
            "total_chunks": total_chunks,
            "persist_dir": self.persist_dir,
            "model": self.model
        }


def check_ollama_connection(url: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running and accessible."""
    try:
        response = requests.get(f"{url}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


# Backward compatibility alias
PDFVectorStore = DocumentVectorStore


def check_model_available(model: str, url: str = "http://localhost:11434") -> bool:
    """Check if a specific model is available in Ollama."""
    try:
        response = requests.get(f"{url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return any(m["name"].startswith(model) for m in models)
        return False
    except requests.exceptions.RequestException:
        return False


if __name__ == "__main__":
    # Test the vector store
    print("Checking Ollama connection...")

    if not check_ollama_connection():
        print("ERROR: Ollama is not running!")
        print("Start Ollama with: ollama serve")
        exit(1)

    if not check_model_available("nomic-embed-text"):
        print("ERROR: nomic-embed-text model not found!")
        print("Pull it with: ollama pull nomic-embed-text")
        exit(1)

    print("Ollama is ready!")

    # Test embedding
    store = DocumentVectorStore("./test_chroma_db")

    test_chunks = [
        "This is a test document about machine learning.",
        "Python is a popular programming language.",
        "Vector databases store embeddings for semantic search."
    ]

    store.add_document("test_doc.pdf", test_chunks)

    results = store.search("What programming languages are mentioned?")
    print("\nSearch results:")
    for r in results:
        print(f"  [{r['score']}] {r['source']}: {r['text'][:50]}...")

    print("\nStats:", store.get_stats())

    # Cleanup test
    store.remove_document("test_doc.pdf")
