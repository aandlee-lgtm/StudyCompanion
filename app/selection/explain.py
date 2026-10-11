"""Reasons and 'Why these questions?' built from the engine's own facts (selection-19, spec 46).

Every statement is derived from data the engine used: the plan item and its bucket, the student's
TRUE recent accuracy ('3 of 5 correct', not the mastery estimate), revision dates, repeats and
why, catch-up after a missed day, the time trade-offs and the mode."""
from __future__ import annotations

from app.selection.context import StudentContext, english_demand, legal_format
from app.selection.scoring import Scored

OFFLINE_METHODS = {"offline_estimate", "self_mark", "self_marked", "offline"}
FORMAT_LABEL = {"mcq": "objective (multiple choice)", "short_answer": "short answer", "stimulus": "stimulus-based", "extended": "extended response"}


def item_name(ctx: StudentContext, item_id: int | None) -> str:
    item = ctx.plan.get(item_id or -1)
    if item is None:
        return "general practice"
    return f"{item.code} {item.title}" if item.chapter else item.title


def accuracy_text(ctx: StudentContext, item_id: int | None) -> str | None:
    acc = ctx.accuracy(item_id)
    if acc is None:
        return None
    correct, n, mean = acc
    methods = ctx.item_methods.get(item_id or -1, set())
    if methods & OFFLINE_METHODS or (methods and "deterministic" not in methods):
        label = " (includes offline estimates)" if methods & OFFLINE_METHODS else ""
        return f"your last {n} answer{'s' if n != 1 else ''} averaged {round(100 * mean)}%{label}"
    return f"you answered {correct} of {n} correctly"


def _d(x) -> str:
    return f"{x:%a %d %b}" if x else "—"


def reason_for(ctx: StudentContext, s: Scored, code: str) -> str:
    q, kind = s.question, s.kind
    name = item_name(ctx, q.plan_item_id)
    flags = set(s.facts.get("flags") or [])
    e = ctx.exposure.get(q.id)
    acc = accuracy_text(ctx, q.plan_item_id)
    if kind == "due" and e is not None:
        last = e.score_history[-1] if e.score_history else 0
        return (f"Revision due: you answered this exact question on {_d(e.last_seen)} ({round(100 * last)}%); its revision "
                f"date was {_d(e.next_revision_date)} and you have practised {name} with a different question since.")
    if kind == "ladder" and e is not None:
        return (f"Repeat, because fresh questions on {name} have run out: last seen {_d(e.last_seen)}, revision date "
                f"{_d(e.next_revision_date)}. Import or approve more questions for this area.")
    if kind == "retry" and e is not None:
        last = e.score_history[-1] if e.score_history else 0
        return (f"Rewrite task: improve your answer from {_d(e.last_seen)} ({round(100 * last)}%). Fresh questions on {name} "
                "have run out, so rewriting is the most useful practice today.")
    if kind in ("repeat", "near_duplicate"):
        seen = _d(e.last_seen) if e else "recently"
        what = "a question very similar to one you saw" if kind == "near_duplicate" else "this question, last seen"
        return f"Repeat: {what} {seen}. The question bank for {name} is low; import or approve more questions."
    if "catch_up" in flags:
        cu = ctx.catch_up.get(q.plan_item_id, {})
        return f"Catch-up from your missed session: revision of {name} fell due on {_d(cu.get('due'))}."
    if "weak_focus" in flags:
        return f"Holiday focus on a weak area: {name}" + (f" ({acc})." if acc else ".")
    if "rebuild" in flags:
        return f"Rebuilding {name}: {acc}." if acc else f"Rebuilding {name}."
    if "coverage_due" in flags and s.bucket != "learning":
        last = ctx.item_last_practised.get(q.plan_item_id or -1)
        return (f"Coverage: you have not practised {name} since {_d(last)}; every earlier topic comes back within a few weeks."
                if last else f"Coverage: {name} has not been practised yet.")
    if "revision_due" in flags:
        due = ctx.revision_item_due.get(q.plan_item_id)
        return (f"Scheduled revision of {name} (due {_d(due)}): a different question on a skill you found difficult"
                + (f" ({acc})." if acc else "."))
    if code == "ENGLISH":
        demand = english_demand(q)
        if q.category == "unseen":
            stim = q.stimulus
            title = f"'{stim.title}'" if stim else "an unseen text"
            return f"Unseen text {title}: a {q.marks}-mark {q.directive_verb or demand} question ({demand})."
        return f"Course-linked practice for {name}: {q.marks}-mark {q.directive_verb or ''} task.".replace("  ", " ")
    if code == "LEGAL":
        fmt = legal_format(q)
        if fmt == "extended":
            return f"Extended response on {name}: next in the topic rotation."
        base = f"{FORMAT_LABEL[fmt].capitalize()} on {name}"
        if fmt != "mcq":
            base += f" ({q.marks}-mark {q.directive_verb or 'response'})"
        if acc and s.bucket != "learning":
            base += f"; {acc}"
        return base + "."
    m = ctx.mastery.get(q.plan_item_id or -1)
    if acc and m is not None and m.attempts >= 3 and m.mastery < 0.6:
        return f"Weak area: {acc} on {name} recently."
    item = ctx.plan.get(q.plan_item_id or -1)
    if s.bucket == "learning":
        return f"Reinforces what you are currently learning: {name}."
    if item is not None and item.is_assumed_knowledge:
        return f"Year 11 assumed knowledge revision: {item.title}."
    if s.bucket == "recent":
        learned = ctx.learned_on.get(q.plan_item_id)
        return f"Keeps recently learned material fresh: {name}" + (f" (learned around {_d(learned)})." if learned else ".")
    if ctx.item_attempts.get(q.plan_item_id or -1, 0) == 0:
        return f"Coverage: {name} has not been practised yet."
    return f"Spaced revision of earlier material: {name}."


def _join(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _count(n: int, one: str, many: str) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    return f"{words.get(n, n)} {one if n == 1 else many}"


def maths_line(ctx: StudentContext, items: list[Scored], facts: dict) -> str:
    groups: dict[str, dict[int | None, int]] = {"learning": {}, "recent": {}, "older": {}}
    for s in items:
        groups[s.bucket][s.question.plan_item_id] = groups[s.bucket].get(s.question.plan_item_id, 0) + 1
    bits = []
    if groups["learning"]:
        names = _join([item_name(ctx, i) for i in groups["learning"]])
        k = sum(groups["learning"].values())
        bits.append(f"{_count(k, 'question reinforces', 'questions reinforce')} {names}, which you are learning now")
    if groups["recent"]:
        names = _join([item_name(ctx, i) for i in groups["recent"]])
        k = sum(groups["recent"].values())
        bits.append(f"{_count(k, 'revisits', 'revisit')} recently learned work ({names})")
    older = groups["older"]
    if older:
        y11 = [i for i in older if ctx.plan.get(i or -1) is not None and ctx.plan[i].is_assumed_knowledge]
        earlier = [i for i in older if i not in y11]
        if earlier:
            bits.append(f"{_count(sum(older[i] for i in earlier), 'revises', 'revise')} earlier work ({_join([item_name(ctx, i) for i in earlier])})")
        if y11:
            bits.append(f"{_count(sum(older[i] for i in y11), 'revises', 'revise')} Year 11 assumed knowledge ({_join([ctx.plan[i].title for i in y11])})")
    line = "Mathematics: " + "; ".join(bits) + "."
    weak = []
    for i in dict.fromkeys(s.question.plan_item_id for s in items):
        m = ctx.mastery.get(i or -1)
        acc = accuracy_text(ctx, i)
        if acc and m is not None and m.attempts >= 3 and m.mastery < 0.6:
            weak.append(f"{item_name(ctx, i)} is here because {acc} there recently")
    if weak:
        line += " " + "; ".join(weak[:2]) + "."
    if facts.get("learning_without_questions"):
        names = _join([item_name(ctx, i) for i in facts["learning_without_questions"]])
        line += f" There are no practice questions yet for {names} (currently Learning): import some, or use AI variants, so today's learning slots went to related work."
    return line


def english_line(ctx: StudentContext, items: list[Scored], facts: dict, reading: float) -> str:
    unseen = [s for s in items if s.question.category == "unseen"]
    course = [s for s in items if s.question.category != "unseen"]
    parts = []
    if unseen:
        stim = unseen[0].question.stimulus
        texts = stim.reading_set() if stim else []
        title = " and ".join(f"'{t.title}'" for t in texts) or "an unseen text"
        form = " / ".join(dict.fromkeys(t.form for t in texts if t.form)) or "unseen text"
        marks = _join([f"{s.question.marks}" for s in unseen]) + "-mark"
        demands = ", ".join(dict.fromkeys(english_demand(s.question) for s in unseen))
        parts.append(f"today's text is {title} ({form.lower()}, about {max(1, round(reading))} min reading) with "
                     f"{marks} question{'s' if len(unseen) > 1 else ''} ({demands})")
        if facts.get("reread"):
            parts.append("every passage has been read in the last 10 weeks, so this one is a re-read")
    if course:
        names = _join(list(dict.fromkeys(item_name(ctx, s.question.plan_item_id) for s in course)))
        if unseen:
            parts.append(f"plus a course-linked task on {names} (about a fifth of English work is course-linked)")
        else:
            parts.append(f"no fresh unseen passage is available, so today is course-linked practice on {names}")
    return "English: " + "; ".join(parts) + "."


def legal_line(ctx: StudentContext, items: list[Scored], facts: dict) -> str:
    by_item: dict[int | None, list[Scored]] = {}
    for s in items:
        by_item.setdefault(s.question.plan_item_id, []).append(s)
    bits = []
    for i, lst in by_item.items():
        descr = _join([(f"a {s.question.marks}-mark {s.question.directive_verb or ''} " if legal_format(s.question) != "mcq" else "an ")
                       .replace("  ", " ") + FORMAT_LABEL[legal_format(s.question)] + " question" for s in lst])
        bits.append(f"{item_name(ctx, i)}: {descr}")
    line = "Legal Studies — " + "; ".join(bits) + "."
    ext = facts.get("extended") or {}
    has_ext = any(legal_format(s.question) == "extended" for s in items)
    if has_ext:
        line += (f" Today includes an extended response (about {ext.get('per_month', 0):.0f} a month at this point in the year, "
                 "rotating through your topics), so the other Legal questions are shorter.")
    week = facts.get("week") or {}
    counts, targets = week.get("counts") or {}, week.get("targets") or {}
    if targets.get("stimulus"):
        done = counts.get("stimulus", 0) + sum(1 for s in items if legal_format(s.question) == "stimulus")
        line += f" Stimulus-based questions this week: {done} of about {round(targets['stimulus'])}."
    return line


def time_line(ctx: StudentContext, sel_minutes: float, tfacts: dict, subject_minutes: dict) -> list[str]:
    lo, hi = tfacts.get("lo"), tfacts.get("hi")
    out = [f"Expected time: about {round(sel_minutes)} minutes (target window {lo:.0f}–{hi:.0f})."]
    return out


def explain(ctx: StudentContext, sel) -> dict:
    """'Why these questions?' — structured facts plus readable lines."""
    f = sel.facts
    lines = []
    for code in ("MATHS", "ENGLISH", "LEGAL"):
        items = sel.by_subject(code)
        if not items:
            continue
        sf = f.get(code, {})
        if code == "MATHS":
            lines.append(maths_line(ctx, items, sf))
        elif code == "ENGLISH":
            lines.append(english_line(ctx, items, sf, f.get("reading", {}).get("ENGLISH", 0.0)))
        else:
            lines.append(legal_line(ctx, items, sf))
    cu = [s for s in sel.items if "catch_up" in (s.facts.get("flags") or [])]
    if cu:
        lines.append(f"Catch-up: {len(cu)} question{'s' if len(cu) != 1 else ''} revise work that fell due on the day you missed, "
                     "in place of lower-priority questions (nothing extra was added).")
    repeats = [s for s in sel.items if s.kind in ("ladder", "retry", "repeat", "near_duplicate")]
    if repeats:
        lines.append(f"{len(repeats)} question{'s are repeats or rewrites' if len(repeats) != 1 else ' is a repeat or rewrite'} because "
                     "the fresh question bank for that area has run out (see each question's reason).")
    if ctx.phase.name != "companion":
        lines.append(ctx.phase.note)
    if ctx.profile.timed and ctx.mode == "normal":
        lines.append("Today is a timed session: work under exam conditions; the countdown shows the time left.")
    mode_note = " ".join(ctx.profile.notes) or None
    return {
        "lines": lines,
        "mode": ctx.mode,
        "mode_note": mode_note,
        "time": f.get("time", {}),
        "subject_minutes": f.get("subject_minutes", {}),
        "reading": {k: round(v, 1) for k, v in (f.get("reading") or {}).items()},
        "difficulty": {"band": f.get("MATHS", {}).get("band"), "quota": {str(k): v for k, v in (f.get("MATHS", {}).get("difficulty_quota") or {}).items()},
                       "target": round(ctx.target_difficulty("MATHS"), 2)},
        "target_difficulty": {c: round(ctx.target_difficulty(c), 2) for c in ("MATHS", "ENGLISH", "LEGAL")},
        "bank": f.get("bank", {}),
        "extended": f.get("LEGAL", {}).get("extended"),
        "timed": ctx.profile.timed,
        "phase": {"name": ctx.phase.name, "label": ctx.phase.label, "progress": round(ctx.progress, 3)},
    }
