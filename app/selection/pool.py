"""Candidate pools: every servable question of one subject, scored once, with its eligibility tier.

Near-duplicate checks against recently seen questions are lazy and cached: only questions that
reach the top of an item's list are compared, so a bank of thousands of questions stays fast."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Question, Stimulus, Subject
from app.selection.context import StudentContext, form_key
from app.selection.scoring import EXCLUDED, REPEAT, Scored, eligibility, is_servable, score
from app.services.fingerprint import NEAR_DUPLICATE, shingles

READING_WPM = 110  # careful reading speed for unseen texts


@lru_cache(maxsize=50000)
def _sh(text: str) -> frozenset:
    return frozenset(shingles(text or ""))


def similar(a: str, b: str) -> float:
    sa, sb = _sh(a), _sh(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def near_duplicate(a: Question, b: Question) -> bool:
    return a.id == b.id or similar(a.question_text, b.question_text) >= NEAR_DUPLICATE


def reading_minutes(stims: list[Stimulus]) -> float:
    total = 0.0
    for s in stims:
        words = len((s.body or "").split())
        total += max(2.0, words / READING_WPM) if words else 3.0
    return round(total, 2)


class Pool:
    def __init__(self, db: Session, ctx: StudentContext, code: str):
        self.ctx, self.code = ctx, code
        subj = db.execute(select(Subject).where(Subject.code == code)).scalar_one()
        qs = db.execute(
            select(Question).options(selectinload(Question.stimulus)).where(Question.subject_id == subj.id)
        ).scalars().all()
        servable = [q for q in qs if is_servable(ctx, q)]
        per_item: dict[int | None, int] = {}
        for q in servable:
            per_item[q.plan_item_id] = per_item.get(q.plan_item_id, 0) + 1
        self.cands: list[Scored] = []
        self.fresh_left: dict[int | None, int] = {}
        for q in servable:
            written = code != "MATHS" and q.question_type != "mcq"
            tier, kind = eligibility(ctx, q, per_item[q.plan_item_id] - 1, written)
            if tier == EXCLUDED:
                continue
            if kind == "fresh":
                self.fresh_left[q.plan_item_id] = self.fresh_left.get(q.plan_item_id, 0) + 1
            self.cands.append(score(ctx, q, code, tier, kind))
        self.cands.sort(key=lambda s: (s.tier, -s.score))
        self._checked: set[int] = set()
        self._recent = [t for t in ctx.recent_texts if t]
        self._forms: dict[int, str] = {}

    # ---------------------------------------------------------------- helpers ---
    def form(self, s: Scored) -> str:
        f = self._forms.get(s.question.id)
        if f is None:
            f = self._forms[s.question.id] = form_key(s.question)
        return f

    def verify(self, s: Scored) -> Scored:
        """Downgrade a fresh question that is a near-duplicate of something seen this week."""
        qid = s.question.id
        if qid in self._checked or s.kind not in ("fresh", "served"):
            return s
        self._checked.add(qid)
        text = s.question.question_text
        if any(similar(text, t) >= NEAR_DUPLICATE for t in self._recent):
            from app.selection.scoring import TIER_PENALTY

            s.score = round(s.score - TIER_PENALTY[REPEAT] + TIER_PENALTY.get(s.tier, 0), 4)
            s.tier, s.kind = REPEAT, "near_duplicate"
        return s

    def ranked(self, pred=None, k: int = 8) -> list[Scored]:
        """Best candidates matching ``pred`` (tier first, then value), verified for near-duplicates."""
        out: list[Scored] = []
        for s in self.cands:
            if pred is not None and not pred(s):
                continue
            out.append(s)
            if len(out) >= k * 2:
                break
        for s in out:
            self.verify(s)
        out.sort(key=lambda s: (s.tier, -s.score))
        return out[:k]

    def by_item(self) -> dict[int | None, list[Scored]]:
        d: dict[int | None, list[Scored]] = {}
        for s in self.cands:
            d.setdefault(s.question.plan_item_id, []).append(s)
        return d
