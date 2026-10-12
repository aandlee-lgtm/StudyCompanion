"""Validation gates for imported questions (sources-04/10/13, english-11, legal-12).

``validate_question`` lists every problem with a question as it stands now (it is recomputed
after each edit, so fixing a field clears its issue). Blocking issues stop approval — by the
reviewer and, a fortiori, automatic approval. ``auto_approval_blockers`` adds the extra
conditions for approving without a human."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.mapping import detect_verb
from app.models import LearningPlanItem, Question, Stimulus
from app.models.common import ADAPTABLE, DIRECT, PARTIAL, REJECT
from app.models.ingestion import QuestionStimulus

INSTRUCTION = re.compile(r"^(Section\s+[IVX]+\b|Attempt (Questions?|ALL|ONE|TWO)\b|Allow about\b|Answer EITHER\b|Use the (multiple-choice|Question)\b|"
                         r"Question \d+ continues\b|End of (Question|paper|section)\b|Office Use Only|\d+\s*marks?$|Reading time\b|Working time\b|"
                         r"General Instructions\b|Total marks\b|Extra writing booklets\b|Answer the question in\b)", re.I)
TEXT_REF = re.compile(r"\bTexts?\s+(\d{1,2}(?:\s*(?:,|and|&)\s*\d{1,2})*)", re.I)
MAX_MARKS = {"MATHS": 20, "ENGLISH": 20, "LEGAL": 25}


@dataclass
class Issue:
    code: str
    message: str
    blocking: bool = True
    field: str | None = None

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "blocking": self.blocking, "field": self.field}


def text_refs(text: str) -> list[int]:
    return sorted({int(x) for m in TEXT_REF.finditer(text or "") for x in re.findall(r"\d{1,2}", m.group(1))})


def linked_stimuli(db: Session, q: Question) -> list[tuple[str | None, Stimulus]]:
    rows = db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id == q.id).order_by(QuestionStimulus.position)).scalars().all()
    out = [(r.label, r.stimulus) for r in rows if r.stimulus is not None]
    if not out and q.stimulus is not None:
        out = [(None, s) for s in q.stimulus.reading_set()]
    return out


def validate_question(db: Session, q: Question, subject_code: str | None = None) -> list[Issue]:
    from app.models import Subject

    code = subject_code or db.get(Subject, q.subject_id).code
    meta = q.import_meta or {}
    issues: list[Issue] = []
    text = (q.question_text or "").strip()
    words = re.findall(r"[A-Za-z]{2,}", text)
    # ---- the text is a real question, not an instruction, heading or fragment
    if q.question_type == "mcq" and meta.get("graph_options"):
        if len(words) < 3:
            issues.append(Issue("text_short", "The question stem is too short to be a question.", field="question_text"))
    elif len(words) < 4:
        issues.append(Issue("text_short", "The text has fewer than four words: it is probably a fragment, not a question.", field="question_text"))
    first_line = text.splitlines()[0] if text else ""
    if INSTRUCTION.match(first_line):
        issues.append(Issue("instruction", f"The text starts like an exam instruction or heading ('{first_line[:50]}').", field="question_text"))
    if text and "?" not in text and not detect_verb(text) and q.question_type != "mcq":
        issues.append(Issue("no_directive", "No directive verb (Explain, Find, Evaluate …) or question mark was found.", field="question_text"))
    # ---- marks
    if meta.get("marks_missing"):
        issues.append(Issue("marks_missing", "No mark was found in the paper for this question: enter the marks.", field="marks"))
    if not q.marks or q.marks < 1 or q.marks > MAX_MARKS.get(code, 25):
        issues.append(Issue("marks_range", f"Marks must be between 1 and {MAX_MARKS.get(code, 25)}.", field="marks"))
    if q.parts:
        if any(p.marks is None or p.marks < 1 for p in q.parts):
            issues.append(Issue("part_marks", "Every part needs its marks.", field="parts"))
        elif sum(p.marks for p in q.parts) != q.marks:
            issues.append(Issue("parts_sum", f"The parts add to {sum(p.marks for p in q.parts)} marks but the question is worth {q.marks}.", field="marks"))
    if meta.get("segment_issues") and not meta.get("segment_ack"):
        for s in meta["segment_issues"]:
            issues.append(Issue("segmentation", s + " Check it against the PDF, fix it, then tick 'Segmentation checked'.", field="segment_ack"))
    # ---- multiple choice
    if q.question_type == "mcq":
        if len(q.options or []) != 4:
            issues.append(Issue("mcq_options", f"A multiple-choice question needs exactly 4 options (found {len(q.options or [])}).", field="options"))
        ans = (q.answer or {}).get("value") if (q.answer or {}).get("type") == "mcq" else None
        if not ans or str(ans).upper() not in ("A", "B", "C", "D"):
            issues.append(Issue("mcq_key", "No answer key: choose the correct letter (A–D).", field="answer"))
    # ---- mapping: never approve without a subtopic
    if not q.plan_item_id or meta.get("mapping_state") == "UNMAPPED":
        issues.append(Issue("unmapped", "UNMAPPED: choose the learning-plan subtopic this question belongs to.", field="plan_item_id"))
    else:
        item = db.get(LearningPlanItem, q.plan_item_id)
        if item is None or item.subject_id != q.subject_id:
            issues.append(Issue("mapping_subject", "The chosen subtopic belongs to another subject.", field="plan_item_id"))
    # ---- relevance
    if q.is_extension or q.relevance_status == REJECT:
        issues.append(Issue("rejected_content", "Extension or rejected content is never added to the pool.", field="relevance"))
    elif q.relevance_status == ADAPTABLE and q.historical_or_generated != "ADAPTED":
        issues.append(Issue("needs_adaptation", "ADAPTABLE questions are never served as written: use 'Adapt' to create an adapted copy.", field="relevance"))
    elif q.relevance_status == PARTIAL and not (meta.get("kept_parts") or meta.get("text_edited")) and q.historical_or_generated != "ADAPTED":
        issues.append(Issue("partial", "PARTIAL: choose which parts to keep (or edit the text) before approval.", field="relevance"))
    # ---- English: unseen questions need their texts
    if code == "ENGLISH":
        if q.category not in ("unseen", "course"):
            issues.append(Issue("category", "Choose the English category: unseen text or course-linked.", field="category"))
        linked = linked_stimuli(db, q)
        labels = {(lab or "").lower() for lab, _ in linked}
        if q.category == "unseen" and not linked:
            issues.append(Issue("stimulus_missing", "An unseen-text question needs its text: link or create the stimulus.", field="stimulus"))
        missing = [n for n in text_refs(text) if f"text {n}" not in labels]
        if missing and not (len(linked) >= len(text_refs(text)) and not any(labels)):
            issues.append(Issue("stimulus_refs", "The question refers to " + ", ".join(f"Text {n}" for n in missing) + " but it is not linked.", field="stimulus"))
        for _, s in linked:
            if not (s.attribution or "").strip():
                issues.append(Issue("attribution", f"'{s.title}' has no attribution.", field="stimulus"))
    # ---- Legal: fact currency (section 8C)
    if code == "LEGAL":
        cur = q.legal_fact_currency or "check"
        if cur == "outdated" and q.historical_or_generated != "ADAPTED":
            issues.append(Issue("legal_outdated", "The legal facts are outdated: adapt the question (with an adaptation note) instead of approving it.", field="legal_fact_currency"))
        elif cur == "check":
            issues.append(Issue("legal_check", "Legal fact currency is 'check': confirm the law is current (set it to 'current') before approval.", field="legal_fact_currency"))
    # ---- non-blocking warnings
    for g in q.parts:
        gm = (g.meta or {}).get("guideline_top_mark")
        if gm is not None and g.marks and gm != g.marks:
            issues.append(Issue("guideline_marks", f"The guideline for {g.label} tops out at {gm} marks but the part is worth {g.marks}.", blocking=False))
    gm = meta.get("guideline_top_mark")
    if gm is not None and q.marks and gm != q.marks and not q.parts:
        issues.append(Issue("guideline_marks", f"The guideline tops out at {gm} marks but the question is worth {q.marks}.", blocking=False))
    if meta.get("duplicate_of"):
        issues.append(Issue("duplicate", f"Looks like a duplicate of question {meta['duplicate_of']}.", blocking=False))
    if q.question_type == "mcq" and meta.get("graph_options") and not q.question_image:
        issues.append(Issue("graph_crop", "The graph options have no cropped image.", field="question_image"))
    return issues


def blocking(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.blocking]


def auto_approval_blockers(db: Session, q: Question, *, mapped_by: str, subtopic_cited: bool, confidence: float, threshold: float,
                           tier: int, subject_code: str) -> list[str]:
    """Reasons a question may not be approved automatically (empty list = auto-approve)."""
    out = [i.message for i in blocking(validate_question(db, q, subject_code))]
    if mapped_by != "ai":
        out.append("Mapped offline: a person must review it.")
    if not subtopic_cited:
        out.append("The AI did not cite a valid subtopic.")
    if confidence < threshold:
        out.append(f"Mapping confidence {confidence:.2f} is below {threshold:.2f}.")
    if q.relevance_status != DIRECT:
        out.append(f"Relevance is {q.relevance_status}, not DIRECT.")
    if tier not in (1, 2):
        out.append("Only NESA sources (tier 1–2) are approved automatically.")
    if subject_code == "LEGAL" and q.legal_fact_currency != "current":
        out.append("Legal fact currency is not 'current'.")
    return out
