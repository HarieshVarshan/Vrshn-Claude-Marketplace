"""
Extraction Engine Abstraction
LibraryEngine wraps existing extractors; TiParseEngine uses LLM-powered extraction.
Auto-fallback from TiParse to library on unsupported formats or errors.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import TIPARSE_SUPPORTED_EXTENSIONS, TIPARSE_DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_SIZE

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of extracting and chunking a document."""
    chunks: list[str]
    engine: str
    metadata: dict = field(default_factory=dict)
    doc_summary: Optional[str] = None


class LibraryEngine:
    """Extraction engine using local libraries (PyMuPDF, python-docx, etc.)."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.chunk_size = chunk_size

    @property
    def name(self) -> str:
        return "library"

    def extract_and_chunk(self, file_path: str) -> ExtractionResult:
        """Extract text and chunk using local libraries."""
        from document_extractor import extract_text, get_file_type
        from chunker import chunk_by_paragraphs

        text = extract_text(file_path)
        if not text.strip():
            return ExtractionResult(chunks=[], engine=self.name)

        chunks = chunk_by_paragraphs(text, max_chunk_size=self.chunk_size)
        metadata = {
            "file_path": os.path.abspath(file_path),
            "file_type": get_file_type(file_path),
        }
        return ExtractionResult(chunks=chunks, engine=self.name, metadata=metadata)


class TiParseEngine:
    """Extraction engine using TiParse LLM-powered parsing."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        chunk_size: int = TIPARSE_DEFAULT_CHUNK_SIZE,
        library_chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.api_base = api_base or os.environ.get("OPENAI_BASE_URL")
        self.chunk_size = chunk_size
        self._library_fallback = LibraryEngine(chunk_size=library_chunk_size)

    @property
    def name(self) -> str:
        return "tiparse"

    def is_supported_native(self, file_path: str) -> bool:
        """Check if TiParse natively supports this file extension."""
        ext = Path(file_path).suffix.lower()
        return ext in TIPARSE_SUPPORTED_EXTENSIONS

    def extract_and_chunk(self, file_path: str) -> ExtractionResult:
        """Extract and chunk using TiParse, falling back to library on unsupported formats or errors."""
        if not self.is_supported_native(file_path):
            logger.info(
                "TiParse does not support %s, falling back to library engine",
                Path(file_path).suffix,
            )
            return self._library_fallback.extract_and_chunk(file_path)

        try:
            return self._tiparse_extract(file_path)
        except Exception as e:
            logger.warning(
                "TiParse failed for %s (%s), falling back to library engine",
                Path(file_path).name,
                e,
            )
            return self._library_fallback.extract_and_chunk(file_path)

    def _tiparse_extract(self, file_path: str) -> ExtractionResult:
        """Run TiParse extraction. Raises on import or runtime errors."""
        import asyncio
        from document_extractor import get_file_type

        # Lazy import — only fails when engine is actually used
        from tiparse import TiParse

        kwargs = {}
        if self.model:
            kwargs["model"] = self.model
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        parser = TiParse(**kwargs)
        chunked_doc = asyncio.run(
            parser.achunk(file_path, chunk_size=self.chunk_size)
        )

        chunks = [chunk.text for chunk in chunked_doc.chunks]
        metadata = {
            "file_path": os.path.abspath(file_path),
            "file_type": get_file_type(file_path),
        }
        doc_summary = getattr(chunked_doc, "summary", None)

        return ExtractionResult(
            chunks=chunks,
            engine="tiparse",
            metadata=metadata,
            doc_summary=doc_summary,
        )


def create_engine(name: str = "library", **kwargs) -> LibraryEngine | TiParseEngine:
    """Factory to create an extraction engine by name.

    Args:
        name: Engine name — "library" or "tiparse".
        **kwargs: Forwarded to the engine constructor.

    Returns:
        An extraction engine instance.
    """
    if name == "tiparse":
        return TiParseEngine(**kwargs)
    if name == "library":
        return LibraryEngine(**kwargs)
    raise ValueError(f"Unknown engine: {name!r}. Choose 'library' or 'tiparse'.")
