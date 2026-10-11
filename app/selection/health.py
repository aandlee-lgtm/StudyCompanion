"""Question bank health (selection-03/04/07/17), measured with the selection engine's own rules.

"Fresh" means what the engine would serve as new today: never attempted, or an exact question
whose revision date has arrived (``scoring.eligibility``). English counts unread passages (the unit
of freshness, one a day), Legal counts by format, Mathematics counts fresh questions and distinct
forms per LEARNING item (a template keeps an item supplied). Read-only and fast (one context, three
pools). Used by the Sessions page card, ``GET /api/selection/bank-health`` and the dashboard card."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.common import LEARNING
from app.selection.context import build_context, legal_format
from app.selection.pool import Pool

LOW_FRESH_PER_ITEM = 10  # spec: a LEARNING item with fewer fresh questions is flagged
LOW_DAYS = 10
FRESH_KINDS = ("fresh", "served", "due")
SUBJECT_LABEL = {"MATHS": "Mathematics", "ENGLISH": "English", "LEGAL": "Legal Studies"}


def _status(days: float) -> str:
    return "empty" if days < 1 else ("low" if days < LOW_DAYS else "ok")


def _plural(n: float, word: str) -> str:
    n = round(n)
    return f"{n} {word}{'' if n == 1 else 's'}"


def _maths(db: Session, ctx) -> dict:
    from app.services import maths_templates, question_bank

    pool = Pool(db, ctx, "MATHS")
    items = []
    for it in sorted((i for i in ctx.plan.values() if i.subject.code == "MATHS" and i.status == LEARNING and i.active),
                     key=lambda i: i.position):
        mine = [s for s in pool.cands if s.question.plan_item_id == it.id and s.kind in FRESH_KINDS]
        forms = {pool.form(s) for s in mine}
        has_template = it.code in maths_templates.TEMPLATES
        low = len(mine) < LOW_FRESH_PER_ITEM and not has_template
        items.append({"id": it.id, "code": it.code, "title": it.title, "fresh": len(mine), "forms": len(forms),
                      "template": has_template, "low": low, "empty": not mine and not has_template,
                      "template_gaps": question_bank.template_gaps(it.code) if has_template else []})
    fresh = sum(1 for s in pool.cands if s.kind in FRESH_KINDS)
    low = [i for i in items if i["low"]]
    status = "empty" if any(i["empty"] for i in items) else ("low" if low else "ok")
    if items:
        text = "Learning now: " + "; ".join(
            f"{i['code']} {i['title']}: {_plural(i['fresh'], 'fresh question')}"
            + (" (a template makes more)" if i["template"] else f", {_plural(i['forms'], 'form')}") for i in items)
    else:
        text = f"{_plural(fresh, 'fresh question')}; no topic is marked Learning."
    action = "; ".join(f"add questions for {i['code']} {i['title']} (import past-paper questions, approve generated "
                       "ones, or enable AI variants)" for i in low) or None
    return {"fresh": fresh, "learning_items": items, "status": status, "text": text, "action": action}


def _english(db: Session, ctx, per_day: int) -> dict:
    pool = Pool(db, ctx, "ENGLISH")
    units: dict[tuple, int] = {}
    for s in pool.cands:
        if s.question.category == "unseen" and s.question.stimulus_id and s.kind in FRESH_KINDS:
            key = ctx.stimulus_unit.get(s.question.stimulus_id, (s.question.stimulus_id,))
            if not any(m in ctx.stimulus_last_read for m in key):
                units[key] = units.get(key, 0) + 1
    passages = sum(1 for n in units.values() if n >= min(3, max(1, per_day)))
    course = sum(1 for s in pool.cands if s.question.category != "unseen" and s.kind in FRESH_KINDS)
    return {"passages_left": passages, "course_left": course, "days": passages, "status": _status(passages),
            "text": f"Unread passages: {passages} (about {_plural(passages, 'day')} of unseen practice); "
                    f"{_plural(course, 'course-linked task')} not yet attempted",
            "action": "Add reading sets so unseen practice stays fresh." if passages < LOW_DAYS else None}


def _legal(db: Session, ctx, per_day: int) -> dict:
    pool = Pool(db, ctx, "LEGAL")
    by_fmt = {f: 0 for f in ("mcq", "short_answer", "stimulus", "extended")}
    for s in pool.cands:
        if s.kind in FRESH_KINDS:
            by_fmt[legal_format(s.question)] += 1
    non_ext = by_fmt["mcq"] + by_fmt["short_answer"] + by_fmt["stimulus"]
    days = non_ext / max(1, per_day)
    return {"fresh_by_format": by_fmt, "fresh": non_ext, "days": round(days, 1), "status": _status(days),
            "text": f"{non_ext} unseen questions (about {_plural(days, 'day')}: {by_fmt['mcq']} multiple choice, "
                    f"{by_fmt['short_answer']} short answer, {by_fmt['stimulus']} stimulus) and "
                    f"{_plural(by_fmt['extended'], 'extended response')}",
            "action": "Add short-answer and stimulus questions so repeats are not needed." if days < LOW_DAYS else None}


def bank_health(db: Session, today: date) -> dict:
    """Per subject: ``status`` (ok | low | empty), ``text`` (one line for the student), ``action``
    (what to add, or None) and the numbers behind them."""
    ctx = build_context(db, today)
    counts = ctx.profile.counts or {}
    return {"MATHS": _maths(db, ctx),
            "ENGLISH": _english(db, ctx, counts.get("ENGLISH", 3)),
            "LEGAL": _legal(db, ctx, counts.get("LEGAL", 3))}
