"""Marking-guideline parser (sources-09/10).

Works on the coordinate layout of a NESA-style marking guideline PDF:

* running headers/footers (rows repeated near the top/bottom of several pages, 'Page N of M')
  are removed before anything else;
* 'Multiple-choice Answer Key' tables become ``mcq_key`` {question number: letter}, whether the
  key is laid out as rows ('1  B'), one token per line, or transposed ('Question 1 2 3' /
  'Answer B A D');
* every 'Question 11 (b) (i)' heading starts an entry keyed by the full label ``11(b)(i)``, so
  sub-parts never overwrite each other;
* 'Criteria | Marks' tables become structured rows (criterion, marks or a range such as 7–8),
  'Sample answer:' and 'Answers could include:' are captured separately;
* the 'Mapping Grid' (question, marks, content, syllabus outcomes, targeted bands) becomes
  ``grid`` rows that feed the original topic, outcome and a difficulty hint.

Nothing here invents content: an entry holds only text found in the PDF."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.layout import GAP, Layout, Row, is_noise_text, norm_key, repeated_running_text

ROMAN = r"(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)"
HEAD = re.compile(rf"^Question\s+(\d{{1,2}})\s*((?:\(\s*[a-h]\s*\)\s*)?(?:\(\s*{ROMAN}\s*\)\s*)?)(.*)$", re.I)
SECTION = re.compile(r"^Section\s+(I{1,3}|IV|VI{0,3}|V)\b", re.I)
KEY_HEAD = re.compile(r"multiple[- ]choice\s+answer\s+key", re.I)
GRID_HEAD = re.compile(r"mapping\s+grid", re.I)
MARK_TOKEN = re.compile(r"^(\d{1,2})(?:\s*[–—-]\s*(\d{1,2}))?$")
OUTCOME = re.compile(r"\b([A-Z]{2,4}\d{1,2}-\d{1,2}[A-Z]?)\b")
BANDS = re.compile(r"\b(E?\d\s*[–—-]\s*E?\d|E?\d)\s*$")
SAMPLE = re.compile(r"^(Sample answer|Sample response|Answer)s?\s*:?\s*(.*)$", re.I)
COULD = re.compile(r"^Answers? (could|may) include\s*:?\s*(.*)$", re.I)
CRITERIA_HEAD = re.compile(r"^Criteria\b.*\bMarks?$", re.I)
GUIDELINE_KINDS = ("official_nesa", "school_trial", "app_authored", "third_party")


@dataclass
class Criterion:
    text: str
    marks: str  # "2" or "7–8"
    low: int
    high: int


@dataclass
class GuidelineEntry:
    key: str  # "11(b)(i)"
    label: str  # "Question 11 (b) (i)"
    page: int
    criteria: list[Criterion] = field(default_factory=list)
    sample_answer: str = ""
    answers_could_include: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def top_mark(self) -> int | None:
        return max((c.high for c in self.criteria), default=None)

    @property
    def text(self) -> str:
        """Readable guideline text (what the reviewer and the AI marker see)."""
        out: list[str] = []
        if self.criteria:
            out.append("Criteria — Marks")
            out += [f"• {c.text} — {c.marks}" for c in self.criteria]
        rest = [ln for ln in self.lines if ln]
        if not self.criteria and rest:
            out += rest
        if self.answers_could_include:
            out.append("Answers could include:")
            out += [f"• {a}" for a in self.answers_could_include]
        if self.sample_answer:
            out.append("Sample answer:")
            out.append(self.sample_answer)
        return "\n".join(out).strip()

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "page": self.page, "top_mark": self.top_mark,
                "criteria": [{"criterion": c.text, "marks": c.marks, "max": c.high} for c in self.criteria],
                "sample_answer": self.sample_answer or None, "answers_could_include": self.answers_could_include}


@dataclass
class GridRow:
    key: str
    marks: int | None
    content: str
    outcomes: list[str]
    bands: str | None

    @property
    def difficulty_hint(self) -> int | None:
        """1 foundation, 2 HSC-standard, 3 challenging, from the targeted performance bands."""
        if not self.bands:
            return None
        nums = [int(n) for n in re.findall(r"\d", self.bands)]
        if not nums:
            return None
        if self.bands.strip().upper().startswith("E"):
            return 3
        top = max(nums)
        return 1 if top <= 3 else (2 if top <= 5 else 3)


@dataclass
class GuidelineSet:
    mcq_key: dict[int, str] = field(default_factory=dict)
    entries: dict[str, GuidelineEntry] = field(default_factory=dict)
    grid: dict[str, GridRow] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def entry(self, key: str) -> GuidelineEntry | None:
        return self.entries.get(key)

    def entries_for(self, keys: list[str]) -> list[GuidelineEntry]:
        """Guideline entries for a unit's keys, most specific first, without duplicates. A
        unit keyed ``11(b)`` with sub-parts gets ``11(b)(i)`` and ``11(b)(ii)``; a guideline
        written for the whole of ``11(b)`` is used when no sub-part entries exist."""
        found: list[GuidelineEntry] = []
        for k in keys:
            e = self.entries.get(k)
            if e and e not in found:
                found.append(e)
        return found

    def grid_for(self, keys: list[str]) -> GridRow | None:
        for k in keys:
            if k in self.grid:
                return self.grid[k]
        for k in keys:  # '11(b)(i)' falls back to '11(b)' then '11'
            parts = re.findall(r"^\d+|\([^)]*\)", k)
            while len(parts) > 1:
                parts = parts[:-1]
                kk = "".join(parts)
                if kk in self.grid:
                    return self.grid[kk]
        return None


def normalise_key(number: str, labels: str = "") -> str:
    labs = re.findall(r"\(\s*([a-z]+)\s*\)", labels.lower())
    return str(int(number)) + "".join(f"({x})" for x in labs)


def _mark_of(row: Row) -> tuple[str | None, Row | None]:
    last = row.toks[-1]
    s = last.text.strip()
    m = MARK_TOKEN.match(s)
    if m and last.x0 > 0.7 * row.width and len(row.toks) > 1:
        return s.replace("—", "–").replace("-", "–"), Row(row.page, row.toks[:-1], row.width, row.height)
    # a mark typed at the end of the same text object after a wide gap
    if GAP in row.text:
        head, _, tail = row.text.rpartition(GAP)
        if MARK_TOKEN.match(tail.strip()) and head.strip():
            from app.ingestion.layout import Tok

            t0 = row.toks[0]
            return tail.strip().replace("—", "–").replace("-", "–"), Row(row.page, [Tok(head.strip(), t0.x0, t0.y0, t0.x1, t0.y1, t0.size)], row.width, row.height)
    return None, row


def _range(marks: str) -> tuple[int, int]:
    nums = [int(n) for n in re.findall(r"\d+", marks)]
    return (min(nums), max(nums)) if nums else (0, 0)


def _parse_key_tokens(rows: list[Row]) -> dict[int, str]:
    """Answer key from rows in any of the three layouts."""
    key: dict[int, str] = {}
    texts = [r.plain for r in rows]
    # transposed: 'Question 1 2 3 ...' followed by 'Answer B A D ...'
    for i, t in enumerate(texts[:-1]):
        a = t.split()
        b = texts[i + 1].split()
        if a and b and a[0].lower() == "question" and b[0].lower() == "answer" and len(a) > 2:
            nums = [x for x in a[1:] if x.isdigit()]
            lets = [x for x in b[1:] if re.fullmatch(r"[A-D]", x)]
            if nums and len(nums) == len(lets):
                key.update({int(n): l for n, l in zip(nums, lets)})
    if key:
        return key
    flat = [tok.strip(".)") for t in texts for tok in t.split() if tok.lower() not in ("question", "answer", "questions", "answers")]
    pending: int | None = None
    for tok in flat:
        if tok.isdigit() and 0 < int(tok) <= 40:
            pending = int(tok)
        elif re.fullmatch(r"[A-D]", tok) and pending is not None:
            key[pending] = tok
            pending = None
    return key


def parse_guidelines(layout: Layout) -> GuidelineSet:
    gs = GuidelineSet()
    running = repeated_running_text(layout)
    mode = "pre"  # pre | key | criteria | grid
    key_rows: list[Row] = []
    entry: GuidelineEntry | None = None
    sub: str | None = None  # None | criteria | sample | could
    grid_section = ""

    def finish_key():
        nonlocal key_rows
        if key_rows:
            got = _parse_key_tokens(key_rows)
            gs.mcq_key.update(got)
            if not got:
                gs.warnings.append("A multiple-choice answer key heading was found but no answers could be read.")
        key_rows = []

    for row in layout.rows():
        text = row.plain
        if is_noise_text(text) or norm_key(text) in running:
            continue
        if KEY_HEAD.search(text):
            finish_key()
            mode, entry, sub = "key", None, None
            continue
        if GRID_HEAD.search(text):
            finish_key()
            mode, entry, sub = "grid", None, None
            continue
        if SECTION.match(text):
            if mode == "key" and key_rows:
                finish_key()
                mode = "criteria"
            if mode == "grid":
                grid_section = SECTION.match(text).group(1).upper()
            continue
        if mode == "key":
            hm = HEAD.match(text)
            transposed = bool(hm and not hm.group(2).strip() and re.fullmatch(r"(\d{1,2}\s+)*\d{1,2}", (hm.group(3) or "").strip()))
            if CRITERIA_HEAD.match(text) or (hm and not transposed):
                finish_key()
                mode = "criteria"
            else:
                key_rows.append(row)
                continue
        if mode == "grid":
            _grid_row(gs, text, grid_section)
            continue
        hm = HEAD.match(text)
        if hm and row.x0 < 0.4 * row.width:
            finish_key()
            mode = "criteria"
            k = normalise_key(hm.group(1), hm.group(2))
            if k in gs.entries:
                gs.warnings.append(f"The guideline for {k} appears twice; the second copy was appended.")
                entry = gs.entries[k]
            else:
                entry = GuidelineEntry(k, re.sub(r"\s+", " ", f"Question {hm.group(1)} {hm.group(2)}").strip(), row.page)
                gs.entries[k] = entry
            sub = None
            rest = (hm.group(3) or "").strip()
            if rest:
                entry.lines.append(rest)
            continue
        if entry is None:
            continue
        if CRITERIA_HEAD.match(text):
            sub = "criteria"
            continue
        sm = SAMPLE.match(text)
        if sm and text.split()[0].lower().startswith("sample"):
            sub = "sample"
            if sm.group(2):
                entry.sample_answer = sm.group(2).strip()
            continue
        cm = COULD.match(text)
        if cm:
            sub = "could"
            if cm.group(2):
                entry.answers_could_include.append(cm.group(2).strip())
            continue
        mark, rest = _mark_of(row)
        if mark is not None and rest is not None and sub in (None, "criteria"):
            lo, hi = _range(mark)
            ctext = re.sub(r"^[•·\-–]\s*", "", rest.plain).strip()
            entry.criteria.append(Criterion(ctext, mark, lo, hi))
            sub = "criteria"
            continue
        if sub == "sample":
            entry.sample_answer = (entry.sample_answer + "\n" + text).strip()
        elif sub == "could":
            item = re.sub(r"^[•·\-–]\s*", "", text).strip()
            if text.lstrip().startswith(("•", "·", "-", "–")) or not entry.answers_could_include:
                entry.answers_could_include.append(item)
            else:
                entry.answers_could_include[-1] += " " + item
        elif sub == "criteria" and entry.criteria and not text.lstrip().startswith("•"):
            entry.criteria[-1].text += " " + text.strip()  # wrapped criterion
        else:
            entry.lines.append(text)
    finish_key()
    return gs


def _grid_row(gs: GuidelineSet, text: str, section: str) -> None:
    t = re.sub(r"\s+", " ", text).strip()
    if re.match(r"^Question\b", t, re.I):
        return  # header row
    m = re.match(rf"^(\d{{1,2}})\s*((?:\(\s*[a-h]\s*\)\s*)?(?:\(\s*{ROMAN}\s*\)\s*)?)(\d{{1,2}})\s+(.*)$", t)
    if not m:
        return
    key = normalise_key(m.group(1), m.group(2))
    rest = m.group(4)
    outcomes = OUTCOME.findall(rest)
    bands = None
    bm = BANDS.search(rest)
    if bm and (not outcomes or bm.start() > rest.rfind(outcomes[-1])):
        bands = bm.group(1).replace(" ", "")
        rest = rest[: bm.start()].strip()
    content = rest
    if outcomes:
        first = rest.find(outcomes[0])
        content = rest[:first].strip() if first > 0 else rest
        content = OUTCOME.sub("", content).strip(" ,;")
    gs.grid[key] = GridRow(key, int(m.group(3)), content, outcomes, bands)


def parse_guideline_pdf(path: Path) -> GuidelineSet:
    from app.ingestion.layout import read_layout

    return parse_guidelines(read_layout(path))


def mcq_answer(letter: str) -> dict:
    return {"type": "mcq", "value": letter.strip().upper()}
