from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LegalEvidence, LegalEvidenceTopic, Subject, SyllabusTopic
from app.routes.common import render, templates
from app.services import legal_evidence as le
from app.services import legal_plan as lp
from app.services import settings as st

router = APIRouter()


def legal_topics_pending() -> bool:
    """Template global for the dashboard notice (v2-legal-logic, owner request): True until the
    student has answered 'Which Legal topics have you started?'. Never breaks a page."""
    from app.db import SessionLocal

    try:
        db = SessionLocal()
        try:
            return lp.topics_pending(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - a notice must never stop the dashboard rendering
        return False


templates.env.globals["legal_topics_pending"] = legal_topics_pending
TYPES = ["legislation", "case", "law_reform", "report", "inquiry", "treaty", "media", "issue"]


@router.get("/legal-evidence")
def bank(request: Request, topic: str = "", item_type: str = "", q: str = "", db: Session = Depends(get_db)):
    stmt = select(LegalEvidence).order_by(LegalEvidence.item_type, LegalEvidence.title)
    if topic.isdigit():
        stmt = stmt.join(LegalEvidenceTopic).where(LegalEvidenceTopic.topic_id == int(topic))
    if item_type:
        stmt = stmt.where(LegalEvidence.item_type == item_type)
    items = db.execute(stmt).scalars().unique().all()
    if q:
        items = [i for i in items if q.lower() in (i.title + i.summary + (i.issue or "")).lower()]
    legal = db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()
    topics = db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == legal.id).order_by(SyllabusTopic.position)).scalars().all()
    tnames = {t.id: t.name for t in topics}
    picker = lp.picker(db)
    return render(request, "legal.html", items=items, topics=topics, tnames=tnames, types=TYPES, f=request.query_params,
                  picker=picker if picker["pending"] else None, picker_next="/legal-evidence", msg=request.query_params.get("msg"))


@router.post("/legal-evidence/add")
def add(db: Session = Depends(get_db), title: str = Form(...), item_type: str = Form("media"), date: str = Form(""), jurisdiction: str = Form("NSW"),
        issue: str = Form(""), summary: str = Form(...), legal_significance: str = Form(""), syllabus_link: str = Form(""), source: str = Form(""),
        source_url: str = Form(""), topic_ids: list[int] = Form([]), verified: int = Form(0)):
    le.add_manual(db, {"title": title, "item_type": item_type, "date": date or None, "jurisdiction": jurisdiction, "issue": issue or None,
                       "summary": summary, "legal_significance": legal_significance, "syllabus_link": syllabus_link or None, "source": source or None,
                       "source_url": source_url or None, "verified": bool(verified)}, topic_ids)
    db.commit()
    return RedirectResponse("/legal-evidence", status_code=303)


@router.post("/legal-evidence/fetch")
def fetch(db: Session = Depends(get_db), url: str = Form(...), topic_ids: list[int] = Form([])):
    le.add_from_url(db, url, topic_ids, st.all_settings(db))
    db.commit()
    return RedirectResponse("/legal-evidence", status_code=303)


@router.post("/legal-evidence/{eid}/verify")
def verify(eid: int, db: Session = Depends(get_db)):
    le.mark_verified(db, db.get(LegalEvidence, eid))
    db.commit()
    return RedirectResponse(f"/legal-evidence#ev{eid}", status_code=303)


@router.post("/legal-evidence/{eid}/delete")
def delete(eid: int, db: Session = Depends(get_db)):
    db.delete(db.get(LegalEvidence, eid))
    db.commit()
    return RedirectResponse("/legal-evidence", status_code=303)
