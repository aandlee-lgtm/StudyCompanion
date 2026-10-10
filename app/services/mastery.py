"""Mastery, spaced repetition and revision scheduling (section 12 and 19)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, Mastery, Question, QuestionExposure, RevisionQueue
from app.services.settings import REVIEW_INTERVALS

SLIP_CATEGORIES = {"careless error", "arithmetic", "sign", "notation", "calculator error"}
INTENSITY = {"light": 1.2, "normal": 1.0, "intense": 0.8}


def quality(fraction: float, confidence: str | None, category: str | None, skipped: bool) -> tuple[str, float]:
    """Returns (interval bucket, mastery evidence 0..1).

    - A correct answer marked 'Guess' is not mastery: short interval, evidence 0.5.
    - A careless slip by a student who was confident is treated differently from a
      misunderstanding: medium interval, evidence 0.7."""
    if skipped:
        return "very_weak", 0.0
    if fraction >= 0.85:
        if confidence == "guess":
            return "weak", 0.5
        if confidence == "unsure":
            return "adequate", 0.75
        return "strong", 1.0
    if category in SLIP_CATEGORIES and confidence in ("confident", "very_confident"):
        return "adequate", 0.7
    if fraction >= 0.6:
        return "adequate", fraction
    if fraction >= 0.35:
        return "weak", fraction
    return "very_weak", fraction


def interval_days(bucket: str, previous_interval: int | None, intensity: str = "normal") -> int:
    lo, hi = REVIEW_INTERVALS[bucket]
    # repeated success pushes towards the long end of the range
    days = hi if previous_interval and previous_interval >= lo else lo
    return max(1, round(days * INTENSITY.get(intensity, 1.0)))


def _queue(db: Session, plan_item_id: int | None, question_id: int | None, due: date, reason: str, priority: float) -> None:
    q = select(RevisionQueue).where(RevisionQueue.status == "open")
    q = q.where(RevisionQueue.plan_item_id == plan_item_id) if plan_item_id else q.where(RevisionQueue.question_id == question_id)
    existing = db.execute(q).scalars().first()
    if existing:
        if due < existing.due_date:
            existing.due_date, existing.reason = due, reason
        existing.priority = max(existing.priority, priority)
        return
    db.add(RevisionQueue(plan_item_id=plan_item_id, question_id=question_id, due_date=due, reason=reason, priority=priority))


def record(db: Session, attempt: Attempt, question: Question, today: date, intensity: str = "normal", category: str | None = None) -> dict:
    """Update exposure, mastery and the revision queue after an attempt."""
    bucket, evidence = quality(attempt.fraction, attempt.confidence, category, attempt.skipped)
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == question.id)).scalar_one_or_none()
    prev_interval = exp.interval_days if exp else None
    days = interval_days(bucket, prev_interval if (exp and bucket == "strong") else None, intensity)
    if exp is None:
        exp = QuestionExposure(question_id=question.id, first_seen=today, last_seen=today, attempts=0, score_history=[])
        db.add(exp)
    exp.last_seen = today
    exp.attempts += 1
    exp.score_history = list(exp.score_history or []) + [round(attempt.fraction, 3)]
    exp.mastery = round(0.6 * (exp.mastery or 0) + 0.4 * evidence, 3) if exp.attempts > 1 else round(evidence, 3)
    exp.interval_days = days
    exp.next_revision_date = today + timedelta(days=days)

    if question.plan_item_id:
        m = db.execute(select(Mastery).where(Mastery.plan_item_id == question.plan_item_id)).scalar_one_or_none()
        if m is None:
            m = Mastery(plan_item_id=question.plan_item_id, mastery=0.5, attempts=0)
            db.add(m)
        alpha = 0.35 if m.attempts >= 3 else 0.5
        m.mastery = round((1 - alpha) * m.mastery + alpha * evidence, 3)
        m.attempts += 1
        m.last_seen = today
        # earlier revision for weak skills (a DIFFERENT question on the same skill first);
        # deliberate two-month recycle of successful concepts.
        if bucket == "very_weak":
            _queue(db, question.plan_item_id, None, today + timedelta(days=2), "Very weak answer: revisit this skill soon with a different question.", 1.0)
        elif bucket == "weak":
            _queue(db, question.plan_item_id, None, today + timedelta(days=5), "Weak answer: practise this skill again with a different question.", 0.8)
        elif bucket == "strong":
            _queue(db, question.plan_item_id, None, today + timedelta(days=60), "Two-month recycle of a concept you answered well.", 0.5)
        m.next_revision_date = min((r.due_date for r in db.execute(select(RevisionQueue).where(
            RevisionQueue.plan_item_id == question.plan_item_id, RevisionQueue.status == "open")).scalars()), default=None)
        # close revision items for this skill that were due (this attempt served them)
        for r in db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == question.plan_item_id,
                                                         RevisionQueue.status == "open", RevisionQueue.due_date <= today)).scalars():
            if not (bucket in ("weak", "very_weak") and r.due_date > today):
                r.status = "done"
    db.flush()
    return {"bucket": bucket, "interval_days": days, "next_revision": exp.next_revision_date.isoformat()}
