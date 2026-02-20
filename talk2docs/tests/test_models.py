"""Tests for structured data models."""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import SearchResult, IndexingResult, IndexStats


class TestSearchResult:
    def test_construction(self):
        r = SearchResult(text="hello world", source="doc.pdf", chunk_index=0, score=0.95)
        assert r.text == "hello world"
        assert r.source == "doc.pdf"
        assert r.chunk_index == 0
        assert r.score == 0.95

    def test_to_dict(self):
        r = SearchResult(text="t", source="s", chunk_index=1, score=0.8)
        d = r.to_dict()
        assert d == {"text": "t", "source": "s", "chunk_index": 1, "score": 0.8}

    def test_to_dict_roundtrip(self):
        r = SearchResult(text="abc", source="f.txt", chunk_index=3, score=0.5)
        d = r.to_dict()
        r2 = SearchResult(**d)
        assert r == r2


class TestIndexingResult:
    def test_construction_success(self):
        r = IndexingResult(
            success=True, doc_id="file.pdf",
            message="Indexed 10 chunks", elapsed_seconds=1.5,
            num_chunks=10, engine="library",
        )
        assert r.success is True
        assert r.doc_id == "file.pdf"
        assert r.num_chunks == 10
        assert r.engine == "library"
        assert r.error is None

    def test_construction_failure(self):
        r = IndexingResult(
            success=False, doc_id="bad.pdf",
            message="Error: file not found",
            error="file not found",
        )
        assert r.success is False
        assert r.error == "file not found"

    def test_defaults(self):
        r = IndexingResult(success=True, doc_id="x", message="ok")
        assert r.elapsed_seconds == 0.0
        assert r.num_chunks == 0
        assert r.engine == "library"
        assert r.error is None

    def test_to_dict_includes_error_only_when_set(self):
        r_ok = IndexingResult(success=True, doc_id="x", message="ok")
        assert "error" not in r_ok.to_dict()

        r_err = IndexingResult(success=False, doc_id="x", message="fail", error="boom")
        assert r_err.to_dict()["error"] == "boom"


class TestIndexStats:
    def test_construction(self):
        s = IndexStats(total_documents=5, total_chunks=100, persist_dir="./db", model="nomic")
        assert s.total_documents == 5
        assert s.total_chunks == 100
        assert s.persist_dir == "./db"
        assert s.model == "nomic"

    def test_to_dict(self):
        s = IndexStats(total_documents=2, total_chunks=50, persist_dir="/tmp/db", model="m")
        d = s.to_dict()
        assert d == {
            "total_documents": 2,
            "total_chunks": 50,
            "persist_dir": "/tmp/db",
            "model": "m",
        }
