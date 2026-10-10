"""Attempt actions: why did I lose the mark, self-marking (owner: adaptive)."""
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

router = APIRouter()


@router.post("/attempt/{aid}/why")
def why(aid: int, db: Session = Depends(get_db)):
    a = db.get(Attempt, aid)
    text = assessment.why_lost(db, a)
    db.commit()
    return JSONResponse({"explanation": text})


@router.post("/attempt/{aid}/self-mark")
def self_mark(aid: int, mark: float = Form(...), back: str = Form("/"), db: Session = Depends(get_db)):
    a = db.get(Attempt, aid)
    assessment.apply_self_mark(db, a, mark)
    db.commit()
    return RedirectResponse(back, status_code=303)


