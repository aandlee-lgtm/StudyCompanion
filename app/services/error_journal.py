"""Automatic error journal (section 23; owner: adaptive).

Two axes for Maths: the *error type* (section 5C: conceptual, algebraic, arithmetic, ...) and the
*topic tag* (section 23: sign error, chain rule, algebra, domain/range, calculator error,
probability interpretation, ... extensible). English and Legal use their section-23 category lists.
Only counted, reliably marked attempts write entries; retries mark earlier entries as fixed;
three correct counted answers in a row on the skill resolve an entry automatically; a tag seen
three or more times in 30 days becomes a targeted revision item (a *pattern*)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, ErrorJournal, ExposureEvent, LearningPlanItem, Question

MATHS_ERROR_TYPES = ["conceptual", "algebraic", "arithmetic", "interpretation", "formula selection", "incomplete reasoning",
                     "insufficient working", "notation", "careless error"]
MATHS_TOPIC_TAGS = ["sign error", "chain rule", "algebra", "domain/range", "calculator error", "probability interpretation",
                    "product/quotient rule", "log laws", "index laws", "limits of integration", "financial periods", "exact values",
                    "radians/degrees", "term number", "series formula", "rounding", "units"]
ENGLISH_CATEGORIES = ["insufficient textual evidence", "technique identification without analysis", "weak thesis", "descriptive response",
                      "poor comparison", "limited evaluation", "imprecise expression"]
LEGAL_CATEGORIES = ["missing authority", "outdated legislation", "weak judgement", "description instead of evaluation",
                    "insufficient contemporary evidence", "poor use of cases", "failure to address directive verb",
                    "imprecise legal terminology", "no law reform", "stimulus not used", "unverified/invented authority"]
CATEGORIES = {"MATHS": MATHS_ERROR_TYPES, "ENGLISH": ENGLISH_CATEGORIES, "LEGAL": LEGAL_CATEGORIES}

# v1 / marker values that are really section-23 topic tags (category, topic tag)
MATHS_LEGACY = {
    "sign": ("careless error", "sign error"), "sign error": ("careless error", "sign error"), "careless": ("careless error", None),
    "calculator error": ("careless error", "calculator error"), "chain rule": ("conceptual", "chain rule"),
    "algebra": ("algebraic", "algebra"), "algebraic error": ("algebraic", "algebra"), "domain/range": ("interpretation", "domain/range"),
    "domain": ("interpretation", "domain/range"), "range": ("interpretation", "domain/range"),
    "probability interpretation": ("interpretation", "probability interpretation"), "working": ("insufficient working", None),
}
ALIASES = {
    "ENGLISH": {"textual evidence": "insufficient textual evidence", "no quotations": "insufficient textual evidence",
                "descriptive": "descriptive response", "retelling": "descriptive response", "thesis": "weak thesis",
                "comparison": "poor comparison", "evaluation": "limited evaluation", "expression": "imprecise expression",
                "technique spotting": "technique identification without analysis", "analysis": "technique identification without analysis"},
    "LEGAL": {"authority": "missing authority", "no legislation": "missing authority", "outdated": "outdated legislation",
              "judgement": "weak judgement", "descriptive": "description instead of evaluation", "evaluation": "description instead of evaluation",
              "contemporary": "insufficient contemporary evidence", "cases": "poor use of cases", "directive verb": "failure to address directive verb",
              "terminology": "imprecise legal terminology", "law reform": "no law reform", "stimulus": "stimulus not used",
              "invented": "unverified/invented authority", "unverified": "unverified/invented authority"},
}
DESCRIPTIONS = {
    "conceptual": "The underlying idea was misapplied — revisit why the method works, not just its steps.",
    "algebraic": "An algebraic manipulation went wrong (expanding, factorising, rearranging or simplifying).",
    "arithmetic": "A calculation went wrong although the method was appropriate.",
    "interpretation": "The question was read differently from what it asked (what is being found, or under which condition).",
    "formula selection": "The wrong formula, or the wrong version of it, was used.",
    "incomplete reasoning": "The answer stopped short of what was asked.",
    "insufficient working": "Working was too thin for method marks to be awarded.",
    "notation": "The value may be right, but it was not written in the required form or notation.",
    "careless error": "A slip in an otherwise sound method.",
    "insufficient textual evidence": "Points were not supported by precise, integrated quotations from the text.",
    "technique identification without analysis": "Techniques were named without explaining how they shape meaning.",
    "weak thesis": "The response lacked a clear, arguable thesis that answers the question.",
    "descriptive response": "The response described or retold the text instead of analysing it.",
    "poor comparison": "The texts were discussed separately rather than compared explicitly.",
    "limited evaluation": "No clear judgement was made about effectiveness or extent.",
    "imprecise expression": "Expression was vague or imprecise for the mark value.",
    "missing authority": "Points were not supported with named legislation or cases.",
    "outdated legislation": "An outdated or repealed law was relied on.",
    "weak judgement": "The judgement about effectiveness was missing or not sustained.",
    "description instead of evaluation": "The law was described rather than evaluated against criteria.",
    "insufficient contemporary evidence": "Recent, dated evidence (cases, reports, reforms) was missing.",
    "poor use of cases": "Cases were named without explaining their legal significance.",
    "failure to address directive verb": "The response did not do what the directive verb asks.",
    "imprecise legal terminology": "Legal terms were missing or used imprecisely.",
    "no law reform": "Law reform (what changed, why, and its effect) was not discussed.",
    "stimulus not used": "The stimulus material was not used to support the answer.",
    "unverified/invented authority": "An authority was cited that is not in your verified evidence bank.",
}
# offline estimate gaps (app.marking.rubric) -> category (legal-20: each gap has its own category)
OFFLINE_GAPS = {
    "ENGLISH": {"Textual evidence": "insufficient textual evidence", "Analysis of effect": "descriptive response",
                "Judgement": "limited evaluation", "Comparison": "poor comparison", "Thesis": "weak thesis",
                "Language/form features": "technique identification without analysis"},
    "LEGAL": {"Legal terminology": "imprecise legal terminology", "Legal authority": "missing authority",
              "Contemporary evidence": "insufficient contemporary evidence", "Judgement": "description instead of evaluation",
              "Law reform": "no law reform", "Stimulus": "stimulus not used", "Directive verb": "failure to address directive verb"},
}


def normalise(code: str, category: str | None, topic_tag: str | None = None) -> tuple[str, str | None]:
    """Map a raw category (marker, AI or other package) onto the subject's enum; unknown -> 'other: <text>'."""
    raw = (category or "").strip().lower()
    tag = (topic_tag or "").strip().lower() or None
    if code == "MATHS":
        if raw in MATHS_ERROR_TYPES:
            return raw, tag
        if raw in MATHS_LEGACY:
            cat, t = MATHS_LEGACY[raw]
            return cat, tag or t
        if raw in MATHS_TOPIC_TAGS:
            return "conceptual", tag or raw
        if not raw and tag:
            return MATHS_LEGACY.get(tag, ("conceptual", tag))[0], tag
        return (f"other: {raw}"[:60] if raw else "conceptual"), tag
    allowed = CATEGORIES.get(code, [])
    if raw in allowed:
        return raw, tag
    match = next((a for a in allowed if a in raw or (len(raw) > 6 and raw in a)), None)
    if match:
        return match, tag
    alias = next((v for k, v in ALIASES.get(code, {}).items() if k in raw), None)
    if alias:
        return alias, tag
    return (f"other: {raw}"[:60] if raw else "other"), tag


def _item(code: str, category: str | None, description: str | None, topic_tag: str | None = None) -> dict:
    cat, tag = normalise(code, category, topic_tag)
    desc = (description or "").strip() or DESCRIPTIONS.get(cat) or cat
    return {"category": cat, "topic_tag": tag, "description": desc}


def written_items(code: str, result: dict, method: str) -> list[dict]:
    """Categories with their OWN descriptions from a written marking result (AI errors or offline gaps)."""
    items: list[dict] = []
    for e in result.get("errors") or []:
        items.append(_item(code, e.get("category"), e.get("description")))
    if method == "offline_estimate":
        gaps = result.get("weaknesses") or []
        texts = result.get("improvements") or []
        for i, g in enumerate(gaps):
            cat = OFFLINE_GAPS.get(code, {}).get(g)
            if cat:
                items.append(_item(code, cat, texts[i] if i < len(texts) else None))
    out, seen = [], set()
    for it in items:
        if it["category"] not in seen:
            seen.add(it["category"])
            out.append(it)
    return out


def items_for(code: str, q: Question, payload: dict, cats: list, method: str) -> list[dict]:
    """Journal items for an attempt. Packages may provide ``payload['journal_items']`` (list of
    {category, topic_tag, description}); otherwise they are derived from the marker's categories."""
    if payload.get("kind") == "skipped":
        return []
    provided = payload.get("journal_items")
    if provided:
        return [_item(code, i.get("category"), i.get("description"), i.get("topic_tag")) for i in provided if i.get("category")]
    if payload.get("kind") == "mcq":
        if payload.get("correct"):
            return []
        sol = q.solution or {}
        chosen = (payload.get("chosen") or str(payload.get("student_answer") or "")[:1]).upper()
        tags = sol.get("option_tags") or {}
        rationale = (sol.get("option_rationales") or {}).get(chosen)
        tag = tags.get(chosen)
        default = {"MATHS": "conceptual", "ENGLISH": "other: multiple choice", "LEGAL": "other: multiple choice"}[code] if code in CATEGORIES else "other"
        cat = (cats[0] if cats and isinstance(cats[0], str) else None) or (sol.get("option_categories") or {}).get(chosen) or default
        desc = f"You chose {chosen}: {rationale}" if rationale else None
        return [_item(code, cat, desc, tag)]
    items = []
    tag = payload.get("topic_tag") or (payload.get("topic_tags") or [None])[0]
    for c in cats or []:
        if isinstance(c, dict):
            items.append(_item(code, c.get("category"), c.get("description"), c.get("topic_tag") or tag))
        elif payload.get("kind") == "maths":
            items.append(_item(code, c, payload.get("divergence"), tag))
        else:
            items.append(_item(code, c, None, tag))
    return items


def add_entries(db: Session, attempt: Attempt, q: Question, code: str, items: list[dict], today: date, source: str) -> list[ErrorJournal]:
    rows = []
    for it in items:
        e = ErrorJournal(attempt_id=attempt.id, question_id=q.id, subject_code=code, category=it["category"][:60],
                         topic_tag=(it.get("topic_tag") or None) and it["topic_tag"][:60], description=it["description"],
                         plan_item_id=q.plan_item_id, study_date=today, source=source)
        db.add(e)
        rows.append(e)
    db.flush()
    return rows


def replace_entries(db: Session, attempt: Attempt, q: Question, code: str, items: list[dict], today: date, source: str) -> None:
    for e in db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == attempt.id)).scalars():
        db.delete(e)
    db.flush()
    add_entries(db, attempt, q, code, items, today, source)


def mark_fixed_on_retry(db: Session, earlier_attempt_ids: list[int], current_categories: set[str]) -> int:
    """Entries from earlier attempts whose category no longer appears are flagged as fixed on retry."""
    n = 0
    if not earlier_attempt_ids:
        return 0
    for e in db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id.in_(earlier_attempt_ids))).scalars():
        fixed = e.category not in current_categories
        if fixed and not e.fixed_on_retry:
            n += 1
        e.fixed_on_retry = fixed
    db.flush()
    return n


def auto_resolve(db: Session, plan_item_id: int | None, today: date, streak: int = 3) -> int:
    """Resolve open entries on a skill after ``streak`` consecutive correct counted answers since the entry."""
    if not plan_item_id:
        return 0
    open_entries = db.execute(select(ErrorJournal).where(ErrorJournal.plan_item_id == plan_item_id, ErrorJournal.resolved.is_(False))).scalars().all()
    if not open_entries:
        return 0
    events = db.execute(select(ExposureEvent).where(ExposureEvent.plan_item_id == plan_item_id, ExposureEvent.counted.is_(True),
                                                    ExposureEvent.method != "offline_estimate")
                        .order_by(ExposureEvent.id.desc()).limit(streak)).scalars().all()
    if len(events) < streak or any(ev.fraction < 0.85 for ev in events):
        return 0
    first_of_streak = min(ev.attempt_id for ev in events)
    n = 0
    for e in open_entries:
        if e.attempt_id < first_of_streak:
            e.resolved, e.auto_resolved, e.resolved_on = True, True, today
            n += 1
    db.flush()
    return n


def pattern_key(e: ErrorJournal) -> tuple[str, str]:
    return (e.subject_code, e.topic_tag or e.category)


def recent_count(db: Session, code: str, key: str, today: date, days: int = 30) -> int:
    since = today - timedelta(days=days)
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.subject_code == code, ErrorJournal.resolved.is_(False),
                                                 ErrorJournal.study_date >= since)).scalars()
    return sum(1 for e in rows if (e.topic_tag or e.category) == key)


def patterns(db: Session, today: date, subject: str = "", limit: int = 8) -> list[dict]:
    """Repeated errors with counts (14/30 days), trend, where they occur and an interpretation line."""
    since = today - timedelta(days=60)
    q = select(ErrorJournal).where(ErrorJournal.study_date >= since)
    if subject:
        q = q.where(ErrorJournal.subject_code == subject)
    rows = db.execute(q).scalars().all()
    groups: dict[tuple[str, str], list[ErrorJournal]] = defaultdict(list)
    for e in rows:
        groups[pattern_key(e)].append(e)
    out = []
    for (code, key), es in groups.items():
        d = lambda e: e.study_date or today  # noqa: E731
        n14 = sum(1 for e in es if (today - d(e)).days < 14)
        n30 = sum(1 for e in es if (today - d(e)).days < 30)
        prev14 = sum(1 for e in es if 14 <= (today - d(e)).days < 28)
        if n30 == 0:
            continue
        open_n = sum(1 for e in es if not e.resolved and (today - d(e)).days < 30)
        fixed = sum(1 for e in es if e.fixed_on_retry)
        items = Counter(e.plan_item_id for e in es if e.plan_item_id and (today - d(e)).days < 30)
        topics = []
        for pid, c in items.most_common(3):
            it = db.get(LearningPlanItem, pid)
            if it:
                topics.append({"id": pid, "name": f"{it.code} {it.title}" if it.chapter else it.title, "count": c})
        cats = Counter(e.category for e in es if e.topic_tag)
        trend = "up" if n14 > prev14 else ("down" if n14 < prev14 else "flat")
        label = key
        where = f", {topics[0]['count']} in {topics[0]['name']}" if topics else ""
        extra = f" (mostly {cats.most_common(1)[0][0]})" if cats else ""
        interp = f"{label[0].upper() + label[1:]}: {n14} in the last 14 days, {n30} in 30{where}{extra}."
        if trend == "down" and prev14:
            interp += " Fewer than the fortnight before — keep going."
        elif trend == "up" and n14 >= 2:
            interp += " Becoming more frequent: worth a targeted question."
        if fixed:
            interp += f" Fixed on retry {fixed} time{'s' if fixed != 1 else ''}, so you can correct it once you see it."
        latest = max(es, key=lambda e: e.id)
        out.append({"subject": code, "key": key, "n14": n14, "n30": n30, "prev14": prev14, "open": open_n, "trend": trend,
                    "topics": topics, "interpretation": interp, "example_ids": [e.question_id for e in sorted(es, key=lambda e: -e.id)[:3]],
                    "description": latest.description, "plan_item_id": topics[0]["id"] if topics else latest.plan_item_id,
                    "repeated": n30 >= 3})
    out.sort(key=lambda p: (-p["n30"], -p["n14"]))
    return out[:limit]


def top_pattern(db: Session, today: date) -> dict | None:
    ps = [p for p in patterns(db, today) if p["repeated"]]
    return ps[0] if ps else None
