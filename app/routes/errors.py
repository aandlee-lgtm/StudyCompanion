"""Error journal page (owner: adaptive; adaptive-11/12): patterns panel with interpretation and a
'Practise this' action, both axes (error type and topic tag), local study dates, resolution details,
full counts and pagination."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ErrorJournal
from app.routes.common import render
from app.services import clock, error_journal, revision
from app.services import settings as st

router = APIRouter()
PAGE_SIZE = 50
SUBJECTS = ("MATHS", "ENGLISH", "LEGAL")


def _today(db: Session):
    return clock.today(st.get(db, "timezone"))


def _key_filter(key: str):
    return or_(ErrorJournal.topic_tag == key, and_(ErrorJournal.topic_tag.is_(None), ErrorJournal.category == key))


@router.get("/errors")
def errors(request: Request, subject: str = "", show_resolved: int = 0, key: str = "", page: int = 1, none: int = 0,
           db: Session = Depends(get_db)):
    subject = subject if subject in SUBJECTS else ""
    today = _today(db)
    conds = []
    if subject:
        conds.append(ErrorJournal.subject_code == subject)
    if key:
        conds.append(_key_filter(key))
    if not show_resolved:
        conds.append(ErrorJournal.resolved.is_(False))
    total = db.execute(select(func.count(ErrorJournal.id)).where(*conds)).scalar_one()
    pages = max(1, -(-total // PAGE_SIZE))
    page = max(1, min(page, pages))
    entries = db.execute(select(ErrorJournal).where(*conds).order_by(ErrorJournal.study_date.desc(), ErrorJournal.id.desc())
                         .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).scalars().all()
    # full counts of open entries on both axes (not just the top few)
    open_conds = [ErrorJournal.resolved.is_(False)] + ([ErrorJournal.subject_code == subject] if subject else [])
    counts = db.execute(select(ErrorJournal.subject_code, ErrorJournal.category, ErrorJournal.topic_tag, func.count(ErrorJournal.id))
                        .where(*open_conds).group_by(ErrorJournal.subject_code, ErrorJournal.category, ErrorJournal.topic_tag)
                        .order_by(func.count(ErrorJournal.id).desc())).all()
    open_total = sum(n for *_, n in counts)
    patterns = error_journal.patterns(db, today, subject)
    return render(request, "errors.html", entries=entries, counts=counts, open_total=open_total, total=total, page=page, pages=pages,
                  subject=subject, show_resolved=show_resolved, key=key, patterns=patterns, today=today, none=none)


@router.get("/errors/practise")
def practise(subject: str = "", key: str = "", db: Session = Depends(get_db)):
    """'Practise this' on a pattern: a fresh, servable question on the skill where the error occurs."""
    today = _today(db)
    p = next((p for p in error_journal.patterns(db, today, subject, limit=50) if p["key"] == key), None)
    back = f"/errors?subject={subject}&key={key}&none=1"
    if p is None:
        return RedirectResponse(back, status_code=303)
    seen = set(p["example_ids"])
    plan_ids = [t["id"] for t in p["topics"]] or ([p["plan_item_id"]] if p["plan_item_id"] else [])
    ctx = revision._context(db, today) if plan_ids else None
    for pid in plan_ids:
        q = revision.pick_question(db, pid, today, tag=key, exclude=seen, ctx=ctx)
        if q is not None:
            return RedirectResponse(f"/practice/{q.id}", status_code=303)
    return RedirectResponse(back, status_code=303)


@router.post("/errors/{eid}/resolve")
def resolve(eid: int, db: Session = Depends(get_db)):
    e = db.get(ErrorJournal, eid)
    if e is not None:
        e.resolved, e.resolved_on, e.auto_resolved = True, _today(db), False
        db.commit()
    return RedirectResponse("/errors", status_code=303)
