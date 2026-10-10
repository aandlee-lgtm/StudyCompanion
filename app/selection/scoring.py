"""Per-question selection score: a configurable weighted sum of educational factors.

Factors (each 0..1): current learning relevance, weakness, spaced-repetition priority,
syllabus coverage gap, difficulty fit, novelty and source priority. Variety and recent-exposure
penalties are applied by the engine while it assembles the day."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models import Question
from app.models.common import LEARNED, LEARNING, ORIGIN_ADAPTED, ORIGIN_GENERATED, ORIGIN_HISTORICAL, ORIGIN_SAMPLE, ORIGIN_TRIAL, REVISION
from app.selection.context import StudentContext

SOURCE_PRIORITY = {ORIGIN_SAMPLE: 1.0, ORIGIN_HISTORICAL: 0.95, ORIGIN_ADAPTED: 0.75, ORIGIN_TRIAL: 0.7, ORIGIN_GENERATED: 0.6}


@dataclass
class Scored:
    question: Question
    score: float
    breakdown: dict[str, float]
    bucket: str  # learning | recent | older
    reason: str


def learning_bucket(ctx: StudentContext, q: Question) -> str:
    item = ctx.plan.get(q.plan_item_id)
    if item is None:
        return "older"
    if item.status == LEARNING:
        return "learning"
    if item.status == REVISION:
        return "older"
    if item.is_assumed_knowledge:
        return "older"
    days = (ctx.today - item.status_changed_at.date()).days
    return "recent" if days <= 42 else "older"


def _current(ctx: StudentContext, q: Question) -> float:
    item = ctx.plan.get(q.plan_item_id)
    if item is None:
        return 0.2
    if item.status == LEARNING:
        return 1.0
    if item.status == REVISION:
        return 0.85
    if item.is_assumed_knowledge:
        return 0.25
    if item.status == LEARNED:
        days = (ctx.today - item.status_changed_at.date()).days
        return 0.65 if days <= 28 else (0.45 if days <= 70 else 0.3)
    return 0.0


def _weakness(ctx: StudentContext, q: Question) -> float:
    m = ctx.mastery.get(q.plan_item_id)
    w = 1.0 - (m.mastery if m else 0.5)
    e = ctx.exposure.get(q.id)
    if e and e.score_history:
        w = max(w, 1.0 - e.score_history[-1])
    return max(0.0, min(1.0, w))


def _spaced(ctx: StudentContext, q: Question) -> float:
    s = 0.0
    if q.id in ctx.revision_questions:
        s = max(s, min(1.0, ctx.revision_questions[q.id]))
    if q.plan_item_id in ctx.revision_items:
        s = max(s, min(1.0, 0.8 * ctx.revision_items[q.plan_item_id]))
    e = ctx.exposure.get(q.id)
    if e and e.next_revision_date and e.next_revision_date <= ctx.today:
        s = max(s, 0.7 + min(0.3, (ctx.today - e.next_revision_date).days / 60))
    return s


def _coverage(ctx: StudentContext, q: Question) -> float:
    n = ctx.item_attempts.get(q.plan_item_id, 0)
    return 1.0 / (1.0 + n / 3.0)


def _difficulty(ctx: StudentContext, q: Question, subject: str) -> float:
    target = ctx.target_difficulty(subject)
    return max(0.0, 1.0 - abs(q.difficulty - target) / 2.0)


def _novelty(ctx: StudentContext, q: Question) -> float:
    e = ctx.exposure.get(q.id)
    if e is None:
        return 1.0
    return 0.25 if (ctx.today - e.last_seen).days > 50 else 0.05


def jitter(ctx: StudentContext, q: Question) -> float:
    """Deterministic tie-breaker (stable across refreshes; never the main logic)."""
    h = hashlib.sha256(f"{ctx.today.isoformat()}:{q.id}".encode()).digest()
    return (h[0] / 255.0) * 0.01


def reason_for(ctx: StudentContext, q: Question, bd: dict[str, float], bucket: str) -> str:
    item = ctx.plan.get(q.plan_item_id)
    name = f"{item.code} {item.title}" if item and item.chapter else (item.title if item else "general practice")
    m = ctx.mastery.get(q.plan_item_id)
    if bd["spaced"] >= 0.7:
        e = ctx.exposure.get(q.id)
        if e:
            return f"Revision due: you last saw this on {e.last_seen:%d %b} and scored {round(100 * (e.score_history[-1] if e.score_history else 0))}%."
        return f"Scheduled revision of {name}: a different question on a skill you found difficult."
    if m and m.attempts >= 3 and m.mastery < 0.6 and bd["weakness"] >= 0.4:
        return f"Weak area: your recent accuracy on {name} is about {round(100 * m.mastery)}%."
    if bucket == "learning":
        return f"Reinforces what you are currently learning: {name}."
    if item and item.is_assumed_knowledge:
        return f"Year 11 assumed knowledge revision: {item.title}."
    if bucket == "recent":
        return f"Keeps recently learned material fresh: {name}."
    if bd["coverage"] >= 0.9:
        return f"Coverage: {name} has not been assessed yet."
    return f"Spaced revision of earlier material: {name}."


def score(ctx: StudentContext, q: Question, subject: str) -> Scored:
    bd = {
        "current": _current(ctx, q),
        "weakness": _weakness(ctx, q),
        "spaced": _spaced(ctx, q),
        "coverage": _coverage(ctx, q),
        "difficulty": _difficulty(ctx, q, subject),
        "novelty": _novelty(ctx, q),
        "source": SOURCE_PRIORITY.get(q.historical_or_generated, 0.6),
    }
    w = ctx.weights
    total = sum(w.get(k, 0) * v for k, v in bd.items()) + jitter(ctx, q)
    # recent-exposure penalty: the same subtopic served heavily in the last few sessions
    total -= 0.03 * ctx.recent_plan_counts.get(q.plan_item_id, 0)
    bucket = learning_bucket(ctx, q)
    return Scored(q, round(total, 4), {k: round(v, 3) for k, v in bd.items()}, bucket, reason_for(ctx, q, bd, bucket))
