from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ErrorJournal
from app.routes.common import render

router = APIRouter()


@router.get("/errors")
def errors(request: Request, subject: str = "", show_resolved: int = 0, db: Session = Depends(get_db)):
    q = select(ErrorJournal).order_by(ErrorJournal.created_at.desc())
    if subject:
        q = q.where(ErrorJournal.subject_code == subject)
    if not show_resolved:
        q = q.where(ErrorJournal.resolved.is_(False))
    entries = db.execute(q.limit(300)).scalars().all()
    counts = Counter((e.subject_code, e.category) for e in entries).most_common(9)
    return render(request, "errors.html", entries=entries, counts=counts, subject=subject, show_resolved=show_resolved)


@router.post("/errors/{eid}/resolve")
def resolve(eid: int, db: Session = Depends(get_db)):
    e = db.get(ErrorJournal, eid)
    e.resolved = True
    db.commit()
    return RedirectResponse("/errors", status_code=303)
