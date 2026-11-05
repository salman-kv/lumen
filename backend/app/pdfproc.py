"""PDF validation, per-page text extraction and page-aware chunking."""
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .config import settings


class PdfError(Exception):
    """Raised with a user-facing message."""


@dataclass
class PageText:
    page: int
    text: str


def validate_and_read(data: bytes, filename: str) -> list[PageText]:
    if not filename.lower().endswith(".pdf"):
        raise PdfError(f'"{filename}" is not a PDF. Only .pdf files are supported.')
    if len(data) == 0:
        raise PdfError(f'"{filename}" is empty.')
    if len(data) > settings.max_pdf_mb * 1024 * 1024:
        mb = len(data) / 1024 / 1024
        raise PdfError(f'"{filename}" is {mb:.1f} MB. The maximum size is {settings.max_pdf_mb} MB per PDF.')
    if not data.lstrip()[:5] == b"%PDF-":
        raise PdfError(f'"{filename}" does not look like a valid PDF file.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfError(f'"{filename}" is password protected. Please upload an unlocked copy.')
        n = len(reader.pages)
    except PdfError:
        raise
    except (PyPdfError, Exception):
        raise PdfError(f'"{filename}" could not be read. The file may be corrupted.')
    if n == 0:
        raise PdfError(f'"{filename}" has no pages.')
    if n > settings.max_pages:
        raise PdfError(f'"{filename}" has {n} pages. The maximum is {settings.max_pages} pages per PDF.')
    pages = []
    for i, p in enumerate(reader.pages, start=1):
        try:
            text = p.extract_text() or ""
        except Exception:
            text = ""
        pages.append(PageText(i, clean(text)))
    if not any(p.text.strip() for p in pages):
        raise PdfError(f'"{filename}" contains no extractable text (it may be a scanned image).')
    return pages


def clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_page(text: str, max_chars: int = 650) -> list[str]:
    """Split a page on blank lines / sentences into chunks that never cross a page boundary."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = [b.strip() for b in text.split("\n") if b.strip()]
    chunks, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) + 1 <= max_chars:
            cur = f"{cur}\n{b}".strip()
            continue
        if cur:
            chunks.append(cur)
        if len(b) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", b)
            cur = ""
            for s in sentences:
                if len(cur) + len(s) + 1 <= max_chars:
                    cur = f"{cur} {s}".strip()
                else:
                    if cur:
                        chunks.append(cur)
                    cur = s
        else:
            cur = b
    if cur:
        chunks.append(cur)
    return chunks
