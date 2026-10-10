"""Daily question-selection engine.

Builds the weekday set (5 Maths, 3 English, 3 Legal) from eligible questions using the
weighted scores in ``scoring``, subject-specific composition rules, duplicate suppression and
a ~90-minute time budget. ``random.choice`` is never used."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import LearningPlanItem, Question, Subject
from app.models.common import (
    APPROVAL_APPROVED,
    DAILY_COUNTS,
    LOCKED,
    ORIGIN_ADAPTED,
    ORIGIN_GENERATED,
    ORIGIN_TRIAL,
    REJECT,
)
from app.selection.context import StudentContext
from app.selection.scoring import Scored, score
from app.services.fingerprint import NEAR_DUPLICATE, similarity

READING_WPM = 110  # careful reading speed for unseen texts


@dataclass
class DailySelection:
    items: list[Scored] = field(default_factory=list)
    expected_minutes: float = 0.0
    notes: list[str] = field(default_factory=list)

    def by_subject(self, code: str) -> list[Scored]:
        return [s for s in self.items if subject_code(s.question) == code]


_SUBJECT_CODES: dict[int, str] = {}


def subject_code(q: Question) -> str:
    return _SUBJECT_CODES[q.subject_id]


# ------------------------------------------------------------------ eligibility ---
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


def freshness_level(ctx: StudentContext, q: Question) -> int:
    """0 = fresh or due for revision; 1 = seen 7+ days ago but not yet due; 2 = seen within 7 days."""
    e = ctx.exposure.get(q.id)
    if e is None:
        return 0
    if e.next_revision_date and e.next_revision_date <= ctx.today:
        return 0
    if q.id in ctx.revision_questions:
        return 0
    if (ctx.today - e.last_seen).days >= 7:
        return 1
    return 2


def near_duplicate_of_recent(ctx: StudentContext, q: Question) -> bool:
    return any(similarity(q.question_text, t) >= NEAR_DUPLICATE for t in ctx.recent_texts)


def candidates(db: Session, ctx: StudentContext, code: str) -> dict[int, list[Scored]]:
    """Scored candidates grouped by freshness level (0 best)."""
    subj = db.execute(select(Subject).where(Subject.code == code)).scalar_one()
    qs = db.execute(
        select(Question).options(selectinload(Question.stimulus)).where(Question.subject_id == subj.id)
    ).scalars().all()
    out: dict[int, list[Scored]] = {0: [], 1: [], 2: []}
    for q in qs:
        if not is_servable(ctx, q):
            continue
        lvl = freshness_level(ctx, q)
        if lvl == 0 and q.id not in ctx.exposure and near_duplicate_of_recent(ctx, q):
            lvl = 2
        out[lvl].append(score(ctx, q, code))
    for lvl in out:
        out[lvl].sort(key=lambda s: s.score, reverse=True)
    return out


def _flatten(groups: dict[int, list[Scored]], max_level: int) -> list[Scored]:
    res: list[Scored] = []
    for lvl in range(max_level + 1):
        for s in groups[lvl]:
            if lvl:
                s.reason += " (Repeat: the fresh question bank for this area is low; import more material.)" if lvl == 2 else ""
            res.append(s)
    return res


def _not_similar(chosen: list[Scored], s: Scored) -> bool:
    return all(
        c.question.id != s.question.id and similarity(c.question.question_text, s.question.question_text) < NEAR_DUPLICATE
        for c in chosen
    )


# ------------------------------------------------------------------ Mathematics ---
def maths_difficulty_quota(ctx: StudentContext, n: int = 5) -> dict[int, int]:
    """Foundation/HSC/challenging composition. Starts at 2/2/1 and shifts with the target
    difficulty (year progress + performance). Always keeps HSC-standard work."""
    start = ctx.settings.get("maths_difficulty_start") or {"foundation": 2, "hsc": 2, "challenge": 1}
    t = ctx.target_difficulty("MATHS")
    if t < 1.35:
        q = {1: 3, 2: 2, 3: 0}
    elif t < 1.85:
        q = {1: start["foundation"], 2: start["hsc"], 3: start["challenge"]}
    elif t < 2.2:
        q = {1: 1, 2: 3, 3: 1}
    elif t < 2.6:
        q = {1: 1, 2: 2, 3: 2}
    else:
        q = {1: 0, 2: 3, 3: 2}
    total = sum(q.values())
    if total != n:
        q[2] += n - total
    return q


def maths_bucket_quota(ctx: StudentContext, n: int = 5) -> dict[str, int]:
    mix = ctx.settings.get("maths_mix") or {"learning": 0.55, "recent": 0.25, "older": 0.20}
    if ctx.mode == "holiday":
        mix = {"learning": 0.35, "recent": 0.35, "older": 0.30}
    elif ctx.mode == "exam":
        mix = {"learning": 0.3, "recent": 0.35, "older": 0.35}
    raw = {k: mix[k] * n for k in mix}
    q = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - q[k], reverse=True)[: n - sum(q.values())]:
        q[k] += 1
    return q


def pick_maths(ctx: StudentContext, groups: dict[int, list[Scored]], n: int = 5) -> list[Scored]:
    diff_q = maths_difficulty_quota(ctx, n)
    bucket_q = maths_bucket_quota(ctx, n)
    chosen: list[Scored] = []
    for max_level in (0, 1, 2):
        pool = _flatten(groups, max_level)
        # pass 1: respect both quotas; pass 2: relax difficulty; pass 3: relax bucket
        for relax in ("none", "difficulty", "bucket", "all"):
            for s in pool:
                if len(chosen) >= n:
                    break
                if not _not_similar(chosen, s):
                    continue
                d_ok = diff_q.get(s.question.difficulty, 0) > 0 or relax in ("difficulty", "all")
                b_ok = bucket_q.get(s.bucket, 0) > 0 or relax in ("bucket", "all")
                same_item = sum(1 for c in chosen if c.question.plan_item_id == s.question.plan_item_id)
                if same_item >= 3 and relax != "all":
                    continue
                same_form = sum(1 for c in chosen if c.question.source_exam and c.question.source_exam == s.question.source_exam)
                if same_form >= 1 and relax == "none":
                    continue  # vary question forms: one instance of each template level per day first
                if d_ok and b_ok:
                    chosen.append(s)
                    diff_q[s.question.difficulty] = diff_q.get(s.question.difficulty, 0) - 1
                    bucket_q[s.bucket] = bucket_q.get(s.bucket, 0) - 1
            if len(chosen) >= n:
                return chosen
    return chosen


# ---------------------------------------------------------------------- English ---
def pick_english(ctx: StudentContext, groups: dict[int, list[Scored]], n: int = 3) -> list[Scored]:
    share = float(ctx.settings.get("english_unseen_share", 0.8))
    course_share = ctx.recent_course_share
    want_course = 1 if (course_share is None and ctx.today.weekday() in (1, 3)) or (course_share is not None and course_share < (1 - share)) else 0
    chosen: list[Scored] = []
    for max_level in (0, 1, 2):
        pool = _flatten(groups, max_level)
        unseen = [s for s in pool if s.question.category == "unseen" and _not_similar(chosen, s)]
        course = [s for s in pool if s.question.category != "unseen" and _not_similar(chosen, s)]
        # group unseen by stimulus (a paired stimulus counts as one reading)
        by_stim: dict[int, list[Scored]] = {}
        for s in unseen:
            by_stim.setdefault(s.question.stimulus_id or -s.question.id, []).append(s)
        need_unseen = n - want_course - len([c for c in chosen if c.question.category == "unseen"])
        ranked = sorted(by_stim.values(), key=lambda lst: (min(len(lst), need_unseen), sum(x.score for x in lst[:need_unseen])), reverse=True)
        for lst in ranked:
            if need_unseen <= 0:
                break
            # vary marks/verbs within the stimulus: prefer distinct mark values
            lst = sorted(lst, key=lambda s: s.score, reverse=True)
            picked_marks: set[int] = set()
            for s in lst:
                if need_unseen <= 0:
                    break
                if s.question.marks in picked_marks and len(lst) > need_unseen:
                    continue
                chosen.append(s)
                picked_marks.add(s.question.marks)
                need_unseen -= 1
        need_course = n - len(chosen)
        for s in course:
            if need_course <= 0:
                break
            if s not in chosen:
                chosen.append(s)
                need_course -= 1
        # fill any remaining slot from whatever is left (unseen first)
        for s in unseen + course:
            if len(chosen) >= n:
                break
            if s not in chosen and _not_similar(chosen, s):
                chosen.append(s)
        if len(chosen) >= n:
            break
    chosen = chosen[:n]
    # keep questions on the same stimulus together, low marks first
    chosen.sort(key=lambda s: (s.question.category != "unseen", s.question.stimulus_id or 0, s.question.marks))
    return chosen


# ------------------------------------------------------------------------ Legal ---
def allow_extended(ctx: StudentContext) -> bool:
    if ctx.mode == "light":
        return False
    friday = ctx.today.weekday() == 4
    if ctx.mode == "exam":
        return ctx.sessions_since_extended >= 2
    if friday and ctx.progress >= 0.15:
        return ctx.sessions_since_extended >= 3
    if ctx.progress >= 0.6:
        return ctx.sessions_since_extended >= 4
    return False


def pick_legal(ctx: StudentContext, groups: dict[int, list[Scored]], n: int = 3) -> list[Scored]:
    """Mix formats (objective, short answer, occasional extended). Format variety is relaxed
    before freshness: a less varied day is better than repeating a question."""
    ext_ok = allow_extended(ctx)
    chosen: list[Scored] = []
    for max_level in (0, 1, 2):
        pool = _flatten(groups, max_level)
        for relaxed in (False, True):
            for s in pool:
                if len(chosen) >= n:
                    break
                if s in chosen or not _not_similar(chosen, s):
                    continue
                qt = s.question.question_type
                n_ext = sum(1 for c in chosen if c.question.question_type == "extended")
                n_type = sum(1 for c in chosen if c.question.question_type == qt)
                if qt == "extended" and (not ext_ok or n_ext >= 1):
                    continue  # never relaxed: no surprise essays, at most one a day
                if qt == "short_answer" and n_ext and n_type >= 1:
                    continue  # an extended day keeps the rest short
                if not relaxed:
                    if qt == "mcq" and n_type >= (2 if n_ext else 1):
                        continue
                    if qt == "short_answer" and n_type >= 2:
                        continue
                chosen.append(s)
            if len(chosen) >= n:
                return chosen[:n]
    return chosen[:n]


# ----------------------------------------------------------------------- Budget ---
def stimulus_minutes(questions: list[Question]) -> float:
    seen, total = set(), 0.0
    for q in questions:
        for s in (q.stimulus.reading_set() if q.stimulus else []):
            if s.id in seen:
                continue
            seen.add(s.id)
            words = len((s.body or "").split())
            total += max(2.0, words / READING_WPM) if words else 3.0
    return total


def expected_minutes(items: list[Scored]) -> float:
    qs = [s.question for s in items]
    return round(sum(q.estimated_minutes for q in qs) + stimulus_minutes(qs), 1)


def budget_bounds(ctx: StudentContext) -> tuple[float, float, float]:
    s = ctx.settings
    target = float(s.get("target_minutes", 90))
    if ctx.mode == "light":
        target = float(s.get("light_target_minutes", 45))
    elif ctx.mode == "holiday":
        target = float(s.get("holiday_target_minutes", target))
    if target == float(s.get("target_minutes", 90)) and ctx.mode not in ("light", "holiday"):
        return target, float(s.get("budget_min_minutes", 80)), float(s.get("budget_max_minutes", 95))
    return target, round(target * 0.88, 1), round(target * 1.06, 1)


def swap_ok(ctx: StudentContext, cur: Scored, alt: Scored, others: list[Scored], strict: bool) -> bool:
    """A budget swap must keep the day's educational composition intact."""
    code = subject_code(cur.question)
    cq, aq = cur.question, alt.question
    if not _not_similar(others, alt):
        return False
    if code == "MATHS":
        if aq.difficulty != cq.difficulty:
            return False  # keep the foundation / HSC / challenging composition
        if strict and alt.bucket != cur.bucket:
            return False
    elif code == "ENGLISH":
        if (aq.category == "unseen") != (cq.category == "unseen"):
            return False
        if aq.category == "unseen":
            stims = {s.question.stimulus_id for s in others if s.question.category == "unseen"}
            if stims and aq.stimulus_id not in stims:
                return False  # never add a second reading passage just to fix time
    elif code == "LEGAL":
        if strict and aq.question_type != cq.question_type:
            return False  # keep the mix of formats (objective / short / extended)
        if aq.question_type == "extended" and (not allow_extended(ctx) or any(s.question.question_type == "extended" for s in others)):
            return False
    return True


def fit_budget(ctx: StudentContext, selection: list[Scored], pools: dict[str, list[Scored]]) -> tuple[list[Scored], list[str]]:
    """Swap long questions for shorter ones (or the reverse) until the day fits the budget.
    Never removes a subject, keeps the 5/3/3 counts and the subject composition rules."""
    target, lo, hi = budget_bounds(ctx)
    notes: list[str] = []
    sel = list(selection)
    for _ in range(15):
        total = expected_minutes(sel)
        if lo <= total <= hi:
            break
        too_long = total > hi
        order = sorted(range(len(sel)), key=lambda i: sel[i].question.estimated_minutes, reverse=too_long)
        swapped = False
        for strict in ((True, False) if too_long else (True,)):
            for i in order:
                cur = sel[i]
                others = [s for j, s in enumerate(sel) if j != i]
                for alt in pools[subject_code(cur.question)]:
                    if alt in sel or not swap_ok(ctx, cur, alt, others, strict):
                        continue
                    delta = alt.question.estimated_minutes - cur.question.estimated_minutes
                    if (too_long and delta < 0) or (not too_long and delta > 0):
                        trial = sel[:i] + [alt] + sel[i + 1 :]
                        if abs(expected_minutes(trial) - target) < abs(total - target):
                            sel, swapped = trial, True
                            break
                if swapped:
                    break
            if swapped:
                break
        if not swapped:
            if too_long:
                notes.append(f"Today's set is about {total:.0f} minutes, longer than the {lo:.0f}–{hi:.0f} minute target; no shorter suitable question was available.")
            else:
                notes.append(f"Today's set is about {total:.0f} minutes, shorter than the {lo:.0f}–{hi:.0f} minute target, because the question bank for your current topics has few longer questions.")
            break
    return sel, notes


# -------------------------------------------------------------------- Top level ---
def build_daily_selection(db: Session, ctx: StudentContext) -> DailySelection:
    for s in db.execute(select(Subject)).scalars():
        _SUBJECT_CODES[s.id] = s.code
    groups = {code: candidates(db, ctx, code) for code in DAILY_COUNTS}
    maths = pick_maths(ctx, groups["MATHS"], DAILY_COUNTS["MATHS"])
    english = pick_english(ctx, groups["ENGLISH"], DAILY_COUNTS["ENGLISH"])
    legal = pick_legal(ctx, groups["LEGAL"], DAILY_COUNTS["LEGAL"])
    selection = maths + english + legal
    pools = {code: _flatten(groups[code], 1) for code in DAILY_COUNTS}
    selection, notes = fit_budget(ctx, selection, pools)
    for code, want in DAILY_COUNTS.items():
        have = sum(1 for s in selection if subject_code(s.question) == code)
        if have < want:
            notes.append(f"Only {have} of {want} {code.title()} questions are available right now: import or approve more questions for the topics you are learning.")
    return DailySelection(items=selection, expected_minutes=expected_minutes(selection), notes=notes)


def explain(ctx: StudentContext, sel: DailySelection) -> dict:
    """'Why these questions?' summary for the start of the session."""
    lines = []
    for code, label in (("MATHS", "Mathematics"), ("ENGLISH", "English"), ("LEGAL", "Legal Studies")):
        items = sel.by_subject(code)
        if not items:
            continue
        buckets: dict[str, int] = {}
        for s in items:
            buckets[s.bucket] = buckets.get(s.bucket, 0) + 1
        bits = []
        if buckets.get("learning"):
            bits.append(f"{buckets['learning']} reinforce{'s' if buckets['learning'] == 1 else ''} what you are currently learning")
        if buckets.get("recent"):
            bits.append(f"{buckets['recent']} revisit{'s' if buckets['recent'] == 1 else ''} recently learned work")
        if buckets.get("older"):
            bits.append(f"{buckets['older']} revise{'s' if buckets['older'] == 1 else ''} earlier material or Year 11 assumed knowledge")
        weak = [s for s in items if s.reason.startswith("Weak area")]
        sentence = f"{label}: " + ", ".join(bits) + "."
        if weak:
            sentence += " " + weak[0].reason
        if code == "ENGLISH":
            n_unseen = sum(1 for s in items if s.question.category == "unseen")
            sentence = f"English: {n_unseen} unseen-text question{'s' if n_unseen != 1 else ''}" + (" on one passage" if len({s.question.stimulus_id for s in items if s.question.category == 'unseen'}) == 1 else "") + (" and 1 course-linked question." if n_unseen < len(items) else ".")
        if code == "LEGAL" and any(s.question.question_type == "extended" for s in items):
            sentence += " Today includes an extended response, so the other Legal questions are shorter."
        lines.append(sentence)
    mode_note = {
        "holiday": "Holiday / revision mode: less new content, more revision and weak areas.",
        "exam": "Exam mode: more HSC-standard and unfamiliar questions under time pressure.",
        "light": "Light day: a shorter session.",
    }.get(ctx.mode)
    return {"lines": lines, "mode": ctx.mode, "mode_note": mode_note, "target_difficulty": {c: round(ctx.target_difficulty(c), 2) for c in DAILY_COUNTS}}


def days_ago(ctx: StudentContext, n: int):
    return ctx.today - timedelta(days=n)
