"""PDF text extraction. PyMuPDF first, pdfplumber as a fallback, OCR only if installed and
needed (scanned papers)."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Page:
    number: int  # 1-based
    text: str
    image_count: int = 0
    drawing_count: int = 0


@dataclass
class Extracted:
    pages: list[Page] = field(default_factory=list)
    method: str = "none"
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(path: Path, allow_ocr: bool = True) -> Extracted:
    out = Extracted()
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as doc:
            for i, page in enumerate(doc, start=1):
                try:
                    drawings = len(page.get_drawings())
                except Exception:
                    drawings = 0
                out.pages.append(Page(i, page.get_text("text"), len(page.get_images(full=True)), drawings))
        out.method = "pymupdf"
    except Exception as exc:  # pragma: no cover - depends on environment
        out.warnings.append(f"PyMuPDF failed: {exc}")
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    out.pages.append(Page(i, page.extract_text() or "", len(page.images), len(page.curves) + len(page.rects)))
            out.method = "pdfplumber"
        except Exception as exc2:
            out.warnings.append(f"pdfplumber failed: {exc2}")
    if allow_ocr and out.pages and sum(len(p.text.strip()) for p in out.pages) < 50 * len(out.pages):
        try:  # optional OCR fallback
            import fitz
            import pytesseract
            from PIL import Image
            import io

            with fitz.open(path) as doc:
                for p, page in zip(out.pages, doc):
                    if len(p.text.strip()) < 50:
                        pix = page.get_pixmap(dpi=200)
                        p.text = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))
            out.method += "+ocr"
        except ImportError:
            out.warnings.append("Little text found (scanned PDF?). Install pytesseract + Tesseract for OCR, or enter questions manually.")
        except Exception as exc:  # pragma: no cover
            out.warnings.append(f"OCR failed: {exc}")
    return out


def render_page(path: Path, page_number: int, out_path: Path, clip: tuple[float, float, float, float] | None = None, dpi: int = 150) -> Path | None:
    """Render a page (or a clipped region in page coordinates) to PNG for private study."""
    try:
        import fitz

        with fitz.open(path) as doc:
            page = doc[page_number - 1]
            rect = fitz.Rect(*clip) if clip else None
            pix = page.get_pixmap(dpi=dpi, clip=rect)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(out_path)
            return out_path
    except Exception as exc:  # pragma: no cover
        log.warning("render failed: %s", exc)
        return None


def find_region(path: Path, page_number: int, needle: str) -> tuple[float, float, float, float] | None:
    """Region from the line containing ``needle`` down to the next 'Question' heading (or page end)."""
    try:
        import fitz

        with fitz.open(path) as doc:
            page = doc[page_number - 1]
            hits = page.search_for(needle)
            if not hits:
                return None
            top = hits[0].y0 - 6
            nxt = [r for r in page.search_for("Question") if r.y0 > top + 20]
            bottom = (nxt[0].y0 - 4) if nxt else page.rect.y1
            return (page.rect.x0, top, page.rect.x1, bottom)
    except Exception:  # pragma: no cover
        return None
