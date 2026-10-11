"""Attempt actions: why did I lose the mark, self-marking, model viewed (owner: adaptive)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt
from app.services import assessment
from app.services.assessment import core

router = APIRouter()


def _attempt(db: Session, aid: int) -> Attempt:
    a = db.get(Attempt, aid)
    if a is None or a.feedback is None:
        raise ValueError("That attempt does not exist.")
    return a


def _safe_back(back: str) -> str:
    return back if back.startswith("/") and not back.startswith("//") else "/"


@router.post("/attempt/{aid}/why")
def why(aid: int, db: Session = Depends(get_db)):
    a = _attempt(db, aid)
    text = assessment.why_lost(db, a)
    db.commit()
    return JSONResponse({"explanation": text, "paragraphs": [p for p in text.split("\n\n") if p.strip()]})


@router.post("/attempt/{aid}/self-mark")
async def self_mark(aid: int, request: Request, mark: float = Form(...), back: str = Form("/"), db: Session = Depends(get_db)):
    """Record or change a self-mark. Optional fields: ``criteria`` (JSON list, or repeated ``criterion`` values for
    the guideline lines the student ticked), ``category`` (repeated journal categories) and ``note``."""
    form = await request.form()
    a = _attempt(db, aid)
    criteria = None
    raw = form.get("criteria")
    if raw:
        try:
            criteria = json.loads(raw)
        except ValueError:
            criteria = None
    ticked = form.getlist("criterion")
    if criteria is None and ticked:
        criteria = [{"criterion": t, "met": True} for t in ticked]
    cats = form.getlist("category")
    assessment.apply_self_mark(db, a, mark, categories=cats or None, criteria=criteria, note=(form.get("note") or None))
    db.commit()
    return RedirectResponse(_safe_back(back) + "#feedback", status_code=303)


@router.post("/attempt/{aid}/model-viewed")
def model_viewed(aid: int, request: Request, back: str = Form(""), db: Session = Depends(get_db)):
    """The model response / full worked solution was opened: later attempts are labelled 'after viewing the model'."""
    a = _attempt(db, aid)
    first = core.mark_model_viewed(db, a)
    db.commit()
    if back:
        return RedirectResponse(_safe_back(back) + "#feedback", status_code=303)
    return JSONResponse({"ok": True, "first": first})
