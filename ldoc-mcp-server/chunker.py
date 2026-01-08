"""
Text Chunking Module
Split text into overlapping chunks for embedding.
"""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks by character count.

    Args:
        text: Input text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Number of overlapping characters between chunks

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap

    return chunks


def chunk_by_paragraphs(text: str, max_chunk_size: int = 1000) -> list[str]:
    """
    Split text by paragraphs, respecting max chunk size.
    Tries to keep paragraphs together when possible.

    Args:
        text: Input text to chunk
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph alone exceeds max size, split it
        if len(para) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # Split large paragraph into smaller chunks
            sub_chunks = chunk_text(para, max_chunk_size, overlap=50)
            chunks.extend(sub_chunks)
        elif len(current_chunk) + len(para) + 2 < max_chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def chunk_by_sentences(text: str, sentences_per_chunk: int = 5, overlap: int = 1) -> list[str]:
    """
    Split text by sentences with overlap.

    Args:
        text: Input text to chunk
        sentences_per_chunk: Number of sentences per chunk
        overlap: Number of overlapping sentences

    Returns:
        List of text chunks
    """
    import re

    # Simple sentence splitting (handles ., !, ?)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= sentences_per_chunk:
        return [text]

    chunks = []
    start = 0

    while start < len(sentences):
        end = min(start + sentences_per_chunk, len(sentences))
        chunk = ' '.join(sentences[start:end])
        chunks.append(chunk)
        start = end - overlap

    return chunks


if __name__ == "__main__":
    # Test chunking
    sample_text = """
    This is the first paragraph. It contains multiple sentences.
    We want to test how the chunking works.

    This is the second paragraph. It should be kept together
    if possible, unless it exceeds the maximum chunk size.

    Third paragraph here. More content for testing purposes.
    The chunker should handle this gracefully.
    """

    print("=== Chunk by paragraphs ===")
    chunks = chunk_by_paragraphs(sample_text, max_chunk_size=200)
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1} ({len(chunk)} chars):")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)

    print("\n=== Chunk by character count ===")
    chunks = chunk_text(sample_text, chunk_size=100, overlap=20)
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1} ({len(chunk)} chars):")
        print(chunk)
