"""English routes (owner: english-logic): guided self-marking of written answers and the
'How marks scale' reference page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt
from app.services.assessment import english

router = APIRouter()


def _attempt(db: Session, aid: int) -> Attempt:
    a = db.get(Attempt, aid)
    if a is None or a.feedback is None:
        raise ValueError("That attempt does not exist.")
    return a


def _safe_back(back: str, a: Attempt) -> str:
    if back.startswith("/") and not back.startswith("//"):
        return back
    return f"/practice/{a.question_id}#feedback"


@router.post("/english/attempt/{aid}/self-mark")
def guided_self_mark(aid: int, request: Request, tick: list[int] = Form(default=[]), back: str = Form("/"), db: Session = Depends(get_db)):
    """Record a guided self-mark: the ticked checklist items set the mark (capped by the deterministic checks)."""
    a = _attempt(db, aid)
    g = english.apply_guided_self_mark(db, a, tick)
    db.commit()
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"mark": g["final"], "raw": g["raw"], "max": a.mark_possible, "cap": g["cap"], "ticked": g["ticked"],
                             "level": g["level"], "next_step": g["next_step"]})
    return RedirectResponse(_safe_back(back, a), status_code=303)


@router.post("/english/attempt/{aid}/self-mark/preview")
def guided_preview(aid: int, tick: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    """The mark the current ticks would give, without recording anything."""
    a = _attempt(db, aid)
    p = dict(a.feedback.payload or {})
    if not p.get("english"):
        raise ValueError("Guided self-marking is only available for English written answers.")
    p["response"] = a.response_text
    g = english.guided_summary(a.question, p, tick)
    return JSONResponse({"mark": g["final"], "raw": g["raw"], "max": a.mark_possible, "cap": g["cap"], "level": g["level"],
                         "next_step": g["next_step"], "cap_reasons": g["cap_reasons"]})
