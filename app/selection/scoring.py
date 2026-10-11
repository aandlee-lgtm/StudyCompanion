"""Two-stage scoring.

Stage 1 ranks PLAN ITEMS (what to practise today): current-learning relevance, weakness, spaced
revision due, coverage gap and how long since the item was practised. These are the configurable
weights of section 10, so changing them really changes which topics get today's slots.

Stage 2 ranks QUESTIONS within an item: difficulty fit (against a per-item target), novelty and
source priority.

Eligibility tiers make the exact-repeat rule hard (section 12, 13): a question already attempted
comes back only once its revision date has arrived AND a different question on the same skill has
been attempted since. Anything else is a fallback, used only when nothing fresh can fill a slot.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.models import Question
from app.models.common import (
    APPROVAL_APPROVED,
    LEARNED,
    LEARNING,
    LOCKED,
    ORIGIN_ADAPTED,
    ORIGIN_GENERATED,
    ORIGIN_HISTORICAL,
    ORIGIN_SAMPLE,
    ORIGIN_TRIAL,
    REJECT,
    REVISION,
)
from app.selection.context import StudentContext
from app.selection.phases import is_exam_style

SOURCE_PRIORITY = {ORIGIN_SAMPLE: 1.0, ORIGIN_HISTORICAL: 0.95, ORIGIN_ADAPTED: 0.75, ORIGIN_TRIAL: 0.7, ORIGIN_GENERATED: 0.6}

# eligibility tiers (lower is better); EXCLUDED is never served
FRESH, LADDER, RETRY, REPEAT, EXCLUDED = 0, 1, 2, 3, 9
TIER_PENALTY = {FRESH: 0.0, LADDER: 2.0, RETRY: 2.5, REPEAT: 3.5}
MIN_REPEAT_GAP = 3  # never on consecutive study days (Friday -> Monday included)
LADDER_GAP = 14  # fallback repeats: nothing seen within two weeks

STAGE1 = ("current", "weakness", "spaced", "coverage", "novelty")
STAGE2 = ("difficulty", "novelty", "source")


@dataclass
class Scored:
    """A question with its scores (kept for compatibility with v1 callers and session rows)."""

    question: Question
    score: float
    breakdown: dict[str, float]
    bucket: str  # learning | recent | older
    reason: str
    tier: int = FRESH
    kind: str = "fresh"  # fresh | due | ladder | retry | repeat | served
    item_priority: float = 0.0
    facts: dict = field(default_factory=dict)

    @property
    def minutes(self) -> float:
        return float(self.question.estimated_minutes or 0)


# ------------------------------------------------------------------ hard rules ---
def is_servable(ctx: StudentContext, q: Question) -> bool:
    """Hard rules that can never be relaxed."""
    if not q.approved or q.approval_status != APPROVAL_APPROVED:
        return False
    if q.relevance_status == REJECT or q.is_extension:
        return False
    item = ctx.plan.get(q.plan_item_id)
    if item is None or item.status == LOCKED or not item.active:
        return False
    if item.enrichment and not ctx.settings.get("enrichment_enabled"):
        return False
    prefs = ctx.settings.get("source_preferences") or {}
    if q.historical_or_generated == ORIGIN_TRIAL and not prefs.get("allow_trial", True):
        return False
    if q.historical_or_generated == ORIGIN_GENERATED and not prefs.get("allow_generated", True):
        return False
    if q.historical_or_generated == ORIGIN_ADAPTED and not prefs.get("allow_adapted", True):
        return False
    return True


def eligibility(ctx: StudentContext, q: Question, item_alternatives: int, written: bool = False) -> tuple[int, str]:
    """(tier, kind). ``item_alternatives`` = other servable questions on the same plan item.

    Fallback ladder when nothing fresh is left (selection-03): (a) LADDER: a question seen at
    least two weeks ago, closest to its revision date; (c) RETRY: rewrite a weak earlier written
    answer (spec 25); (d) REPEAT: a flagged repeat, never on consecutive study days. (b), an AI
    variant on the same skill, is created by ``app.selection.variants`` when a provider exists."""
    if q.id in ctx.exclude_ids or q.id in ctx.reserved_ids:
        return EXCLUDED, "excluded"
    e = ctx.exposure.get(q.id)
    ds = ctx.days_since_seen(q.id)
    if e is None:
        if ds is None:
            return FRESH, "fresh"
        # served in an earlier session but never answered: still new to the student
        return (FRESH, "served") if ds >= MIN_REPEAT_GAP else (EXCLUDED, "recent")
    if ds is not None and ds < MIN_REPEAT_GAP:
        return EXCLUDED, "recent"
    due = (e.next_revision_date is not None and e.next_revision_date <= ctx.today) or q.id in ctx.revision_questions
    different_since = item_alternatives == 0 or any(
        d > e.last_seen and qid != q.id for d, qid in ctx.item_attempt_dates.get(q.plan_item_id or -1, ())
    )
    if due and different_since:
        return FRESH, "due"
    if ds is not None and ds >= LADDER_GAP:
        return LADDER, "ladder"
    if written and e.score_history and e.score_history[-1] < 0.7:
        return RETRY, "retry"
    return REPEAT, "repeat"


# --------------------------------------------------------------- plan items ---
def learning_bucket(ctx: StudentContext, item) -> str:
    if item is None:
        return "older"
    if item.status == LEARNING:
        return "learning"
    if item.status == REVISION or item.is_assumed_knowledge:
        return "older"
    learned = ctx.learned_on.get(item.id) or item.status_changed_at.date()
    return "recent" if (ctx.today - learned).days <= 42 else "older"


def _current(ctx: StudentContext, item) -> float:
    if item is None:
        return 0.2
    if item.status == LEARNING:
        return 1.0
    if item.status == REVISION:
        return 0.85
    if item.is_assumed_knowledge:
        return 0.25
    if item.status == LEARNED:
        learned = ctx.learned_on.get(item.id) or item.status_changed_at.date()
        days = (ctx.today - learned).days
        return 0.65 if days <= 28 else (0.45 if days <= 70 else 0.3)
    return 0.0


def item_factors(ctx: StudentContext, item_id: int | None) -> dict[str, float]:
    item = ctx.plan.get(item_id or -1)
    m = ctx.mastery.get(item_id or -1)
    weakness = (1.0 - m.mastery) if (m is not None and m.attempts) else 0.4
    spaced = min(1.0, 0.8 * ctx.revision_items[item_id]) if item_id in ctx.revision_items else 0.0
    coverage = 1.0 / (1.0 + ctx.item_attempts.get(item_id or -1, 0) / 3.0)
    last = ctx.item_last_practised.get(item_id or -1)
    recency = 1.0 if last is None else min(1.0, (ctx.today - last).days / 21.0)
    return {"current": _current(ctx, item), "weakness": max(0.0, min(1.0, weakness)), "spaced": spaced,
            "coverage": coverage, "novelty": recency}


def is_struggling(ctx: StudentContext, item_id: int | None) -> bool:
    m = ctx.mastery.get(item_id or -1)
    return m is not None and m.attempts >= 3 and m.mastery < 0.55


def item_priority(ctx: StudentContext, item_id: int | None) -> tuple[float, dict[str, float], list[str]]:
    """Stage-1 priority (about 0..1.6) with its factors and the bonuses applied."""
    f = item_factors(ctx, item_id)
    w = ctx.weights
    wsum = sum(w.get(k, 0) for k in STAGE1) or 1.0
    p = sum(w.get(k, 0) * f[k] for k in STAGE1) / wsum
    flags: list[str] = []
    if item_id in ctx.catch_up:
        p += 0.5
        flags.append("catch_up")
    if is_struggling(ctx, item_id) and item_id not in ctx.last_session_items:
        p += 0.35  # a rebuild slot at least every second session until the skill recovers
        flags.append("rebuild")
    if item_id in ctx.revision_items:
        flags.append("revision_due")
    cov = coverage_overdue(ctx, item_id)
    if cov is not None:  # every earlier Maths item comes back within a few weeks, however strong (selection-21)
        p += min(1.0, 0.4 + 0.04 * cov)
        flags.append("coverage_due")
    return round(p, 4), f, flags


def coverage_overdue(ctx: StudentContext, item_id: int | None) -> int | None:
    """Days past the coverage limit for an earlier (not currently learning) Maths item, or None.

    Weak items rightly take most revision slots, so without this a strong Year 11 topic could go
    months without a single question."""
    item = ctx.plan.get(item_id or -1)
    if item is None or item.status in (LEARNING, LOCKED) or item.subject.code != "MATHS":
        return None
    limit = int(ctx.settings.get("selection_coverage_days") or 18)
    last = ctx.item_last_practised.get(item.id)
    days = (ctx.today - last).days if last else (ctx.sessions_before * 7) // 5
    return days - limit if days >= limit else None


# ------------------------------------------------------------------ questions ---
def jitter(ctx: StudentContext, q: Question) -> float:
    """Deterministic tie-breaker (stable across refreshes; never the main logic)."""
    h = hashlib.sha256(f"{ctx.plan_date.isoformat()}:{q.id}".encode()).digest()
    return (h[0] / 255.0) * 0.01


def question_factors(ctx: StudentContext, q: Question, subject: str, kind: str) -> dict[str, float]:
    target = ctx.item_target_difficulty(subject, q.plan_item_id)
    diff = max(0.0, 1.0 - abs((q.difficulty or 2) - target) / 2.0)
    novelty = {"fresh": 1.0, "served": 0.8, "due": 0.55, "ladder": 0.2, "retry": 0.3, "repeat": 0.05}.get(kind, 0.5)
    return {"difficulty": diff, "novelty": novelty, "source": SOURCE_PRIORITY.get(q.historical_or_generated, 0.6)}


def question_score(ctx: StudentContext, q: Question, subject: str, kind: str) -> tuple[float, dict[str, float]]:
    f = question_factors(ctx, q, subject, kind)
    w = ctx.weights
    wsum = sum(w.get(k, 0) for k in STAGE2) or 1.0
    s = sum(w.get(k, 0) * f[k] for k in STAGE2) / wsum
    if kind == "due":  # an exact question whose revision date has arrived
        s += 0.3 * min(1.0, ctx.revision_questions.get(q.id, 0.7))
    if subject == "MATHS" and ctx.phase.exam_style_bonus and is_exam_style(q):
        s += ctx.phase.exam_style_bonus  # more exam-like as the HSC approaches (selection-22)
    return round(s + jitter(ctx, q), 4), f


def score(ctx: StudentContext, q: Question, subject: str, tier: int = FRESH, kind: str = "fresh") -> Scored:
    """Stage 1 + stage 2 for one question (value used by the set optimiser)."""
    p, f1, flags = item_priority(ctx, q.plan_item_id)
    s2, f2 = question_score(ctx, q, subject, kind)
    value = p + 0.5 * s2 - TIER_PENALTY.get(tier, 5.0)
    bd = {**{k: round(v, 3) for k, v in f1.items()}, **{f"q_{k}": round(v, 3) for k, v in f2.items()},
          "item_priority": p, "question_score": s2}
    item = ctx.plan.get(q.plan_item_id or -1)
    return Scored(q, round(value, 4), bd, learning_bucket(ctx, item), "", tier=tier, kind=kind, item_priority=p,
                  facts={"flags": flags})
