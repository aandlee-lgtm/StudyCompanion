"""Reveal gate for answers, guidelines, worked solutions and model responses (adaptive-01).

They are shown on the question detail page only after the student has attempted or skipped the
question (a reveal from the detail page records an honest skip), or when the owner switched on
``admin_mode`` in Settings."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, Question
from app.services import settings as st


def attempt_count(db: Session, q: Question) -> int:
    return db.execute(select(func.count(Attempt.id)).where(Attempt.question_id == q.id)).scalar_one()


def revealed(db: Session, q: Question) -> bool:
    if st.get(db, "admin_mode"):
        return True
    return attempt_count(db, q) > 0


def reveal_by_skipping(db: Session, q: Question) -> None:
    """Record a skip through the normal assessment path, so the reveal counts as 'not answered'
    in mastery and the revision queue instead of silently exposing the answer."""
    from app.services import assessment

    if attempt_count(db, q) == 0:
        assessment.submit(db, q, "", skipped=True)
