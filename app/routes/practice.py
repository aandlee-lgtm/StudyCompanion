"""Practice outside daily sessions (owner: adaptive).

Practice is one attempt chain with the daily sessions (adaptive-02): practising a question that is
not yet due, or that was already answered or revealed, is stored as *rehearsal* — shown in the
history, never evidence for mastery or schedules. Drafts autosave here too (english-15)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Question
from app.routes.common import render
from app.routes.question_helpers import do_submit, question_context, save_practice_draft

router = APIRouter()


def _question(db: Session, qid: int) -> Question:
    q = db.get(Question, qid)
    if q is None or not q.approved:
        raise ValueError("That question is not available for practice.")
    return q


@router.get("/practice/{qid}")
def practice(qid: int, request: Request, retry: int = 0, db: Session = Depends(get_db)):
    q = _question(db, qid)
    ctx = question_context(db, q, None, bool(retry))
    return render(request, "question.html", s=None, total=None, pos=None, base=f"/practice/{qid}", **ctx)


@router.post("/practice/{qid}/draft")
def practice_draft(qid: int, text: str = Form(""), time_seconds: int = Form(0), db: Session = Depends(get_db)):
    d = save_practice_draft(db, _question(db, qid), text, time_seconds)
    db.commit()
    return JSONResponse({"ok": True, "saved_at": d.updated_at.isoformat()})


@router.post("/practice/{qid}/submit")
def practice_submit(qid: int, answer: str = Form(""), working: str = Form(""), confidence: str = Form(""), time_seconds: int = Form(0),
                    db: Session = Depends(get_db)):
    do_submit(db, _question(db, qid), None, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)


@router.post("/practice/{qid}/skip")
def practice_skip(qid: int, time_seconds: int = Form(0), db: Session = Depends(get_db)):
    do_submit(db, _question(db, qid), None, "", "", "", time_seconds, True)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)
