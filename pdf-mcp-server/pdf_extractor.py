"""
PDF Text Extraction Module
Uses PyMuPDF (fitz) to extract text from PDF files.
"""

import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a single string
    """
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        if page_text.strip():
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page_text
    doc.close()
    return text


def extract_text_with_metadata(pdf_path: str) -> dict:
    """
    Extract text and metadata from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with text, page_count, and metadata
    """
    doc = fitz.open(pdf_path)

    pages = []
    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        if page_text.strip():
            pages.append({
                "page_num": page_num + 1,
                "text": page_text
            })

    metadata = doc.metadata
    page_count = len(doc)
    doc.close()

    return {
        "file_path": str(pdf_path),
        "file_name": Path(pdf_path).name,
        "page_count": page_count,
        "metadata": metadata,
        "pages": pages,
        "full_text": "\n".join([p["text"] for p in pages])
    }


def extract_from_multiple_pdfs(pdf_paths: list[str]) -> dict[str, str]:
    """
    Extract text from multiple PDF files.

    Args:
        pdf_paths: List of paths to PDF files

    Returns:
        Dictionary mapping file paths to extracted text
    """
    results = {}
    for path in pdf_paths:
        try:
            results[path] = extract_text_from_pdf(path)
        except Exception as e:
            print(f"Error extracting {path}: {e}")
            results[path] = ""
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_file>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(text)} characters from {pdf_path}")
    print("-" * 50)
    print(text[:2000] + "..." if len(text) > 2000 else text)
