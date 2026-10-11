"""Question bank health (selection-03/04/07/17), measured with the selection engine's own rules.

"Fresh" means what the engine would serve as new today: never attempted, or an exact question
whose revision date has arrived (``scoring.eligibility``). English counts unread passages (the unit
of freshness), Legal counts by format, Mathematics counts fresh questions and distinct forms per
LEARNING item. For the dashboard card and the Learning plan; read-only and fast (one context, three
pools)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.common import LEARNING
from app.selection.context import build_context, legal_format
from app.selection.pool import Pool

LOW_FRESH_PER_ITEM = 10


def _status(days: float) -> str:
    return "empty" if days < 1 else ("low" if days < 10 else "ok")


def bank_health(db: Session, today: date) -> dict:
    from app.services import question_bank

    ctx = build_context(db, today)
    out: dict = {}
    counts = ctx.profile.counts if ctx.profile.counts else {"MATHS": 5, "ENGLISH": 3, "LEGAL": 3}
    fresh_kinds = ("fresh", "served", "due")

    # Mathematics: fresh questions and forms per LEARNING item; template levels it cannot produce
    pool = Pool(db, ctx, "MATHS")
    items = []
    for it in sorted((i for i in ctx.plan.values() if i.subject.code == "MATHS" and i.status == LEARNING and i.active),
                     key=lambda i: i.position):
        mine = [s for s in pool.cands if s.question.plan_item_id == it.id and s.kind in fresh_kinds]
        forms = {pool.form(s) for s in mine}
        items.append({"id": it.id, "code": it.code, "title": it.title, "fresh": len(mine), "forms": len(forms),
                      "low": len(mine) < LOW_FRESH_PER_ITEM, "template_gaps": question_bank.template_gaps(it.code)})
    m_fresh = sum(1 for s in pool.cands if s.kind in fresh_kinds)
    out["MATHS"] = {"fresh": m_fresh, "learning_items": items, "status": "low" if any(i["fresh"] == 0 for i in items) else "ok",
                    "action": "; ".join(f"add questions for {i['code']} {i['title']} ({i['fresh']} fresh, {i['forms']} form"
                                        f"{'s' if i['forms'] != 1 else ''})" for i in items if i["low"]) or None}

    # English: unread passages (one a day) and course-linked tasks
    pool = Pool(db, ctx, "ENGLISH")
    units: dict[tuple, int] = {}
    for s in pool.cands:
        if s.question.category == "unseen" and s.question.stimulus_id and s.kind in fresh_kinds:
            key = ctx.stimulus_unit.get(s.question.stimulus_id, (s.question.stimulus_id,))
            if not any(m in ctx.stimulus_last_read for m in key):
                units[key] = units.get(key, 0) + 1
    passages = sum(1 for n in units.values() if n >= min(3, counts.get("ENGLISH", 3)))
    course = sum(1 for s in pool.cands if s.question.category != "unseen" and s.kind in fresh_kinds)
    out["ENGLISH"] = {"passages_left": passages, "course_left": course, "days": passages, "status": _status(passages),
                      "text": f"Passages left: {passages} (about {passages} day{'s' if passages != 1 else ''})",
                      "action": "Add reading sets so unseen practice stays fresh." if passages < 10 else None}

    # Legal Studies: fresh questions by format
    pool = Pool(db, ctx, "LEGAL")
    by_fmt = {f: 0 for f in ("mcq", "short_answer", "stimulus", "extended")}
    for s in pool.cands:
        if s.kind in fresh_kinds:
            by_fmt[legal_format(s.question)] += 1
    daily = max(1, counts.get("LEGAL", 3))
    non_ext = by_fmt["mcq"] + by_fmt["short_answer"] + by_fmt["stimulus"]
    days = non_ext / daily
    out["LEGAL"] = {"fresh_by_format": by_fmt, "days": round(days, 1), "status": _status(days),
                    "text": f"{non_ext} unseen questions (about {round(days)} days), {by_fmt['extended']} extended responses",
                    "action": "Add short-answer and stimulus questions so repeats are not needed." if days < 10 else None}
    return out
