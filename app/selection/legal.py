"""Legal Studies: a weekly format plan and an extended-response plan (selection-16, legal-07, legal-10).

Formats are mcq | short_answer | stimulus | extended. Each day respects:
  * at most one objective (MCQ) question, two on an extended-response day;
  * at least one response at Describe/Explain level or above;
  * at most one stimulus (one scenario or data set to read);
  * an extended response only when the plan schedules one, never more than one.
Over the week the mix follows a target that moves with progress through the year (more stimulus
work later), and each directive-verb tier appears. Extended responses follow a monthly target that
rises towards the HSC, preferring Fridays, rotating through Crime, Human rights and any activated
option; an identical essay is never repeated while the rules above forbid it."""
from __future__ import annotations

import itertools
from datetime import timedelta

from app.models.common import LOCKED
from app.selection.context import StudentContext, legal_format, verb_tier, verb_tier_of
from app.selection.optimiser import Option
from app.selection.pool import Pool, near_duplicate, reading_minutes
from app.selection.scoring import FRESH, LADDER, REPEAT, RETRY, Scored

FORMATS = ("mcq", "short_answer", "stimulus", "extended")


def _interp(points: list, x: float) -> float:
    pts = sorted((float(a), float(b)) for a, b in points)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1)
    return pts[-1][1]


def extended_per_month(ctx: StudentContext) -> float:
    if ctx.profile.extended == "none":
        return 0.0
    if ctx.profile.extended == "exam":
        return float(ctx.settings.get("legal_extended_exam_per_month", 8) or 8)
    pts = ctx.settings.get("legal_extended_per_month") or [[0, 1], [1, 8]]
    return _interp(pts, ctx.progress)


def _study_days(ctx: StudentContext) -> list[int]:
    return sorted(ctx.settings.get("weekdays") or [0, 1, 2, 3, 4])


def topic_roots(ctx: StudentContext) -> dict[int, int]:
    """Legal plan item id -> the id of its topic. A sub-area item (``LS-CRIME-TRIAL``) belongs to the
    topic whose code is its shortest prefix (``LS-CRIME``), so the extended-response rotation
    alternates Crime / Human rights / options rather than sub-areas."""
    legal = [it for it in ctx.plan.values() if it.subject.code == "LEGAL"]
    by_code = {it.code: it for it in legal}
    out: dict[int, int] = {}
    for it in legal:
        parts = (it.code or "").split("-")
        root = next((by_code[c] for c in ("-".join(parts[:k]) for k in range(1, len(parts))) if c in by_code), it)
        out[it.id] = root.id
    return out


def extended_plan(ctx: StudentContext, pool: Pool | None = None) -> dict:
    """Is an extended response due today, and which topic is next in the rotation?"""
    per_month = extended_per_month(ctx)
    hist = sorted((h for h in ctx.legal_history if h["type"] == "extended"), key=lambda h: h["date"], reverse=True)
    last = hist[0]["date"] if hist else None
    n28 = sum(1 for h in hist if (ctx.today - h["date"]).days < 28)
    days_since = (ctx.today - last).days if last else None
    min_gap = max(2.0, 28.0 / per_month * 0.7) if per_month else 999
    weekday = ctx.plan_date.weekday()
    days = _study_days(ctx)
    preferred = {4 if 4 in days else days[-1]}
    if per_month >= 5:
        preferred.add(2 if 2 in days else days[len(days) // 2])
    if ctx.profile.extended == "exam":
        preferred = set(days)
    min_sessions = int(ctx.settings.get("legal_extended_min_sessions", 8) or 0)
    plan = {"per_month": round(per_month, 2), "last_28_days": n28, "days_since": days_since, "due": False, "why": ""}
    if per_month <= 0:
        plan["why"] = "no extended responses in this mode"
    elif ctx.profile.extended != "exam" and ctx.sessions_before < min_sessions:
        plan["why"] = "too early in the year"
    elif weekday not in preferred:
        plan["why"] = "not an extended-response day"
    elif n28 + 0.5 > per_month:
        plan["why"] = "this month's extended responses are done"
    elif days_since is not None and days_since < min_gap:
        plan["why"] = "one was done recently"
    else:
        plan["due"] = True
    # topic rotation: the topic whose last extended response is oldest (never first)
    roots = topic_roots(ctx)
    last_by_item: dict = {}
    for h in hist:
        last_by_item.setdefault(roots.get(h["item"], h["item"]), h["date"])
    topic_ids = {roots[it.id] for it in ctx.plan.values() if it.subject.code == "LEGAL" and it.active and it.status != LOCKED}
    topics = [ctx.plan[i] for i in topic_ids if i in ctx.plan]
    topics.sort(key=lambda it: (last_by_item.get(it.id) is not None, last_by_item.get(it.id) or ctx.today, it.position))
    plan["rotation"] = [it.id for it in topics]
    return plan


def weekly_targets(ctx: StudentContext) -> dict[str, float]:
    """Target count per format for the week (scaled to this week's Legal questions)."""
    cfg = ctx.settings.get("legal_weekly_formats") or {}
    a = cfg.get("start") or {"mcq": 4, "short_answer": 8, "stimulus": 2}
    b = cfg.get("end") or {"mcq": 3, "short_answer": 6, "stimulus": 4}
    p = ctx.progress
    raw = {f: (1 - p) * float(a.get(f, 0)) + p * float(b.get(f, 0)) for f in ("mcq", "short_answer", "stimulus")}
    week_n = ctx.profile.counts["LEGAL"] * len(_study_days(ctx))
    total = sum(raw.values()) or 1.0
    return {f: v * week_n / total for f, v in raw.items()}


def week_so_far(ctx: StudentContext) -> dict:
    monday = ctx.plan_date - timedelta(days=ctx.plan_date.weekday())
    rows = [h for h in ctx.legal_history if monday <= h["date"] < ctx.plan_date]
    counts = {f: 0 for f in FORMATS}
    tiers: set[int] = set()
    for h in rows:
        fmt = h["type"] if h["type"] in ("mcq", "extended", "stimulus") else ("stimulus" if h.get("stimulus_id") else "short_answer")
        counts[fmt] += 1
        if fmt != "mcq":
            tiers.add(verb_tier_of(h["type"], h.get("verb"), "", h.get("marks")))
    days = _study_days(ctx)
    done_days = sum(1 for d in days if d < ctx.plan_date.weekday())
    return {"counts": counts, "tiers": tiers, "done_days": done_days, "days": len(days)}


def _format_bonus(ctx: StudentContext, week: dict, targets: dict) -> dict[str, float]:
    k, D = week["done_days"], max(1, week["days"])
    out = {}
    for f, t in targets.items():
        expected = t * (k + 1) / D
        deficit = expected - week["counts"].get(f, 0)
        out[f] = 0.12 * max(-1.0, min(1.5, deficit))
    return out


def pick_legal(ctx: StudentContext, pool: Pool, n: int | None = None) -> tuple[list[Option], dict]:
    n = ctx.profile.counts["LEGAL"] if n is None else n
    ext = extended_plan(ctx, pool)
    targets = weekly_targets(ctx)
    week = week_so_far(ctx)
    fbonus = _format_bonus(ctx, week, targets)
    facts = {"extended": ext, "week": {"counts": week["counts"], "targets": {f: round(v, 1) for f, v in targets.items()}}}

    def fmt_of(s: Scored) -> str:
        return legal_format(s.question)

    lists: dict[str, list[Scored]] = {}
    for f, k in (("mcq", 4), ("short_answer", 6), ("stimulus", 4)):
        lists[f] = pool.ranked(lambda s, f=f: fmt_of(s) == f and s.tier <= FRESH, k=k)
    ext_cands: list[Scored] = []
    if ext["due"]:
        roots = topic_roots(ctx)
        for item_id in ext["rotation"]:
            got = pool.ranked(lambda s, i=item_id: fmt_of(s) == "extended" and roots.get(s.question.plan_item_id, s.question.plan_item_id) == i
                              and s.tier <= FRESH, k=2)
            if got:
                for s in got:
                    s.facts["rotation_topic"] = item_id
                ext_cands = got
                break
        facts["extended"]["topic"] = ext_cands[0].facts.get("rotation_topic") if ext_cands else None
        if not ext_cands:
            facts["extended"]["why"] = "no unseen extended response is available for any topic"
    fresh_total = sum(len(v) for v in lists.values())
    fallback: list[Scored] = []
    if fresh_total < n + 2:
        fallback = pool.ranked(lambda s: fmt_of(s) != "extended" and s.tier in (LADDER, RETRY, REPEAT), k=6)
    cands = [s for lst in lists.values() for s in lst] + ext_cands + fallback
    seen_ids: set[int] = set()
    uniq = []
    for s in cands:
        if s.question.id not in seen_ids:
            seen_ids.add(s.question.id)
            uniq.append(s)
    cands = uniq
    options: list[Option] = []
    size = min(n, len(cands))
    for combo in (itertools.combinations(cands, size) if size else ()):
        fmts = [fmt_of(s) for s in combo]
        n_ext = fmts.count("extended")
        if n_ext > 1 or (n_ext and not ext["due"]):
            continue
        stim_units = {s.question.stimulus_id for s in combo if s.question.stimulus_id}
        if len(stim_units) > 1:
            continue
        if any(near_duplicate(a.question, b.question) for a, b in itertools.combinations(combo, 2)):
            continue
        value = sum(s.score for s in combo)
        mcq_cap = 2 if n_ext else 1
        value -= 1.0 * max(0, fmts.count("mcq") - mcq_cap)
        tiers = [verb_tier(s.question) for s in combo]
        if n >= 2 and max(tiers) < 2:
            value -= 0.8
        if ext["due"] and ext_cands and not n_ext:
            value -= 1.2
        if n_ext:
            value += 0.3
        used: dict[str, int] = {}
        for f in fmts:
            if f == "extended":
                continue
            b = fbonus.get(f, 0.0)
            value += b if used.get(f, 0) == 0 else b * 0.5
            used[f] = used.get(f, 0) + 1
        new_tiers = {t for t in tiers if t >= 1} - week["tiers"]
        value += 0.08 * len(new_tiers)
        items = [s.question.plan_item_id for s in combo]
        value -= 0.15 * (len(items) - len(set(items)))
        reading = 0.0
        if stim_units:
            stim = next(s.question.stimulus for s in combo if s.question.stimulus_id)
            reading = reading_minutes(stim.reading_set()) if stim else 0.0
        order = {"mcq": 0, "short_answer": 1, "stimulus": 2, "extended": 3}
        ordered = sorted(combo, key=lambda s: (order[fmt_of(s)], s.question.marks))
        options.append(Option("LEGAL", ordered, round(value, 4), round(sum(s.minutes for s in combo) + reading, 2), reading,
                              facts={"formats": fmts}))
    facts["fresh_left"] = sum(1 for s in pool.cands if s.kind in ("fresh", "served") and fmt_of(s) != "extended")
    facts["fresh_by_format"] = {f: sum(1 for s in pool.cands if s.kind in ("fresh", "served") and fmt_of(s) == f) for f in FORMATS}
    return options, facts
