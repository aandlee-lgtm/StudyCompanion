"""The auditability line under every question (sources-19), built from structured fields:

    Source: NESA 2025 HSC Mathematics Advanced Q11(d), p. 7 · 2027 mapping: Integral calculus —
    3G The trapezoidal rule · Outcome: MA12-7 · Relevance: Direct (reviewed 10 Oct 2026)

It never shows answers, guidelines or internal mapping jargon, so it is safe under an unanswered
question."""
from __future__ import annotations

import re
from datetime import date

from sqlalchemy.orm import object_session

from app.models.common import ORIGIN_ADAPTED, ORIGIN_GENERATED, ORIGIN_LABELS, ORIGIN_TRIAL

_INTERNAL = re.compile(r"\s*\((?:AI mapping failed|The AI (?:did not|named only)|Extension content was detected)[^)]*\)\s*|"
                       r"\b(?:offline keyword (?:proposal|match(?:es)?)|keyword score[^.;]*|confirm it\.?|needs? human review\.?)", re.I)


def _title_with_year(title: str, year: int | None) -> str:
    if year and str(year) not in (title or ""):
        return f"{title} {year}"
    return title or "Unknown source"


def clean_reason(text: str | None) -> str:
    """Mapping reasons are written for the reviewer; strip the internal phrases for the student."""
    t = _INTERNAL.sub(" ", text or "")
    t = re.sub(r"\s{2,}", " ", t).strip(" ;,")
    return t


def _fmt(d) -> str:
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return d
    return f"{d.day} {d.strftime('%b %Y')}" if d else ""


def audit_info(q, item=None, mapping=None) -> dict:
    db = object_session(q)
    meta = q.import_meta or {}
    item, mapping = item or None, mapping or None  # Jinja passes Undefined when the caller has none
    if item is None and q.plan_item_id and db is not None:
        from app.models import LearningPlanItem

        item = db.get(LearningPlanItem, q.plan_item_id)
    if mapping is None and q.mappings:
        mapping = q.mappings[-1]
    label = f" Q{q.question_number}" if q.question_number else ""
    page = f", p. {q.source_page}" if q.source_page else ""
    src = q.source
    origin = q.historical_or_generated
    if origin == ORIGIN_ADAPTED and meta.get("adaptation"):
        source = f"Adapted from {meta['adaptation'].get('from_label')}"
    elif origin == ORIGIN_GENERATED:
        source = "GENERATED practice question" + (f" ({src.title})" if src and src.title else "")
    else:
        source = _title_with_year(src.title if src else "", q.source_year) + label + page
        if origin == ORIGIN_TRIAL:
            source += " · TRIAL / NON-NESA"
    topic = item.topic.name if item is not None and item.topic is not None else None
    subtopic = f"{item.code} {item.title}" if item is not None else None
    mapping_txt = " — ".join(x for x in [topic, subtopic] if x) or "not mapped"
    outcome = None
    if q.syllabus_outcome_id and db is not None:
        from app.models import SyllabusOutcome

        o = db.get(SyllabusOutcome, q.syllabus_outcome_id)
        outcome = o.code if o is not None else None
    reviewed = meta.get("reviewed_on")
    rel = (q.relevance_status or "").capitalize()
    relevance = rel + (f" (reviewed {_fmt(reviewed)})" if reviewed else (" (approved automatically)" if q.approved and meta else ""))
    rationale = meta.get("student_rationale") or clean_reason(mapping.mapping_reason if mapping is not None else "")
    pdf = f"/sources/{src.id}/pdf" if src is not None and src.local_file else None
    return {"source": source, "origin_label": ORIGIN_LABELS.get(origin, origin), "mapping": mapping_txt, "outcome": outcome,
            "relevance": relevance, "rationale": rationale or None, "pdf": pdf, "legal_currency": q.legal_fact_currency,
            "facts_checked_on": _fmt(q.facts_checked_on) if q.facts_checked_on else None}


def audit_text(q, item=None, mapping=None) -> str:
    a = audit_info(q, item, mapping)
    bits = [f"Source: {a['source']}", f"2027 mapping: {a['mapping']}"]
    if a["outcome"]:
        bits.append(f"Outcome: {a['outcome']}")
    bits.append(f"Relevance: {a['relevance']}")
    return " · ".join(bits)
