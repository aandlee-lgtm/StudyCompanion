"""Coordinate-aware PDF layout for NESA-style papers (sources-01/02/04/16).

PyMuPDF gives text spans with bounding boxes. We regroup them into visual *rows* (spans whose
vertical extents overlap, so a question number in the left margin, the stem beside it and the
mark in the right margin form one row, and raised exponents stay on their line), detect figure
regions from vector drawings and images (ignoring ruled answer lines and page frames), and drop
running noise (footers, barcodes, 'Office Use Only').

Everything downstream works on ``Row`` objects, never on raw ``page.get_text('text')``."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

GAP = "   "  # three spaces mark a wide horizontal gap between tokens in Row.text


@dataclass
class Tok:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float = 10.0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Row:
    page: int
    toks: list[Tok]
    width: float  # page width
    height: float  # page height
    in_figure: bool = False

    @property
    def x0(self) -> float:
        return min(t.x0 for t in self.toks)

    @property
    def x1(self) -> float:
        return max(t.x1 for t in self.toks)

    @property
    def y0(self) -> float:
        return min(t.y0 for t in self.toks)

    @property
    def y1(self) -> float:
        return max(t.y1 for t in self.toks)

    @property
    def size(self) -> float:
        return max(t.size for t in self.toks)

    @property
    def text(self) -> str:
        out, prev = "", None
        for t in self.toks:
            s = t.text.strip()
            if prev is None:
                out = s
            else:
                gap = t.x0 - prev.x1
                sep = "" if gap <= 0.6 else (" " if gap < max(prev.size, t.size) * 1.6 else GAP)
                out += sep + s
            prev = t
        return out.strip()

    @property
    def plain(self) -> str:
        """Text with wide gaps collapsed to single spaces."""
        return re.sub(r"\s+", " ", self.text).strip()

    def without(self, drop: list[Tok]) -> "Row | None":
        keep = [t for t in self.toks if not any(t is d for d in drop)]
        return Row(self.page, keep, self.width, self.height, self.in_figure) if keep else None


@dataclass
class Figure:
    page: int
    rect: tuple[float, float, float, float]

    def contains(self, t: Tok, pad: float = 10.0) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 - pad <= t.cx <= x1 + pad and y0 - pad <= t.cy <= y1 + pad


@dataclass
class PageLayout:
    number: int
    width: float
    height: float
    rows: list[Row] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    image_count: int = 0


@dataclass
class Layout:
    pages: list[PageLayout] = field(default_factory=list)
    method: str = "pymupdf"
    warnings: list[str] = field(default_factory=list)

    def rows(self):
        for p in self.pages:
            yield from p.rows

    @property
    def text(self) -> str:
        return "\n".join(r.plain for r in self.rows())


# ------------------------------------------------------------------------------- noise ---
FOOTER = re.compile(r"^[–—-]\s*\d{1,3}\s*[–—-]$")
NOISE_PATTERNS = [
    re.compile(r"^Office Use Only", re.I),
    re.compile(r"^BLANK PAGE$", re.I),
    re.compile(r"^End of (paper|examination|section\b.*)$", re.I),
    re.compile(r"^End of Question \d{1,2}\b", re.I),
    re.compile(r"^Question \d{1,2} continues on (page|the next page)", re.I),
    re.compile(r"^Please turn over", re.I),
    re.compile(r"^\d{6,}$"),  # barcodes / candidate numbers
    re.compile(r"^Page \d+ of \d+$", re.I),
    re.compile(r"^NSW Education Standards Authority$", re.I),
]


def is_noise_text(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if FOOTER.match(t):
        return True
    return any(p.search(t) for p in NOISE_PATTERNS)


# ---------------------------------------------------------------------------- figures ---
def _figure_boxes(page, width: float, height: float) -> tuple[list[tuple], int]:
    """Union of drawing/image boxes, ignoring ruled answer lines, page frames and hairlines."""
    rects: list[list[float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:  # pragma: no cover
        drawings = []
    for d in drawings:
        r = d.get("rect")
        if r is None:
            continue
        w, h = r.x1 - r.x0, r.y1 - r.y0
        if h < 2.5 and w > 0.45 * width:  # ruled writing lines / separators
            continue
        if w > 0.85 * width and h > 0.85 * height:  # page frame
            continue
        if w < 1 and h < 1:
            continue
        rects.append([r.x0, r.y0, r.x1, r.y1])
    images = 0
    try:
        for info in page.get_image_info():
            b = info.get("bbox")
            if b:
                images += 1
                rects.append(list(b))
    except Exception:  # pragma: no cover
        pass
    # merge boxes that touch (with a small tolerance) until stable
    pad = 6.0
    merged = True
    while merged:
        merged = False
        out: list[list[float]] = []
        for r in rects:
            for o in out:
                if r[0] - pad <= o[2] and o[0] - pad <= r[2] and r[1] - pad <= o[3] and o[1] - pad <= r[3]:
                    o[0], o[1], o[2], o[3] = min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3])
                    merged = True
                    break
            else:
                out.append(list(r))
        rects = out
    boxes = [tuple(r) for r in rects if (r[2] - r[0]) * (r[3] - r[1]) >= 600 and (r[3] - r[1]) >= 12]
    return boxes, images


# ------------------------------------------------------------------------------- rows ---
def _rows_from_tokens(toks: list[Tok], page_no: int, width: float, height: float) -> list[Row]:
    toks = sorted(toks, key=lambda t: (t.cy, t.x0))
    rows: list[list[Tok]] = []
    for t in toks:
        placed = False
        for r in reversed(rows[-4:]):
            ry0, ry1 = min(x.y0 for x in r), max(x.y1 for x in r)
            overlap = min(ry1, t.y1) - max(ry0, t.y0)
            if overlap >= 0.45 * min(ry1 - ry0, t.y1 - t.y0):
                # same visual line unless the token collides horizontally with one already there
                if not any(t.x0 < x.x1 - 1 and x.x0 < t.x1 - 1 for x in r):
                    r.append(t)
                    placed = True
                    break
        if not placed:
            rows.append([t])
    out = [Row(page_no, sorted(r, key=lambda x: x.x0), width, height) for r in rows]
    out.sort(key=lambda r: (round(r.y0, 0), r.x0))
    return out


def page_layout(page, number: int) -> PageLayout:
    width, height = page.rect.width, page.rect.height
    toks: list[Tok] = []
    d = page.get_text("dict")
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                text = s.get("text", "")
                if not text.strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                # split a span on internal wide runs of spaces (one-line option lists)
                parts = re.split(r"(\s{3,}|\t+)", text)
                if len(parts) > 1 and len(text) > 0:
                    cw = (x1 - x0) / max(1, len(text))
                    pos = 0
                    for part in parts:
                        if part.strip() and not re.fullmatch(r"\s+", part):
                            lead = len(part) - len(part.lstrip())
                            px0 = x0 + (pos + lead) * cw
                            toks.append(Tok(part.strip(), px0, y0, px0 + len(part.strip()) * cw, y1, s.get("size", 10)))
                        pos += len(part)
                else:
                    toks.append(Tok(text, x0, y0, x1, y1, s.get("size", 10)))
    pl = PageLayout(number, width, height)
    boxes, images = _figure_boxes(page, width, height)
    pl.figures = [Figure(number, b) for b in boxes]
    pl.image_count = images
    pl.rows = _rows_from_tokens(toks, number, width, height)
    return pl


def read_layout(path: Path, allow_ocr: bool = True) -> Layout:
    """Rows and figures for every page. Falls back to plain text lines (no coordinates) for
    scanned pages when OCR is available."""
    import fitz

    lay = Layout()
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pl = page_layout(page, i)
            if not pl.rows and allow_ocr:
                text = _ocr_page(page, lay)
                y = 60.0
                for line in (text or "").splitlines():
                    if line.strip():
                        pl.rows.append(Row(i, [Tok(line.strip(), 60, y, 60 + 5 * len(line), y + 10)], pl.width, pl.height))
                        y += 14
                if text:
                    lay.method = "pymupdf+ocr"
            lay.pages.append(pl)
    if lay.pages and not any(p.rows for p in lay.pages):
        lay.warnings.append("No text found (scanned PDF?). Install pytesseract + Tesseract for OCR, or enter questions manually.")
    return lay


def _ocr_page(page, lay: Layout) -> str | None:
    try:
        import io

        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=200)
        return pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))
    except ImportError:
        return None
    except Exception as exc:  # pragma: no cover
        lay.warnings.append(f"OCR failed on page {page.number + 1}: {exc}")
        return None


def repeated_running_text(layout: Layout, band: float = 0.09) -> set[str]:
    """Normalised text of rows that repeat near the top or bottom of several pages (running
    headers and footers in marking guidelines)."""
    if len(layout.pages) < 2:
        return set()
    seen: dict[str, set[int]] = {}
    for p in layout.pages:
        for r in p.rows:
            if r.y1 < p.height * band or r.y0 > p.height * (1 - band):
                key = norm_key(r.plain)
                seen.setdefault(key, set()).add(p.number)
    need = 2 if len(layout.pages) <= 3 else max(2, len(layout.pages) // 2)
    return {k for k, pages in seen.items() if len(pages) >= need}


def norm_key(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.strip().lower()))


# ------------------------------------------------------------------------- rendering ---
def render_regions(path: Path, regions: list[tuple[int, tuple[float, float, float, float]]], out_path: Path, dpi: int = 150) -> Path | None:
    """Render one or more page regions (stacked vertically, e.g. a part that continues on the
    next page) into a single PNG."""
    try:
        import fitz

        regions = [(p, r) for p, r in regions if r[3] - r[1] > 4 and r[2] - r[0] > 4]
        if not regions:
            return None
        with fitz.open(path) as src:
            if len(regions) == 1:
                pno, rect = regions[0]
                pix = src[pno - 1].get_pixmap(dpi=dpi, clip=fitz.Rect(*rect))
            else:
                width = max(r[2] - r[0] for _, r in regions)
                height = sum(r[3] - r[1] for _, r in regions) + 6 * (len(regions) - 1)
                tmp = fitz.open()
                page = tmp.new_page(width=width, height=height)
                y = 0.0
                for pno, r in regions:
                    h = r[3] - r[1]
                    page.show_pdf_page(fitz.Rect(0, y, r[2] - r[0], y + h), src, pno - 1, clip=fitz.Rect(*r))
                    y += h + 6
                pix = page.get_pixmap(dpi=dpi)
                tmp.close()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(out_path)
            return out_path
    except Exception:  # pragma: no cover - rendering is best effort
        return None
