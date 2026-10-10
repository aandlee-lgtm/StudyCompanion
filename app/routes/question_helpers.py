"""Shared question-page helpers used by session and practice routes (owner: adaptive)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, LearningPlanItem, Question, SessionQuestion
from app.services import assessment, sessions
from app.services import settings as st

WORKING_SEP = "\n<<WORKING>>\n"


def split_draft(text: str | None) -> tuple[str, str]:
    if not text:
        return "", ""
    if WORKING_SEP in text:
        a, w = text.split(WORKING_SEP, 1)
        return a, w
    return text, ""


def get_sq(db: Session, sid: int, pos: int) -> SessionQuestion:
    sq = db.execute(select(SessionQuestion).where(SessionQuestion.session_id == sid, SessionQuestion.position == pos)).scalar_one_or_none()
    if sq is None:
        raise ValueError("That question is not part of this session.")
    return sq


def attempts_for(db: Session, q: Question, sq: SessionQuestion | None) -> list[Attempt]:
    stmt = select(Attempt).where(Attempt.question_id == q.id)
    stmt = stmt.where(Attempt.session_question_id == sq.id) if sq else stmt.where(Attempt.session_question_id.is_(None))
    return list(db.execute(stmt.order_by(Attempt.attempt_number)).scalars())


def question_context(db: Session, q: Question, sq: SessionQuestion | None, retry: bool) -> dict:
    attempts = attempts_for(db, q, sq)
    latest = attempts[-1] if attempts else None
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    mapping = q.mappings[-1] if q.mappings else None
    answer, working = split_draft(sq.draft_text if sq else None)
    if retry and latest and not answer:
        answer = latest.response_text
    code = assessment.subject_code(db, q)
    kind = "mcq" if q.question_type == "mcq" else ("maths" if code == "MATHS" else "written")
    return {"q": q, "sq": sq, "attempts": attempts, "latest": latest, "item": item, "mapping": mapping, "code": code, "kind": kind,
            "show_form": latest is None or retry, "draft_answer": answer, "draft_working": working,
            "reading": q.stimulus.reading_set() if q.stimulus else [], "ask_confidence": st.get(db, "ask_confidence"),
            "image": ("/media/" + q.question_image.split("/")[-1]) if q.question_image else None}



def do_submit(db: Session, q: Question, sq: SessionQuestion | None, answer: str, working: str, confidence: str, time_seconds: int, skipped: bool):
    if not skipped and not (answer or "").strip():
        raise ValueError("Write an answer first, or choose 'Show answer / skip'.")
    assessment.submit(db, q, answer, sq=sq, working=working or None, confidence=confidence or None, time_seconds=time_seconds, skipped=skipped)
    if sq is not None:
        sq.draft_text = None
        sessions.maybe_complete(db, sq.session)

