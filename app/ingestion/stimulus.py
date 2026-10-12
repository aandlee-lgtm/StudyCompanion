"""English stimulus-booklet import (sources-08).

A NESA Paper 1 stimulus booklet prints each unseen text under a heading such as
'Text 2 — Poem'. Each block becomes a ``Stimulus`` row: the body text (poems keep their line
breaks), the form, the attribution taken from the © / 'Source:' lines printed with the text, the
page, and the page region so a visual text (a web page, an advertisement, a cartoon) is kept as
a cropped image rather than recreated."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.layout import Layout, Row, is_noise_text
from app.ingestion.segment import _join

TEXT_HEAD = re.compile(r"^Text\s+(\d{1,2})\s*(?:[–—:-]\s*(.*))?$", re.I)
ATTRIB = re.compile(r"^(©|\(c\)|Source\s*:|From\s*:|Copyright\b|Reproduced\b|Image\s*:)", re.I)
VERSE_FORMS = re.compile(r"poem|poetry|verse|lyric|song|haiku|sonnet", re.I)
VISUAL_FORMS = re.compile(r"website|web page|image|photograph|advertisement|poster|cartoon|infographic|visual|graphic novel|comic|screenshot", re.I)
READING_WPM = 200  # words per minute used for reading-time estimates of unseen texts


@dataclass
class StimulusBlock:
    number: int
    form: str
    body: str
    attribution: str
    page: int
    regions: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)
    figure_regions: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"Text {self.number}" + (f" — {self.form}" if self.form else "")

    @property
    def visual(self) -> bool:
        return bool(self.figure_regions) or bool(VISUAL_FORMS.search(self.form or ""))

    @property
    def words(self) -> int:
        return len(re.findall(r"[A-Za-z’']+", self.body))

    @property
    def reading_minutes(self) -> float:
        return round(max(0.5, self.words / READING_WPM), 1)


@dataclass
class _Open:
    number: int
    form: str
    page: int
    rows: list[Row] = field(default_factory=list)
    attrib: list[str] = field(default_factory=list)


def _verse(rows: list[Row]) -> str:
    lines: list[str] = []
    prev: Row | None = None
    for r in rows:
        if prev is not None and r.page == prev.page and r.y0 - prev.y1 > 1.2 * max(prev.size, 8):
            lines.append("")  # stanza break
        lines.append(r.plain)
        prev = r
    return "\n".join(lines).strip()


def parse_stimulus_layout(layout: Layout) -> list[StimulusBlock]:
    blocks: list[StimulusBlock] = []
    cur: _Open | None = None

    def close():
        nonlocal cur
        if cur is None:
            return
        body_rows = cur.rows
        body = _verse(body_rows) if VERSE_FORMS.search(cur.form or "") else _join(body_rows)
        b = StimulusBlock(cur.number, cur.form, body, " ".join(cur.attrib).strip(), cur.page)
        by_page: dict[int, list[float]] = {}
        width = body_rows[0].width if body_rows else 595.0
        for r in body_rows:
            lo, hi = by_page.get(r.page, [r.y0, r.y1])
            by_page[r.page] = [min(lo, r.y0), max(hi, r.y1)]
        for p in layout.pages:
            if p.number in by_page or p.number == cur.page:
                lo, hi = by_page.get(p.number, [None, None])
                for f in p.figures:
                    if lo is None or (f.rect[3] >= lo - 30 and f.rect[1] <= hi + 30):
                        b.figure_regions.append((p.number, f.rect))
                        if lo is not None:
                            by_page[p.number] = [min(lo, f.rect[1]), max(hi, f.rect[3])]
        b.regions = [(pg, (0.06 * width, lo - 4, width - 0.04 * width, hi + 6)) for pg, (lo, hi) in sorted(by_page.items())]
        if not b.attribution:
            b.issues.append(f"No attribution (©/Source line) was found for Text {cur.number}; add it before approval.")
        if not body.strip() and not b.figure_regions:
            b.issues.append(f"Text {cur.number} has no readable text and no image region.")
        blocks.append(b)
        cur = None

    for row in layout.rows():
        text = row.plain
        if is_noise_text(text):
            continue
        hm = TEXT_HEAD.match(text)
        if hm and row.x0 < 0.4 * row.width and len(text) < 120:
            n = int(hm.group(1))
            if cur is not None and cur.number == n:
                continue  # 'Text 3 (continued)'
            close()
            cur = _Open(n, (hm.group(2) or "").strip(" –—-:"), row.page)
            continue
        if cur is None:
            continue
        if ATTRIB.match(text):
            cur.attrib.append(text)
            continue
        if re.match(r"^End of (Stimulus Booklet|texts?)\b", text, re.I):
            close()
            continue
        cur.rows.append(row)
    close()
    return blocks


def parse_stimulus_pdf(path: Path) -> list[StimulusBlock]:
    from app.ingestion.layout import read_layout

    return parse_stimulus_layout(read_layout(path))
