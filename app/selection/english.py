"""English: the reading passage is the unit of freshness (selection-04, english-19).

A day is ONE unseen passage (or one deliberate paired set) with differently weighted questions,
sometimes with a course-linked task (about 20% of English questions over time). A passage that has
been read is not offered as an unseen text again for ``unseen_passage_cooldown_days``. When no
fresh passage is left, the day is course-linked / Craft of Writing tasks, with the reason stated,
rather than a second or re-read passage."""
from __future__ import annotations

import itertools

from app.selection.context import ENGLISH_DEMANDS, StudentContext, demand_from_verb, english_demand
from app.selection.optimiser import Option
from app.selection.pool import Pool, reading_minutes
from app.selection.scoring import FRESH, REPEAT, Scored

COURSE_ONLY_PENALTY = 1.5  # only when a fresh passage exists
REREAD_PENALTY = 2.5
DUP_MARKS_PENALTY = 0.6


def unit_of(ctx: StudentContext, s: Scored) -> tuple:
    sid = s.question.stimulus_id
    if not sid:
        return ("q", s.question.id)
    return ctx.stimulus_unit.get(sid, (sid,))


def want_course(ctx: StudentContext) -> bool:
    target = 1.0 - float(ctx.settings.get("english_unseen_share", 0.8))
    share = ctx.recent_course_share
    if share is None:
        return ctx.plan_date.weekday() in (1, 3)
    return share < target


def _demand_bonus(ctx: StudentContext, chosen: list[Scored]) -> float:
    """Rolling cognitive-demand mix: favour demands (identify ... synthesise) not practised lately."""
    seen: dict[str, int] = {d: 0 for d in ENGLISH_DEMANDS}
    for h in ctx.english_history[:15]:
        d = demand_from_verb(h.get("verb"))
        seen[d] = seen.get(d, 0) + 1
    bonus = 0.0
    for d in {english_demand(s.question) for s in chosen}:
        bonus += 0.06 if seen.get(d, 0) == 0 else (0.03 if seen.get(d, 0) <= 1 else 0.0)
    return bonus


def _recent_forms(ctx: StudentContext, pool: Pool) -> list[str]:
    forms = []
    stim_forms = {s.question.stimulus_id: (s.question.stimulus.form if s.question.stimulus else None) for s in pool.cands if s.question.stimulus_id}
    for h in ctx.english_history:
        if h.get("stimulus_id") and h["stimulus_id"] in stim_forms and stim_forms[h["stimulus_id"]]:
            if not forms or forms[-1] != stim_forms[h["stimulus_id"]]:
                forms.append(stim_forms[h["stimulus_id"]])
        if len(forms) >= 3:
            break
    return forms


def pick_english(ctx: StudentContext, pool: Pool, n: int | None = None) -> tuple[list[Option], dict]:
    n = ctx.profile.counts["ENGLISH"] if n is None else n
    cooldown = int(ctx.settings.get("unseen_passage_cooldown_days", 70) or 70)
    course_wanted = want_course(ctx)
    facts: dict = {"want_course": course_wanted, "fresh_passages": 0, "reread": False}

    units: dict[tuple, list[Scored]] = {}
    for s in pool.cands:
        if s.question.category == "unseen" and s.tier <= REPEAT:
            units.setdefault(unit_of(ctx, s), []).append(s)
    course = pool.ranked(lambda s: s.question.category != "unseen" and s.tier <= FRESH, k=6)
    if len(course) < n:
        extra = pool.ranked(lambda s: s.question.category != "unseen" and s.tier > FRESH, k=6)
        course = course + [s for s in extra if s not in course][: 6 - len(course)]
    recent_forms = _recent_forms(ctx, pool)

    passage_opts: list[Option] = []
    for key, members in units.items():
        if key[0] != "q" and any(m in ctx.exclude_stimuli for m in key):
            continue
        last = max((ctx.stimulus_last_read[m] for m in key if m in ctx.stimulus_last_read), default=None)
        fresh_passage = last is None or (ctx.today - last).days >= cooldown
        verified = [pool.verify(s) for s in members]
        elig = sorted((s for s in verified if s.tier <= FRESH), key=lambda s: -s.score)[:6]
        if len(elig) < min(2, n):  # last resort: questions from the fallback ladder (penalised by tier)
            elig = sorted((s for s in verified if s.tier <= REPEAT), key=lambda s: (s.tier, -s.score))[:6]
        if not elig:
            continue
        stim = elig[0].question.stimulus
        reading = reading_minutes(stim.reading_set()) if stim else 0.0
        form = stim.form if stim else None
        base_pen = 0.0 if fresh_passage else REREAD_PENALTY
        if form and form in recent_forms:
            base_pen += 0.15 * (3 - recent_forms.index(form)) / 3
        if fresh_passage and len(elig) >= min(2, n):
            facts["fresh_passages"] += 1
        for k_unseen in sorted({n, n - 1, 1}, reverse=True):
            if k_unseen < 1 or k_unseen > len(elig):
                continue
            n_course = n - k_unseen
            if n_course and not course:
                continue
            for combo in itertools.combinations(elig, k_unseen):
                marks = [s.question.marks for s in combo]
                pen = base_pen + (DUP_MARKS_PENALTY if len(set(marks)) < len(marks) else 0.0)
                if k_unseen == 1 and n > 2:
                    pen += 1.0  # one question on a passage wastes the reading and strands its other questions
                value = sum(s.score for s in combo) + _demand_bonus(ctx, list(combo)) - pen
                if n_course == 0:
                    passage_opts.append(Option("ENGLISH", sorted(combo, key=lambda s: s.question.marks), round(value, 4),
                                               round(sum(s.minutes for s in combo) + reading, 2), reading,
                                               facts={"unit": key, "fresh_passage": fresh_passage, "form": form}))
                    continue
                for cc in itertools.combinations(course[:4], n_course):
                    v = value + sum(s.score for s in cc) + (0.4 if course_wanted else -0.3)
                    passage_opts.append(Option("ENGLISH", sorted(combo, key=lambda s: s.question.marks) + list(cc), round(v, 4),
                                               round(sum(s.minutes for s in combo) + sum(s.minutes for s in cc) + reading, 2), reading,
                                               facts={"unit": key, "fresh_passage": fresh_passage, "form": form, "course": n_course}))
    has_fresh = any(o.facts.get("fresh_passage") for o in passage_opts)
    facts["reread"] = bool(passage_opts) and not has_fresh
    course_opts: list[Option] = []
    if len(course) >= n:
        for cc in itertools.combinations(course[:6], n):
            modules = {s.question.plan_item_id for s in cc}
            v = sum(s.score for s in cc) - (0.2 * (n - len(modules))) - (COURSE_ONLY_PENALTY if has_fresh else 0.0)
            course_opts.append(Option("ENGLISH", list(cc), round(v, 4), round(sum(s.minutes for s in cc), 2), 0.0,
                                      facts={"unit": None, "course_only": True}))
    if not course_opts and course and len(course) < n:  # fewer course tasks than slots: still offer them
        course_opts.append(Option("ENGLISH", list(course), round(sum(s.score for s in course) - 3.0 * (n - len(course)), 4),
                                  round(sum(s.minutes for s in course), 2), 0.0, facts={"unit": None, "course_only": True}))
    options = passage_opts + course_opts
    if not options and course:  # not enough of anything: give what exists
        options = [Option("ENGLISH", course[:n], round(sum(s.score for s in course[:n]) - 3.0, 4),
                          round(sum(s.minutes for s in course[:n]), 2), 0.0, facts={"unit": None, "course_only": True})]
    facts["passages_left"] = sum(1 for key, members in units.items()
                                 if sum(1 for s in members if s.kind in ("fresh", "served")) >= min(3, n)
                                 and not any(m in ctx.stimulus_last_read for m in key if key[0] != "q"))
    facts["course_left"] = sum(1 for s in pool.cands if s.question.category != "unseen" and s.kind in ("fresh", "served"))
    return options, facts
