"""Practice outside daily sessions (owner: adaptive)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, DailySession, LearningPlanItem, Question, SessionQuestion
from app.routes.common import render
from app.services import analytics, assessment, clock, sessions
from app.services import settings as st

from app.routes.question_helpers import do_submit, question_context

router = APIRouter()


@router.get("/practice/{qid}")
def practice(qid: int, request: Request, retry: int = 0, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None or not q.approved:
        raise ValueError("That question is not available for practice.")
    ctx = question_context(db, q, None, bool(retry))
    return render(request, "question.html", s=None, total=None, pos=None, base=f"/practice/{qid}", **ctx)


@router.post("/practice/{qid}/submit")
def practice_submit(qid: int, answer: str = Form(""), working: str = Form(""), confidence: str = Form(""), time_seconds: int = Form(0),
                    db: Session = Depends(get_db)):
    do_submit(db, db.get(Question, qid), None, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)


@router.post("/practice/{qid}/skip")
def practice_skip(qid: int, db: Session = Depends(get_db)):
    do_submit(db, db.get(Question, qid), None, "", "", "", 0, True)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)


