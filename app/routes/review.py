from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LearningPlanItem, Question, QuestionExposure, RevisionQueue
from app.routes.common import render
from app.services import clock
from app.services import settings as st

router = APIRouter()


@router.get("/review")
def review(request: Request, db: Session = Depends(get_db)):
    today = clock.today(st.get(db, "timezone"))
    seen = {e.question_id for e in db.execute(select(QuestionExposure)).scalars()}
    due, upcoming = [], []
    for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "open").order_by(RevisionQueue.due_date)).scalars():
        item = db.get(LearningPlanItem, r.plan_item_id) if r.plan_item_id else None
        if r.due_date <= today:
            sample = None
            if item:
                sample = db.execute(select(Question).where(Question.plan_item_id == item.id, Question.approved.is_(True),
                                                           Question.is_extension.is_(False), Question.id.not_in(seen or {-1}))).scalars().first()
            elif r.question_id:
                sample = db.get(Question, r.question_id)
            due.append((r, item, sample))
        elif r.due_date <= today + timedelta(days=21):
            upcoming.append((r, item))
    repeats = db.execute(select(QuestionExposure, Question).join(Question, QuestionExposure.question_id == Question.id)
                         .where(QuestionExposure.next_revision_date <= today).order_by(QuestionExposure.next_revision_date).limit(20)).all()
    return render(request, "review.html", due=due, upcoming=upcoming, repeats=repeats)
