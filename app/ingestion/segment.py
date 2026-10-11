"""Coordinate-based question segmentation for NESA-style papers (sources-01/02/04/11/16).

Input is the row layout from ``app.ingestion.layout``. Rules (all derived from how NESA papers
are typeset):

* Section headings ('Section I', 'Section III — Human rights') start a section; the rows that
  follow until the first question are instructions: they are never questions, but
  'Attempt Questions 1–10' gives the expected count and 'multiple-choice' the section type.
* Multiple choice: the question number is an integer token in the left margin whose value is the
  next expected number; option labels A–D are found by position, in order, wherever they sit on
  a row (one per line, all on one line, 2 x 2 grid, or letter-only graph options).
* Written questions: 'Question N (M marks)' headings give the question total; '(a)' labels start
  parts and '(i)' labels start sub-parts; marks are integer tokens in the right margin (beyond
  85 % of the page width) and belong to the innermost open part. Tokens inside figure regions
  (axis labels, tick marks) are never text and never marks.
* State carries across page breaks, so '(ii)' after 'Question 13 (continued)' stays a sub-part
  of 13(b). A lettered part that begins 'Hence…' is merged with the part it depends on.
* Each servable unit is a lettered part (or the whole question when it has none). Sub-parts
  become ``parts`` (QuestionPart rows) with their own marks and guideline keys.
* Anything inconsistent (parts that do not add up to the heading, a missing mark, an MCQ without
  four options, a short count) is recorded in ``issues``; issues block approval later."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.layout import GAP, Figure, Layout, Row, is_noise_text

SECTION = re.compile(r"^Section\s+(I{1,3}|IV|VI{0,3}|V)\b\s*[–—:-]?\s*(.*)$", re.I)
Q_HEAD = re.compile(r"^Question\s+(\d{1,2})\b\s*(.*)$", re.I)
HEAD_MARKS = re.compile(r"\(\s*(\d{1,3})\s*marks?\s*\)", re.I)
BOOKLET = re.compile(r"Use the Question \d{1,2} Writing Booklet\.?", re.I)
PART = re.compile(r"^\(([a-h])\)(?:\s+|$)")
SUBPART = re.compile(r"^\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\)(?:\s+|$)")
ROMANS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
MCQ_NUM = re.compile(r"^(\d{1,2})[.)]?$")
MCQ_NUM_TEXT = re.compile(r"^(\d{1,2})[.)]?\s+(\S.*)$")
OPT_LABEL = re.compile(r"^\(?([A-D])[.)](?:\s+(.*))?$")
ATTEMPT_RANGE = re.compile(r"Attempt Questions?\s+(\d{1,2})\s*[–—-]\s*(\d{1,2})", re.I)
ATTEMPT_ONE = re.compile(r"Attempt Question\s+(\d{1,2})\b", re.I)
ATTEMPT_FROM = re.compile(r"Attempt\s+(ONE|TWO|THREE|\d)\s+questions?\s+from\s+Questions\s+(\d{1,2})\s*[–—-]\s*(\d{1,2})", re.I)
INSTRUCTION_IN_QUESTION = [
    re.compile(r"^Answer EITHER part", re.I),
    re.compile(r"^OR$"),
    re.compile(r"^Answer the question in a writing booklet", re.I),
    re.compile(r"^(Answer each question in|Extra writing booklets)", re.I),
    re.compile(r"^Use the Question \d{1,2} Writing Booklet", re.I),
]
CONTINUED = re.compile(r"^Question\s+(\d{1,2})\s*\(continued\)", re.I)
HENCE = re.compile(r"^(Hence\b|Using (your|the) (answer|result)|Use your (answer|result)|Deduce\b)", re.I)
TEXT_REFS = re.compile(r"\bTexts?\s+(\d{1,2}(?:\s*(?:,|and|&)\s*\d{1,2})*)", re.I)
WORDS = {"ONE": 1, "TWO": 2, "THREE": 3}


@dataclass
class SubPart:
    label: str  # "(i)", "(c)", "(c)(i)"
    key: str  # guideline key, e.g. "11(b)(i)"
    text: str
    marks: int | None
    hence: bool = False


@dataclass
class Unit:
    """One servable question unit (kept compatible with the v1 ``Segment`` fields)."""

    number: str  # "11(b)", "13(c)–(d)", "3"
    text: str
    marks: int | None
    page: int
    section: str  # "mcq" | "written"
    options: list[str] = field(default_factory=list)
    has_visual: bool = False
    question: str = ""  # "11"
    parts: list[SubPart] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)  # guideline keys this unit covers
    regions: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)
    figure_regions: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)
    section_name: str | None = None  # "I", "IV"
    section_title: str | None = None  # "Human rights"
    question_title: str | None = None  # "Consumers" (Legal option questions)
    heading_marks: int | None = None
    alternative_group: str | None = None  # EITHER/OR: the question number shared by alternatives
    stem: str = ""
    stimulus_refs: list[int] = field(default_factory=list)
    graph_options: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def pages(self) -> list[int]:
        return sorted({p for p, _ in self.regions}) or [self.page]


Segment = Unit  # v1 name


@dataclass
class SectionInfo:
    name: str
    title: str = ""
    marks: int | None = None
    mode: str | None = None  # mcq | written
    expected: tuple[int, int] | None = None
    choose: int | None = None  # 'Attempt TWO questions from ...'
    instructions: list[str] = field(default_factory=list)
    detected_mcq: int = 0
    detected_questions: set = field(default_factory=set)


@dataclass
class SegmentResult:
    units: list[Unit] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)
    cover: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def expected_vs_detected(self) -> list[dict]:
        out = []
        for s in self.sections:
            if s.expected:
                exp = s.expected[1] - s.expected[0] + 1
                det = s.detected_mcq if s.mode == "mcq" else len(s.detected_questions)
                out.append({"section": s.name, "mode": s.mode, "expected": exp, "detected": det, "range": f"{s.expected[0]}–{s.expected[1]}"})
        return out


# ---------------------------------------------------------------------- containers ---
@dataclass
class _Box:
    """A part, sub-part or question stem being filled while reading rows."""

    label: str
    rows: list[Row] = field(default_factory=list)
    marks: int | None = None
    children: list["_Box"] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class _Question:
    number: int
    page: int
    section: SectionInfo | None
    heading_marks: int | None = None
    title: str | None = None
    either_or: bool = False
    stem: _Box = field(default_factory=lambda: _Box(""))
    parts: list[_Box] = field(default_factory=list)


@dataclass
class _MCQ:
    number: int
    page: int
    section: SectionInfo | None
    stem_rows: list[Row] = field(default_factory=list)
    options: list[list] = field(default_factory=list)  # [letter, text, page, y]
    rows: list[Row] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _join(rows: list[Row]) -> str:
    """Rows -> text. Wrapped lines (same left edge) join with a space; indented display lines,
    tables and poems keep their line breaks."""
    out = ""
    prev: Row | None = None
    for r in rows:
        t = r.text.strip()
        if not t:
            continue
        if prev is None:
            out = t
        else:
            tabular = GAP in t or GAP in prev.text
            same_edge = abs(r.x0 - prev.x0) <= 4 and r.page == prev.page
            new_para = r.page == prev.page and r.y0 - prev.y1 > 1.2 * max(prev.size, 8)
            if tabular or new_para:
                out += ("\n\n" if new_para and not tabular else "\n") + t
            elif same_edge or r.page != prev.page:
                out += " " + t
            else:
                out += "\n" + t
        prev = r
    out = re.sub(r"[ \t]{2,}", lambda m: "   " if len(m.group()) >= 3 else " ", out)
    return out.strip()


def _strip_label(row: Row, pattern: re.Pattern) -> tuple[str | None, Row | None]:
    """If the row starts with a label (as its own token or as the start of the first token),
    return (label, row without the label)."""
    first = row.toks[0]
    m = pattern.match(first.text.strip())
    if not m:
        return None, row
    label = m.group(1)
    rest = first.text.strip()[m.end():].strip()
    toks = list(row.toks[1:])
    if rest:
        from app.ingestion.layout import Tok

        toks.insert(0, Tok(rest, first.x1 - len(rest) * (first.x1 - first.x0) / max(1, len(first.text)), first.y0, first.x1, first.y1, first.size))
    return label, (Row(row.page, toks, row.width, row.height) if toks else None)


def _right_margin_mark(row: Row) -> tuple[int | None, Row | None]:
    last = row.toks[-1]
    if re.fullmatch(r"\d{1,2}", last.text.strip()) and last.x0 > 0.85 * row.width:
        rest = row.toks[:-1]
        return int(last.text.strip()), (Row(row.page, rest, row.width, row.height) if rest else None)
    return None, row


def _parse_instruction(sec: SectionInfo, text: str) -> None:
    sec.instructions.append(text)
    if re.search(r"multiple[- ]choice", text, re.I):
        sec.mode = sec.mode or "mcq"
    m = ATTEMPT_FROM.search(text)
    if m:
        sec.choose = WORDS.get(m.group(1).upper(), None) or (int(m.group(1)) if m.group(1).isdigit() else None)
        sec.expected = (int(m.group(2)), int(m.group(3)))
        return
    m = ATTEMPT_RANGE.search(text)
    if m:
        sec.expected = (int(m.group(1)), int(m.group(2)))
        return
    m = ATTEMPT_ONE.search(text)
    if m:
        sec.expected = (int(m.group(1)), int(m.group(1)))
        return
    m = re.match(r"^(\d{1,3})\s*marks$", text, re.I)
    if m:
        sec.marks = int(m.group(1))


def _is_cover(rows: list[Row]) -> bool:
    text = " ".join(r.plain for r in rows[:60])
    has_q = any(Q_HEAD.match(r.plain) and HEAD_MARKS.search(r.plain) for r in rows)
    return bool(re.search(r"Total marks|General Instructions|Reading time", text, re.I)) and not has_q


def segment_layout(layout: Layout) -> SegmentResult:
    res = SegmentResult()
    has_margin_marks = any(
        r.toks and re.fullmatch(r"\d{1,2}", r.toks[-1].text.strip()) and r.toks[-1].x0 > 0.85 * r.width for r in layout.rows()
    )
    pages = list(layout.pages)
    if pages and _is_cover(pages[0].rows):
        res.cover = [r.plain for r in pages[0].rows]
        pages = pages[1:]

    section: SectionInfo | None = None
    in_instructions = False
    q: _Question | None = None
    mcq: _MCQ | None = None
    questions: list[_Question] = []
    mcqs: list[_MCQ] = []
    timeline: list[tuple[int, float, _Box]] = []  # (page, y, box) whenever a box receives a row
    next_mcq = 1
    figures: list[Figure] = [f for p in pages for f in p.figures]

    def close_mcq():
        nonlocal mcq
        if mcq is not None:
            mcqs.append(mcq)
            if mcq.section:
                mcq.section.detected_mcq += 1
        mcq = None

    def close_q():
        nonlocal q
        if q is not None:
            questions.append(q)
            if q.section:
                q.section.detected_questions.add(q.number)
        q = None

    def innermost(qq: _Question) -> _Box:
        if qq.parts:
            p = qq.parts[-1]
            return p.children[-1] if p.children else p
        return qq.stem

    for page in pages:
        page_figs = page.figures
        for row in page.rows:
            text = row.plain
            if is_noise_text(text):
                continue
            # ---- section headings
            sm = SECTION.match(text)
            if sm and row.x0 < 0.3 * row.width and not re.search(r"\(pages?\s", text, re.I):
                close_mcq()
                close_q()
                rest = sm.group(2).strip()
                title = re.sub(r"^\d{1,3}\s*marks?\b.*$", "", rest, flags=re.I).strip(" –—-:")
                section = SectionInfo(sm.group(1).upper(), title=title)
                mk = re.search(r"(\d{1,3})\s*marks", rest, re.I)
                if mk:
                    section.marks = int(mk.group(1))
                res.sections.append(section)
                in_instructions = True
                continue
            cm = CONTINUED.match(text)
            if cm:
                if q is None or q.number != int(cm.group(1)):
                    res.warnings.append(f"'{text}' on page {row.page} does not follow Question {cm.group(1)}.")
                continue
            # ---- written question heading
            hm = Q_HEAD.match(text)
            if hm and row.x0 < 0.3 * row.width:
                close_mcq()
                close_q()
                in_instructions = False
                if section is None:
                    section = SectionInfo("", mode="written")
                    res.sections.append(section)
                section.mode = "written" if section.mode != "mcq" or not section.detected_mcq else section.mode
                n = int(hm.group(1))
                rest = BOOKLET.sub("", hm.group(2)).strip()
                q = _Question(n, row.page, section)
                mk = HEAD_MARKS.search(rest)
                if mk:
                    q.heading_marks = int(mk.group(1))
                    before, after = rest[: mk.start()].strip(" –—-:"), rest[mk.end():].strip(" –—-:.")
                    q.title = before or None
                    rest = after
                else:
                    rest = rest.strip(" –—-:")
                if rest:
                    q.stem.rows.append(Row(row.page, [_tok_like(row, rest)], row.width, row.height))
                    timeline.append((row.page, row.y0, q.stem))
                continue
            # ---- section instructions (before the first question of a section)
            if in_instructions and section is not None:
                first = row.toks[0].text.strip()
                starts_mcq = (MCQ_NUM.match(first) or MCQ_NUM_TEXT.match(text)) and row.toks[0].x0 < 0.2 * row.width
                num = int((MCQ_NUM.match(first) or MCQ_NUM_TEXT.match(text)).group(1)) if starts_mcq else None
                exp_start = section.expected[0] if section.expected else 1
                if not (starts_mcq and num == exp_start and (section.mode in (None, "mcq"))):
                    _parse_instruction(section, text)
                    continue
                in_instructions = False
                section.mode = "mcq"
                next_mcq = exp_start
            # ---- multiple choice
            if q is None and (section is None or section.mode in (None, "mcq")):
                first = row.toks[0]
                m1 = MCQ_NUM.match(first.text.strip())
                m2 = None if m1 else MCQ_NUM_TEXT.match(first.text.strip())
                num = int((m1 or m2).group(1)) if (m1 or m2) else None
                if num is not None and first.x0 < 0.2 * row.width and num in (next_mcq, next_mcq + 1) and (mcq is None or mcq.options or num == next_mcq):
                    close_mcq()
                    if section is None:
                        section = SectionInfo("", mode="mcq")
                        res.sections.append(section)
                    section.mode = "mcq"
                    mcq = _MCQ(num, row.page, section)
                    if num != next_mcq:
                        mcq.issues.append(f"Question {next_mcq} was not detected before question {num}.")
                    next_mcq = num + 1
                    rest = row.toks[1:]
                    if m2:
                        rest = [_tok_like(first, m2.group(2))] + rest
                    mcq.rows.append(row)
                    if rest:
                        mcq.stem_rows.append(Row(row.page, rest, row.width, row.height))
                    continue
                if mcq is not None:
                    mcq.rows.append(row)
                    _mcq_row(mcq, row, page_figs)
                    continue
                continue  # preamble before any question
            if q is None:
                continue
            # ---- inside a written question
            if any(p.search(text) for p in INSTRUCTION_IN_QUESTION):
                if re.search(r"EITHER", text):
                    q.either_or = True
                continue
            row = _drop_figure_tokens(row, page_figs)
            if row is None:
                continue
            mark, row = _right_margin_mark(row)
            if row is not None and mark is None and not has_margin_marks and re.fullmatch(r"\d{1,2}", row.plain):
                box = innermost(q)
                if box.rows and box.marks is None and int(row.plain) <= 40:
                    mark, row = int(row.plain), None
            if row is not None:
                label, rest = _strip_label(row, PART)
                cur_part = q.parts[-1] if q.parts else None
                if label is not None:
                    expected = chr(ord(cur_part.label) + 1) if cur_part and cur_part.label else "a"
                    if label == "i" and cur_part is not None and not cur_part.children and expected != "i":
                        label = None  # '(i)' here is a sub-part
                    elif label != expected:
                        label = None
                if label is not None:
                    box = _Box(label)
                    q.parts.append(box)
                    row = rest
                else:
                    sub, rest = _strip_label(row, SUBPART)
                    if sub is not None:
                        if cur_part is None:  # sub-parts directly under the question
                            cur_part = _Box("")
                            q.parts.append(cur_part)
                        expected = ROMANS[len(cur_part.children)] if len(cur_part.children) < len(ROMANS) else None
                        if sub == expected:
                            cur_part.children.append(_Box(sub))
                            row = rest
                box = innermost(q)
                if row is not None:
                    box.rows.append(row)
                    timeline.append((row.page, row.y0, box))
                else:
                    timeline.append((page.number, 0.0, box))
            box = innermost(q)
            if mark is not None:
                if box.marks is None:
                    box.marks = mark
                else:
                    box.issues.append(f"Two marks values ({box.marks} and {mark}) were found for one part.")
    close_mcq()
    close_q()

    # figures belong to the box that was active just above them
    for fig in figures:
        owner = None
        for pg, y, box in timeline:
            if (pg, y) <= (fig.page, fig.rect[1] + 2):
                owner = box
        if owner is not None:
            owner.figures.append(fig)

    for m in mcqs:
        res.units.append(_mcq_unit(m, figures))
    for qq in questions:
        res.units.extend(_question_units(qq, timeline))
    # expected counts per section (sources-01 point 5)
    for s in res.sections:
        if s.mode == "mcq" and s.expected:
            exp = s.expected[1] - s.expected[0] + 1
            if s.detected_mcq != exp:
                msg = f"Section {s.name}: detected {s.detected_mcq} of {exp} multiple-choice questions ({s.expected[0]}–{s.expected[1]})."
                res.warnings.append(msg)
                for u in res.units:
                    if u.section == "mcq" and u.section_name == s.name:
                        u.issues.append(msg)
        elif s.mode == "written" and s.expected and not s.choose:
            exp = set(range(s.expected[0], s.expected[1] + 1))
            missing = sorted(exp - s.detected_questions)
            if missing:
                res.warnings.append(f"Section {s.name}: questions {', '.join(map(str, missing))} were not detected.")
    _cover_expectations(res)
    res.units.sort(key=lambda u: (u.page, _num_key(u.number)))
    return res


def _num_key(label: str) -> tuple:
    m = re.match(r"(\d+)", label)
    return (int(m.group(1)) if m else 0, label)


def _tok_like(row_or_tok, text: str):
    from app.ingestion.layout import Tok

    t = row_or_tok.toks[0] if isinstance(row_or_tok, Row) else row_or_tok
    return Tok(text, t.x0, t.y0, max(t.x1, t.x0 + 5 * len(text)), t.y1, t.size)


def _drop_figure_tokens(row: Row, figs: list[Figure]) -> Row | None:
    if not figs:
        return row
    drop = [t for t in row.toks if any(f.contains(t) for f in figs)]
    if not drop:
        return row
    return row.without(drop)


def _mcq_row(m: _MCQ, row: Row, figs: list[Figure]) -> None:
    """Assign a row's tokens to the stem or to options A–D (in order, by position)."""
    current: list | None = m.options[-1] if m.options else None
    stem_toks = []
    for t in row.toks:
        s = t.text.strip()
        lm = OPT_LABEL.match(s)
        expected = "ABCD"[len(m.options)] if len(m.options) < 4 else None
        if lm and lm.group(1) == expected:
            current = [expected, (lm.group(2) or "").strip(), row.page, row.y0, t.x0]
            m.options.append(current)
            continue
        if any(f.contains(t, pad=0) for f in figs):
            continue  # a label inside a graph option
        if current is None:
            stem_toks.append(t)
        else:
            current[1] = (current[1] + " " + s).strip()
    if stem_toks:
        m.stem_rows.append(Row(row.page, stem_toks, row.width, row.height))


def _mcq_unit(m: _MCQ, figures: list[Figure]) -> Unit:
    sec = m.section
    stem = _join(m.stem_rows)
    u = Unit(number=str(m.number), text=stem, marks=1, page=m.page, section="mcq", question=str(m.number),
             section_name=sec.name if sec else None, section_title=sec.title if sec else None, stem=stem, issues=list(m.issues))
    u.keys = [str(m.number)]
    graph = bool(m.options) and all(not o[1] for o in m.options)
    u.graph_options = graph
    u.options = [f"{o[0]}. {o[1]}" if o[1] else f"{o[0]}. (graph {o[0]} — see the image)" for o in m.options]
    if len(m.options) != 4:
        u.issues.append(f"Multiple-choice question {m.number} has {len(m.options)} option(s); 4 are expected.")
    elif any(not o[1] for o in m.options) and not graph:
        u.issues.append(f"An option of question {m.number} has no text.")
    by_page: dict[int, list[float]] = {}
    for r in m.rows:
        lo, hi = by_page.get(r.page, [r.y0, r.y1])
        by_page[r.page] = [min(lo, r.y0), max(hi, r.y1)]
    if m.rows:
        width = m.rows[0].width
        for pg, (lo, hi) in by_page.items():
            figs = [f for f in figures if f.page == pg and f.rect[1] >= lo - 4 and f.rect[1] <= hi + 4]
            for f in figs:
                hi = max(hi, f.rect[3])
                u.figure_regions.append((pg, f.rect))
            u.regions.append((pg, (0.06 * width, lo - 4, width - 0.04 * width, hi + 6)))
    u.has_visual = bool(u.figure_regions)
    return u


def _box_text(b: _Box) -> str:
    return _join(b.rows)


def _box_marks(b: _Box) -> int | None:
    if b.children:
        vals = [c.marks for c in b.children]
        if any(v is None for v in vals):
            return None if b.marks is None else b.marks
        return sum(vals)
    return b.marks


def _question_units(q: _Question, timeline) -> list[Unit]:
    sec = q.section
    n = str(q.number)
    stem = _box_text(q.stem)
    base = dict(page=q.page, section="written", question=n, section_name=sec.name if sec else None,
                section_title=(sec.title if sec else None) or None, question_title=q.title, heading_marks=q.heading_marks, stem=stem)
    units: list[Unit] = []
    groups: list[list[_Box]] = []
    if not q.parts:
        u = Unit(number=n, text=stem, marks=q.stem.marks if q.stem.marks is not None else q.heading_marks, **base)
        u.keys = [n]
        u.issues += q.stem.issues
        if q.stem.marks is not None and q.heading_marks is not None and q.stem.marks != q.heading_marks:
            u.issues.append(f"The margin shows {q.stem.marks} marks but the heading says {q.heading_marks}.")
        _regions(u, [q.stem], timeline)
        units.append(u)
    else:
        for p in q.parts:
            if groups and not q.either_or and HENCE.match(_box_text(p)) and p.label:
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            labels = [p.label for p in g if p.label]
            number = n + (f"({labels[0]})" if len(labels) == 1 else (f"({labels[0]})–({labels[-1]})" if labels else ""))
            lines: list[str] = []
            if stem and not q.either_or:
                lines.append(stem)
            elif stem and q.either_or and not re.match(r"^Answer EITHER", stem, re.I):
                lines.append(stem)
            sub: list[SubPart] = []
            keys: list[str] = []
            issues: list[str] = []
            multi = len(g) > 1
            for p in g:
                pkey = n + (f"({p.label})" if p.label else "")
                ptext = _box_text(p)
                head = f"({p.label}) " if (multi and p.label) else ""
                if p.children:
                    if ptext or head:
                        lines.append((head + ptext).strip())
                    for c in p.children:
                        ctext = _box_text(c)
                        lines.append(f"({c.label}) {ctext}" + (f" ({c.marks} mark{'s' if c.marks != 1 else ''})" if c.marks else ""))
                        lab = (f"({p.label})" if (multi and p.label) else "") + f"({c.label})"
                        sub.append(SubPart(lab, f"{pkey}({c.label})", ctext, c.marks, bool(HENCE.match(ctext))))
                        keys.append(f"{pkey}({c.label})")
                        if c.marks is None:
                            issues.append(f"No mark was found for {pkey}({c.label}).")
                        issues += c.issues
                    if p.marks is not None:
                        issues.append(f"A mark ({p.marks}) sits on the stem of {pkey} as well as on its sub-parts.")
                else:
                    lines.append(head + ptext + (f" ({p.marks} mark{'s' if p.marks != 1 else ''})" if multi and p.marks else ""))
                    if multi:
                        sub.append(SubPart(f"({p.label})", pkey, ptext, p.marks, bool(HENCE.match(ptext))))
                keys.append(pkey)
                issues += p.issues
            marks_vals = [_box_marks(p) for p in g]
            if q.either_or:
                marks = q.heading_marks if q.heading_marks is not None else (marks_vals[0] if marks_vals else None)
                if marks_vals and marks_vals[0] is not None and q.heading_marks is not None and marks_vals[0] != q.heading_marks:
                    issues.append(f"The margin shows {marks_vals[0]} marks but the heading says {q.heading_marks}.")
            elif any(v is None for v in marks_vals):
                marks = None
                if not any("No mark was found" in i for i in issues):
                    issues.append(f"No mark was found for {number}.")
            else:
                marks = sum(marks_vals)
            u = Unit(number=number, text="\n\n".join(x for x in lines if x), marks=marks, parts=sub, keys=keys, issues=issues, **base)
            if q.either_or:
                u.alternative_group = n
            _regions(u, g, timeline)
            units.append(u)
        if not q.either_or and q.heading_marks is not None:
            total = sum((u.marks or 0) for u in units)
            if all(u.marks is not None for u in units) and total != q.heading_marks:
                for u in units:
                    u.issues.append(f"The parts of Question {n} add to {total} marks but the heading says {q.heading_marks}.")
    for u in units:
        u.stimulus_refs = sorted({int(x) for m in TEXT_REFS.finditer(u.text) for x in re.findall(r"\d{1,2}", m.group(1))})
        if u.marks is None and not any("No mark" in i for i in u.issues):
            u.issues.append(f"No mark was found for {u.number}.")
    return units


def _all_boxes(b: _Box) -> list[_Box]:
    return [b, *[x for c in b.children for x in _all_boxes(c)]]


def _regions(u: Unit, boxes: list[_Box], timeline) -> None:
    mine = {id(x) for b in boxes for x in _all_boxes(b)}
    by_page: dict[int, list[float]] = {}
    width = None
    for b in boxes:
        for x in _all_boxes(b):
            for r in x.rows:
                width = width or r.width
                lo, hi = by_page.get(r.page, [r.y0, r.y1])
                by_page[r.page] = [min(lo, r.y0), max(hi, r.y1)]
            for f in x.figures:
                lo, hi = by_page.get(f.page, [f.rect[1], f.rect[3]])
                by_page[f.page] = [min(lo, f.rect[1]), max(hi, f.rect[3])]
                u.figure_regions.append((f.page, f.rect))
    width = width or 595.0
    u.regions = [(pg, (0.06 * width, lo - 5, width - 0.04 * width, hi + 6)) for pg, (lo, hi) in sorted(by_page.items())]
    if u.regions:
        u.page = u.regions[0][0]
    u.has_visual = bool(u.figure_regions)
    del mine


def _cover_expectations(res: SegmentResult) -> None:
    """Fill missing section expectations from the cover ('Section I – 10 marks', 'Attempt
    Questions 1–10')."""
    cur = None
    cover: dict[str, dict] = {}
    for line in res.cover:
        m = SECTION.match(line)
        if m:
            cur = m.group(1).upper()
            cover[cur] = {}
            mk = re.search(r"(\d{1,3})\s*marks", line, re.I)
            if mk:
                cover[cur]["marks"] = int(mk.group(1))
            continue
        if cur:
            for pat in (ATTEMPT_RANGE, ATTEMPT_ONE):
                mm = pat.search(line)
                if mm:
                    a = int(mm.group(1))
                    b = int(mm.group(2)) if pat is ATTEMPT_RANGE else a
                    cover[cur].setdefault("expected", (a, b))
    for s in res.sections:
        info = cover.get(s.name) or {}
        if s.expected is None and info.get("expected"):
            s.expected = info["expected"]
        if s.marks is None and info.get("marks"):
            s.marks = info["marks"]


def segment_pdf(path) -> tuple[SegmentResult, Layout]:
    from app.ingestion.layout import read_layout

    lay = read_layout(path)
    return segment_layout(lay), lay
