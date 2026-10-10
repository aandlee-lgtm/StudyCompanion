"""Legal Studies specifics for written marking: evidence from the bank, citation checks,
'current information checked' and the disclaimer."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import MarkingResult
from app.models import LegalEvidence, LegalEvidenceTopic, Question

DISCLAIMER = "Legal Studies feedback is for education only and is not legal advice."

def evidence_for(db: Session, q: Question) -> list[dict]:
    if not q.topic_id:
        return []
    rows = db.execute(select(LegalEvidence).join(LegalEvidenceTopic).where(LegalEvidenceTopic.topic_id == q.topic_id)).scalars().all()
    return [{"title": e.title, "type": e.item_type, "date": e.date, "jurisdiction": e.jurisdiction, "summary": e.summary,
             "significance": e.legal_significance, "source_url": e.source_url,
             "verified": e.last_verified_date.isoformat() if e.last_verified_date else "UNVERIFIED"} for e in rows]


CITATION = re.compile(r"\b([A-Z][A-Za-z()'’,\- ]{2,80}? Act \d{4}(?: \([A-Za-z]+\))?|[A-Z][A-Za-z]+ v (?:The )?[A-Z][A-Za-z]+(?: \(No \d\))?)")


def unverified_citations(text: str, evidence: list[dict]) -> list[str]:
    known = " ".join(e["title"] for e in evidence).lower()
    out = []
    for m in CITATION.findall(text or ""):
        name = m.strip()
        core = re.sub(r"\s*\(.*?\)\s*$", "", name).lower()
        if core and core not in known and name not in out:
            out.append(name)
    return out


def post_process(db: Session, q: Question, ctx: dict, result: MarkingResult, payload: dict, method: str) -> None:
    """Add Legal-only fields to the feedback payload (called by written.mark_written)."""
    ev = ctx["evidence"]
    model = payload.get("model_answer") or ""
    verified = [e["verified"] for e in ev if e["verified"] != "UNVERIFIED"]
    payload["facts_checked"] = max(verified) if verified else None
    all_text = " ".join([model, result.improved_argument, " ".join(result.evidence_suggestions), result.improved_answer])
    payload["unverified_references"] = unverified_citations(all_text, ev) if method == "ai" else []
    payload["evidence"] = ev
    payload["disclaimer"] = DISCLAIMER


def why_lost(q: Question, p: dict, attempt) -> str | None:
    """Legal-specific offline explanation; None falls back to the generic written explainer."""
    return None
