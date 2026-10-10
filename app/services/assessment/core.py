"""Submission: attempts, feedback records, error journal, mastery updates, self-marking."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_provider
from app.models import Attempt, AttemptFeedback, ErrorJournal, Question, SessionQuestion
from app.services import mastery
from app.services import settings as st
from app.services.assessment.common import subject_code
from app.services.assessment.maths import mark_deterministic
from app.services.assessment.written import mark_written


def submit(db: Session, q: Question, response: str, *, sq: SessionQuestion | None = None, working: str | None = None,
           confidence: str | None = None, time_seconds: int = 0, skipped: bool = False, today: date | None = None) -> Attempt:
    from app.services.clock import today as clock_today

    settings = st.all_settings(db)
    today = today or clock_today(settings.get("timezone", "Australia/Sydney"))
    same_context = Attempt.session_question_id == sq.id if sq else Attempt.session_question_id.is_(None)
    prev_attempts = db.execute(select(Attempt).where(Attempt.question_id == q.id, same_context).order_by(Attempt.attempt_number)).scalars().all()
    if sq is None:  # practice outside a session: each day's practice starts with a fresh first attempt
        prev_attempts = [a for a in prev_attempts if a.submitted_at.date() == today]
    attempt_no = len(prev_attempts) + 1
    code = subject_code(db, q)
    if skipped:
        mark, payload, cats, method = 0.0, {"kind": "skipped", "mark": 0, "max": q.marks, "label": "Skipped — answer shown. Recorded as skipped, not correct."}, [], "skipped"
    elif q.answer is not None:
        mark, payload, cats, method = mark_deterministic(db, q, response, working, settings)
    elif code == "MATHS" and not get_provider(settings).generative:
        mark, payload, cats, method = 0.0, {
            "kind": "self_mark", "mark": 0, "max": q.marks, "method": "self",
            "label": "This imported question has no machine-checkable answer and no AI provider is configured. "
                     "Compare your working with the marking guideline below and record the mark you earned.",
            "guideline": q.marking_guideline, "guideline_official": q.guideline_official,
        }, [], "self"
    else:
        previous = prev_attempts[-1].response_text if prev_attempts else None
        mark, payload, cats, method = mark_written(db, q, response, settings, previous)
    attempt = Attempt(question_id=q.id, session_question_id=sq.id if sq else None, attempt_number=attempt_no, response_text=response or "",
                      skipped=skipped, mark_awarded=float(mark), mark_possible=float(q.marks), confidence=confidence, time_seconds=time_seconds,
                      marking_method=method, official_guideline_used=bool(q.guideline_official and method == "ai"),
                      submitted_at=datetime.combine(today, datetime.now().time()))  # local study day
    db.add(attempt)
    db.flush()
    if working:
        payload["working"] = working
    if prev_attempts:
        p = prev_attempts[-1]
        payload["previous"] = {"attempt_number": p.attempt_number, "mark": p.mark_awarded, "max": p.mark_possible,
                               "change": round(attempt.mark_awarded - p.mark_awarded, 1)}
    db.add(AttemptFeedback(attempt_id=attempt.id, payload=payload, error_categories=cats))
    for c in cats:
        db.add(ErrorJournal(attempt_id=attempt.id, question_id=q.id, subject_code=code, category=c, plan_item_id=q.plan_item_id,
                            description=_journal_text(payload, c)))
    if attempt_no == 1:  # retries improve the answer but do not reset the schedule
        sched = mastery.record(db, attempt, q, today, settings.get("revision_intensity", "normal"), cats[0] if cats else payload.get("error_category"))
        payload["schedule"] = sched
        fb = db.execute(select(AttemptFeedback).where(AttemptFeedback.attempt_id == attempt.id)).scalar_one()
        fb.payload = dict(payload)
    if sq is not None:
        sq.status = "skipped" if skipped else "submitted"
        sq.time_spent_seconds = max(sq.time_spent_seconds, time_seconds)
    db.flush()
    return attempt


def _journal_text(payload: dict, category: str) -> str:
    if payload.get("kind") == "maths":
        return payload.get("divergence") or category
    r = payload.get("result") or {}
    for e in r.get("errors", []):
        if e.get("category", "").lower() in category or category in e.get("category", "").lower():
            return e.get("description", category)
    return "; ".join(r.get("improvements", [])[:1]) or category


# ------------------------------------------------------------- Why lost ---


def apply_self_mark(db: Session, attempt: Attempt, mark: float) -> None:
    from app.services.clock import today as clock_today

    attempt.mark_awarded = max(0.0, min(float(mark), attempt.mark_possible))
    fb = attempt.feedback
    payload = dict(fb.payload)
    payload["mark"] = attempt.mark_awarded
    payload["self_marked"] = True
    fb.payload = payload
    settings = st.all_settings(db)
    if attempt.attempt_number == 1:
        mastery.record(db, attempt, attempt.question, clock_today(settings.get("timezone", "Australia/Sydney")), settings.get("revision_intensity", "normal"))
    db.flush()
