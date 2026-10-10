"""Heuristic question-boundary detection for NESA-style papers.

Automated parsing will not always be right, so every imported question goes through the
review queue unless its mapping is DIRECT with high confidence."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.pdf import Extracted

Q_HEAD = re.compile(r"^\s*Question\s+(\d{1,2})\b(.*)$", re.I)
PART = re.compile(r"^\s*\(([a-h])\)\s*(.*)$")
SUBPART = re.compile(r"^\s*\((i{1,3}|iv|v|vi)\)\s*(.*)$")
MARKS_INLINE = re.compile(r"\((\d{1,2})\s*marks?\)", re.I)
MARK_LINE = re.compile(r"^\s*(\d{1,2})\s*$")
MCQ_START = re.compile(r"^\s*(\d{1,2})\s{1,4}(\S.*)$")
OPTION = re.compile(r"^\s*([A-D])\.?\s+(.*)$")
NOISE = re.compile(r"(^\s*–\s*\d+\s*–\s*$)|(^\s*Office Use Only)|(^\s*BLANK PAGE)|(^\s*©)|(^\s*\d{4} HIGHER SCHOOL CERTIFICATE)", re.I)


@dataclass
class Segment:
    number: str  # "11(a)", "3"
    text: str
    marks: int | None
    page: int
    section: str  # "mcq" | "written"
    options: list[str] = field(default_factory=list)
    has_visual: bool = False


def _clean(lines: list[str]) -> list[str]:
    return [l.rstrip() for l in lines if not NOISE.search(l)]


def segment(doc: Extracted) -> list[Segment]:
    segs: list[Segment] = []
    cur: Segment | None = None
    section = "mcq"
    visual_pages = {p.number for p in doc.pages if p.image_count or p.drawing_count > 15}

    def flush():
        nonlocal cur
        if cur and cur.text.strip():
            m = MARKS_INLINE.search(cur.text)
            if m and cur.marks is None:
                cur.marks = int(m.group(1))
            cur.text = re.sub(r"\n{3,}", "\n\n", cur.text).strip()
            cur.has_visual = cur.page in visual_pages
            segs.append(cur)
        cur = None

    q_num = None
    for page in doc.pages:
        for line in _clean(page.text.splitlines()):
            if re.match(r"^\s*Section\s+II", line, re.I):
                flush()
                section = "written"
                continue
            h = Q_HEAD.match(line)
            if h:
                flush()
                section = "written"
                q_num = h.group(1)
                rest = h.group(2).strip(" .:()–-")
                if rest and not re.match(r"^\(?\d+ marks?\)?$", rest, re.I) and "continue" not in rest.lower():
                    cur = Segment(q_num, rest + "\n", None, page.number, section)
                continue
            if section == "written" and q_num:
                p = PART.match(line)
                if p:
                    flush()
                    cur = Segment(f"{q_num}({p.group(1)})", p.group(2) + "\n", None, page.number, section)
                    continue
                mk = MARK_LINE.match(line)
                if mk and cur is not None and cur.marks is None and int(mk.group(1)) <= 20:
                    cur.marks = int(mk.group(1))
                    continue
                if cur is None:
                    cur = Segment(q_num, "", None, page.number, section)
                cur.text += line + "\n"
                continue
            # Section I multiple choice
            o = OPTION.match(line)
            if o and cur is not None and cur.section == "mcq":
                cur.options.append(f"{o.group(1)}. {o.group(2).strip()}")
                continue
            m = MCQ_START.match(line)
            if m and (cur is None or len(cur.options) >= 4 or cur.section != "mcq") and int(m.group(1)) <= 30:
                flush()
                cur = Segment(m.group(1), m.group(2) + "\n", 1, page.number, "mcq")
                continue
            if cur is not None:
                if cur.section == "mcq" and cur.options and not o:
                    cur.options[-1] += " " + line.strip()
                else:
                    cur.text += line + "\n"
    flush()
    return [s for s in segs if len(s.text) > 8]


def split_guideline(text: str) -> dict[str, str]:
    """Split a marking-guideline document into {question number: text}."""
    out: dict[str, str] = {}
    cur_key, buf = None, []
    for line in text.splitlines():
        m = re.match(r"^\s*Question\s+(\d{1,2})\s*(\(([a-h])\))?", line, re.I)
        if m:
            if cur_key:
                out[cur_key] = "\n".join(buf).strip()
            cur_key = m.group(1) + (f"({m.group(3)})" if m.group(3) else "")
            buf = [line]
        elif cur_key:
            buf.append(line)
    if cur_key:
        out[cur_key] = "\n".join(buf).strip()
    return out
