"""Daily question-selection engine (spec 10–14).

1. Every servable question gets an eligibility tier (fresh / due exact repeat / fallbacks) and a
   two-stage score: plan-item priority (configurable weights) + question fit (``scoring``).
2. Each subject proposes complete candidate sets that respect its rules: Mathematics allocates
   slots to plan items and keeps one question per form (``maths``); English uses one passage as
   the unit (``english``); Legal follows its weekly format and extended-response plans (``legal``).
3. ``optimiser.choose`` picks one set per subject to maximise value within the day's time window
   (a real constraint, with per-subject envelopes), recording any time trade-offs.
``random.choice`` is never used; tie-breaks are deterministic per day."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, Subject
from app.selection import explain as _explain
from app.selection.context import StudentContext, legal_format
from app.selection.english import pick_english
from app.selection.legal import pick_legal
from app.selection.maths import maths_bucket_quota, maths_difficulty_quota, pick_maths  # noqa: F401  (re-exported)
from app.selection.optimiser import Option, choose
from app.selection.pool import READING_WPM, Pool, reading_minutes  # noqa: F401
from app.selection.scoring import Scored, is_servable  # noqa: F401
from app.selection.explain import item_name

SUBJECT_ORDER = ("MATHS", "ENGLISH", "LEGAL")
SUBJECT_LABEL = {"MATHS": "Mathematics", "ENGLISH": "English", "LEGAL": "Legal Studies"}


@dataclass
class DailySelection:
    items: list[Scored] = field(default_factory=list)
    expected_minutes: float = 0.0
    notes: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def by_subject(self, code: str) -> list[Scored]:
        return [s for s in self.items if subject_code(s.question) == code]


_SUBJECT_CODES: dict[int, str] = {}


def subject_code(q: Question) -> str:
    return _SUBJECT_CODES[q.subject_id]


def load_subject_codes(db: Session) -> None:
    for s in db.execute(select(Subject)).scalars():
        _SUBJECT_CODES[s.id] = s.code


# ----------------------------------------------------------------------- Budget ---
def stimulus_minutes(questions: list[Question]) -> float:
    seen, stims = set(), []
    for q in questions:
        for s in (q.stimulus.reading_set() if q.stimulus else []):
            if s.id not in seen:
                seen.add(s.id)
                stims.append(s)
    return reading_minutes(stims)


def expected_minutes(items: list[Scored]) -> float:
    qs = [s.question for s in items]
    return round(sum(q.estimated_minutes for q in qs) + stimulus_minutes(qs), 1)


def budget_bounds(ctx: StudentContext) -> tuple[float, float, float]:
    """(target, lo, hi) minutes for the day, from the mode profile."""
    p = ctx.profile
    return p.target, p.lo, p.hi


# ----------------------------------------------------------------- bank health ---
def _bank_notes(ctx: StudentContext, sel_items: list[Scored], subj_facts: dict, options: dict, tfacts: dict) -> tuple[list[str], dict]:
    notes: list[str] = []
    bank: dict = {}
    ef = subj_facts.get("ENGLISH", {})
    lf = subj_facts.get("LEGAL", {})
    if "ENGLISH" in subj_facts:
        left = ef.get("passages_left", 0)
        bank["ENGLISH"] = {"passages_left": left, "course_left": ef.get("course_left", 0)}
        if left <= 5:
            notes.append(f"English: {left} unread passage{'s' if left != 1 else ''} left (about {left} day{'s' if left != 1 else ''} of unseen "
                         "practice). Add reading sets to keep unseen practice fresh.")
    if "LEGAL" in subj_facts:
        fb = lf.get("fresh_by_format", {})
        bank["LEGAL"] = fb
        if lf.get("fresh_left", 0) < 3 * ctx.profile.counts["LEGAL"]:
            notes.append(f"Legal Studies: only {lf.get('fresh_left', 0)} unseen questions left "
                         f"({fb.get('mcq', 0)} objective, {fb.get('short_answer', 0)} short answer, {fb.get('stimulus', 0)} stimulus). "
                         "Add questions so repeats are not needed.")
    # the time window
    total, lo, hi = tfacts.get("total", 0), tfacts.get("lo", 0), tfacts.get("hi", 0)
    if not tfacts.get("in_window") and total:
        shortfalls = []
        for code, opts in options.items():
            if not opts:
                continue
            elo, ehi = ctx.profile.envelopes.get(code, (0, 999))
            longest, shortest = max(o.minutes for o in opts), min(o.minutes for o in opts)
            if total < lo and longest < elo:
                items = _join_names(ctx, {s.question.plan_item_id for s in sel_items if subject_code(s.question) == code})
                what = {"MATHS": f"today's topics ({items}) only have short questions; multi-part 4–6 mark questions would help",
                        "ENGLISH": "the passages and course tasks available carry few marks",
                        "LEGAL": "few longer short-answer or stimulus questions are available"}[code]
                shortfalls.append(f"{SUBJECT_LABEL[code]} can reach only about {round(longest)} min: {what}")
            if total > hi and shortest > ehi:
                shortfalls.append(f"{SUBJECT_LABEL[code]} has no set shorter than about {round(shortest)} min today")
        side = "shorter" if total < lo else "longer"
        msg = f"Today's set is about {round(total)} minutes, {side} than the {lo:.0f}–{hi:.0f} minute window"
        notes.append(msg + (": " + "; ".join(shortfalls) + "." if shortfalls else "."))
    swapped = {code: d for code, d in (tfacts.get("displaced") or {}).items() if d.get("out") and d.get("value_cost", 0) >= 0.05}
    if swapped:
        parts = [f"{SUBJECT_LABEL[c]} {len(d['out'])}" for c, d in swapped.items()]
        longer = sum(d.get("minutes_gain", 0) for d in swapped.values()) > 0
        notes.append(f"Time fit: to bring the day {'up to' if longer else 'within'} the time window, a few questions were swapped for "
                     f"{'longer' if longer else 'shorter'} ones on today's topics ({', '.join(parts)}); weak-area and revision-due "
                     "questions are never swapped out.")
    return notes, bank


def _join_names(ctx: StudentContext, ids) -> str:
    names = [item_name(ctx, i) for i in ids if i]
    return ", ".join(names[:3]) or "today's topics"


# -------------------------------------------------------------------- Top level ---
def build_daily_selection(db: Session, ctx: StudentContext) -> DailySelection:
    load_subject_codes(db)
    counts = ctx.profile.counts
    pools = {code: Pool(db, ctx, code) for code in SUBJECT_ORDER if counts.get(code, 0) > 0}
    try:  # fallback ladder rung (b): AI variants on the same skill when a provider is configured
        from app.selection.variants import top_up_with_variants

        if top_up_with_variants(db, ctx, pools):
            pools = {code: Pool(db, ctx, code) for code in pools}
    except Exception:  # pragma: no cover - never block a day on an AI failure
        pass
    pickers = {"MATHS": pick_maths, "ENGLISH": pick_english, "LEGAL": pick_legal}
    options: dict[str, list[Option]] = {}
    subj_facts: dict[str, dict] = {}
    for code, pool in pools.items():
        options[code], subj_facts[code] = pickers[code](ctx, pool, counts[code])
    chosen, tfacts = choose(options, budget_bounds(ctx), ctx.profile.envelopes)
    items: list[Scored] = []
    for code in SUBJECT_ORDER:
        if code in chosen:
            items.extend(chosen[code].items)
    for s in items:
        s.reason = _explain.reason_for(ctx, s, subject_code(s.question))
    notes, bank = _bank_notes(ctx, items, subj_facts, options, tfacts)
    for code in SUBJECT_ORDER:
        want = counts.get(code, 0)
        have = len(chosen[code].items) if code in chosen else 0
        if have < want:
            notes.append(f"Only {have} of {want} {SUBJECT_LABEL[code]} questions are available right now: import or approve more "
                         "questions for the topics you are learning.")
    mf = subj_facts.get("MATHS") or {}
    q_learn, got_learn = (mf.get("quota") or {}).get("learning", 0), sum(
        1 for s in items if subject_code(s.question) == "MATHS" and s.bucket == "learning")
    if got_learn < q_learn:  # selection-17: say which current topic is short of questions, and what to do
        empty = list(mf.get("learning_without_questions") or [])
        short = [i for i, v in (mf.get("info") or {}).items() if v.get("bucket") == "learning"]
        names = _join_names(ctx, dict.fromkeys(empty + short)) if (empty or short) else "the topics you are learning"
        what = (f"there are no practice questions yet for {_join_names(ctx, empty)}" if empty and not short else
                f"there are not enough different questions on {names}")
        notes.append(f"Only {got_learn} of {q_learn} current-learning Mathematics slots could be filled today: {what}. Import or "
                     "approve questions for it, or enable AI variants; the other slots went to recent work.")
    ext = subj_facts.get("LEGAL", {}).get("extended") or {}
    if ext.get("due") and not any(legal_format(s.question) == "extended" for s in items if subject_code(s.question) == "LEGAL"):
        notes.append("An extended response was due today, but " + (ext.get("why") or "none fitted today's time window") + ".")
    facts = {**subj_facts, "time": tfacts, "bank": bank,
             "subject_minutes": {c: o.minutes for c, o in chosen.items()},
             "reading": {c: o.reading for c, o in chosen.items()}}
    return DailySelection(items=items, expected_minutes=expected_minutes(items), notes=notes, facts=facts)


def explain(ctx: StudentContext, sel: DailySelection) -> dict:
    return _explain.explain(ctx, sel)


def days_ago(ctx: StudentContext, n: int):
    return ctx.today - timedelta(days=n)
