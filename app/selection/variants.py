"""Fallback ladder rung (b): when a written subject has run out of fresh questions and an AI
provider is configured, write a NEW question on the same skill (labelled GENERATED, linked to the
question it was modelled on) instead of repeating. Offline, nothing happens here and the ladder
moves on to rewrite tasks and flagged repeats."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.common import ORIGIN_GENERATED
from app.selection.context import StudentContext
from app.selection.scoring import FRESH

MAX_PER_SUBJECT = 2


def _short_of_fresh(ctx: StudentContext, code: str, pool) -> int:
    n = ctx.profile.counts.get(code, 0)
    if code == "LEGAL":
        fresh = [s for s in pool.cands if s.tier == FRESH and s.question.question_type != "extended"]
        return max(0, n - len(fresh))
    if code == "ENGLISH":
        unseen = [s for s in pool.cands if s.tier == FRESH and s.question.category == "unseen"]
        course = [s for s in pool.cands if s.tier == FRESH and s.question.category != "unseen"]
        if len(unseen) >= n:
            return 0
        return max(0, n - len(course))
    return 0


def top_up_with_variants(db: Session, ctx: StudentContext, pools: dict) -> int:
    from app.ai import factory
    from app.services import question_bank as qb

    provider = factory.get_provider(ctx.settings)
    if not getattr(provider, "generative", False):
        return 0
    created = 0
    for code in ("ENGLISH", "LEGAL"):
        pool = pools.get(code)
        if pool is None:
            continue
        need = min(MAX_PER_SUBJECT, _short_of_fresh(ctx, code, pool))
        if not need:
            continue
        bases = [s.question for s in pool.cands
                 if s.kind in ("ladder", "retry", "repeat") and s.question.question_type in ("short_answer", "working")
                 and (code != "ENGLISH" or s.question.category != "unseen")]
        bases.sort(key=lambda q: (ctx.exposure[q.id].score_history[-1] if q.id in ctx.exposure and ctx.exposure[q.id].score_history else 1.0))
        for base in bases[:need]:
            try:
                v = provider.generate_question_variant({
                    "subject_name": {"ENGLISH": "English Advanced", "LEGAL": "Legal Studies"}[code],
                    "topic": base.topic.name if getattr(base, "topic", None) else "", "marks": base.marks, "question": base.question_text,
                })
            except Exception:
                continue
            src = qb.get_or_create_source(
                db, "HSC Companion — AI-generated practice variants", organisation="HSC Companion (AI generated)",
                subject_id=base.subject_id, source_type="generated", tier=4, official=False,
                notes="New questions written by the configured AI provider on the same skill as an earlier question, when the "
                      "fresh bank ran out. Labelled GENERATED; never past HSC questions.",
            )
            q = qb.create_question(
                db, subject_code=code, source_id=src.id, question_text=v.question_text, marks=v.marks,
                question_type="short_answer", directive_verb=base.directive_verb, difficulty=base.difficulty, topic_id=base.topic_id,
                plan_item_id=base.plan_item_id, category=base.category, historical_or_generated=ORIGIN_GENERATED,
                generated_from_question_id=base.id, model_answer=v.model_answer, marking_guideline=base.marking_guideline,
                guideline_official=False, legal_fact_currency="check" if code == "LEGAL" else None, mapped_by="ai",
                mapping_reason=f"AI-generated variant of question {base.id} on the same skill, created because fresh questions ran out.",
            )
            if q.id != base.id:
                created += 1
    return created
