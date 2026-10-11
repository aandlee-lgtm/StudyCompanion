"""Revision page (owner: adaptive; adaptive-18): sections by urgency, evidence per item, 'Practise now'
through the selection engine's rules, 15-minute revision sets and completed-revision outcomes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RevisionQueue, RevisionSet
from app.routes.common import render, render_error
from app.services import clock, revision
from app.services import settings as st

router = APIRouter()


def _today(db: Session):
    return clock.today(st.get(db, "timezone"))


@router.get("/review")
def review(request: Request, none: int = 0, db: Session = Depends(get_db)):
    data = revision.review_page(db, _today(db))
    missing = db.get(RevisionQueue, none) if none else None
    return render(request, "review.html", missing=missing, no_set=none == -1, **data)


@router.get("/review/{rid}/practise")
def practise_item(rid: int, db: Session = Depends(get_db)):
    """Serve the best question for this revision item now (also for items not yet due)."""
    r = db.get(RevisionQueue, rid)
    if r is None:
        return RedirectResponse("/review", status_code=303)
    q = revision.pick_for_item(db, r, _today(db))
    if q is None:
        return RedirectResponse(f"/review?none={rid}#missing", status_code=303)
    return RedirectResponse(f"/practice/{q.id}", status_code=303)


@router.post("/review/set")
def start_set(db: Session = Depends(get_db)):
    s = revision.start_set(db, _today(db))
    if s is None:
        return RedirectResponse("/review?none=-1#missing", status_code=303)
    db.commit()
    return RedirectResponse(f"/review/set/{s.id}", status_code=303)


@router.get("/review/set/{sid}")
def show_set(sid: int, request: Request, db: Session = Depends(get_db)):
    s = db.get(RevisionSet, sid)
    if s is None:
        return render_error(request, "That revision set does not exist.", 404)
    rows = revision.refresh_set_status(db, s)
    db.commit()
    nxt = next((r for r in rows if r["attempt"] is None and r["question"] is not None), None)
    return render(request, "review_set.html", s=s, rows=rows, nxt=nxt)
