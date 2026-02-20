"""
Structured Data Types
Dataclasses for search results, indexing results, and index statistics.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """A single search result from the vector store."""
    text: str
    source: str
    chunk_index: int
    score: float

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "score": self.score,
        }


@dataclass
class IndexingResult:
    """Result of indexing a single document."""
    success: bool
    doc_id: str
    message: str
    elapsed_seconds: float = 0.0
    num_chunks: int = 0
    engine: str = "library"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "success": self.success,
            "doc_id": self.doc_id,
            "message": self.message,
            "elapsed_seconds": self.elapsed_seconds,
            "num_chunks": self.num_chunks,
            "engine": self.engine,
        }
        if self.error is not None:
            d["error"] = self.error
        return d


@dataclass
class IndexStats:
    """Statistics about the vector index."""
    total_documents: int
    total_chunks: int
    persist_dir: str
    model: str

    def to_dict(self) -> dict:
        return {
            "total_documents": self.total_documents,
            "total_chunks": self.total_chunks,
            "persist_dir": self.persist_dir,
            "model": self.model,
        }
