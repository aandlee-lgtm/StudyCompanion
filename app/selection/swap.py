"""Real-time swap of an unanswered question (owner request, 2026-10-11).

"Swap — I haven't learnt this yet" or "Swap — give me a different one". The replacement comes
from the selection engine's own machinery, not a parallel selector:

* the subject's candidate ``Pool``: hard rules (approved, plan item not LOCKED, enrichment and
  source preferences) and the eligibility tiers, so only FRESH-tier questions qualify (unseen,
  served-but-unanswered, or an exact repeat whose revision date has arrived after a different
  question on the skill). An exact repeat that the repeat rules forbid is never a replacement;
  near-duplicates of this week's questions are downgraded by ``Pool.verify`` and so excluded;
* the engine's two-stage value (plan-item priority + question fit) to rank what qualifies;
* the rules a daily set keeps: Mathematics one question per form (a template sibling with new
  numbers is not "a different one"); English, the passage is the unit, so a reading set swaps as a
  whole for an unread passage (``pick_english``); Legal, at most one multiple-choice question
  (two on an extended-response day), one stimulus and one extended response.

Among the candidates that keep those rules, the one closest in expected minutes and marks wins
(a strict window first, then a wider one, said so). With "not learnt", the same plan item is never
used again (for an unseen passage, whose plan item is always "Unseen texts", the same text form).
Nothing here writes to the database: ``app.services.sessions.swap_question`` applies the result."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, DailySession, LearningPlanItem, Question, SessionQuestion, WorkingPhoto
from app.models.common import LOCKED
from app.selection import explain as _explain
from app.selection.context import StudentContext, build_context, form_key, legal_format
from app.selection.engine import SUBJECT_LABEL, load_subject_codes, stimulus_minutes
from app.selection.english import pick_english, unit_of as unit_key
from app.selection.pool import Pool, near_duplicate, reading_minutes
from app.selection.scoring import FRESH, Scored, learning_bucket

REASONS = ("not_learnt", "different")
REASON_TEXT = {"not_learnt": "in place of a question on something you have not learnt yet",
               "different": "you asked for a different question"}
ANSWERED = ("submitted", "skipped")
FINISHED = ("completed", "closed", "missed", "skipped")
LINE_PREFIX = {"MATHS": "Mathematics:", "ENGLISH": "English:", "LEGAL": "Legal Studies"}


@dataclass
class Unit:
    """The session rows that swap together: one question, or a whole English reading set."""

    sess: DailySession
    sqs: list[SessionQuestion]
    code: str
    passage: bool = False
    stimulus_ids: tuple[int, ...] = ()

    @property
    def questions(self) -> list[Question]:
        return [x.question for x in self.sqs]

    @property
    def positions(self) -> list[int]:
        return [x.position for x in self.sqs]

    @property
    def marks(self) -> int:
        return sum(int(q.marks or 0) for q in self.questions)

    @property
    def minutes(self) -> float:
        """Expected minutes, including the reading time of a passage."""
        return round(sum(float(q.estimated_minutes or 0) for q in self.questions) + (stimulus_minutes(self.questions) if self.passage else 0.0), 1)

    @property
    def form(self) -> str | None:
        stim = self.questions[0].stimulus if self.passage else None
        return (stim.form or None) if stim else None

    def label(self) -> str:
        p = self.positions
        if len(p) == 1:
            return f"Q{p[0]}"
        return f"Q{p[0]}–Q{p[-1]}" if p == list(range(p[0], p[-1] + 1)) else ", ".join(f"Q{x}" for x in p)


@dataclass
class Replacement:
    items: list[Scored] = field(default_factory=list)
    relaxed: bool = False  # found only in the wider time/marks window
    why_none: str | None = None
    facts: dict = field(default_factory=dict)
    ctx: StudentContext | None = None


# ------------------------------------------------------------------- the unit ---
def _is_passage(sq: SessionQuestion) -> bool:
    q = sq.question
    return sq.subject_code == "ENGLISH" and q.category == "unseen" and bool(q.stimulus_id)


def _reading_ids(q: Question) -> set[int]:
    return {s.id for s in q.stimulus.reading_set()} if q.stimulus else set()


def unit_for(sess: DailySession, sq: SessionQuestion) -> Unit:
    if not _is_passage(sq):
        return Unit(sess, [sq], sq.subject_code)
    texts = _reading_ids(sq.question)
    rows = [x for x in sess.questions if _is_passage(x) and _reading_ids(x.question) & texts]
    return Unit(sess, sorted(rows, key=lambda x: x.position), "ENGLISH", passage=True, stimulus_ids=tuple(sorted(texts)))


def _pending_photos(db: Session, sq_ids: list[int]) -> set[int]:
    if not sq_ids:
        return set()
    return set(db.execute(select(WorkingPhoto.session_question_id).where(
        WorkingPhoto.session_question_id.in_(sq_ids), WorkingPhoto.attempt_id.is_(None))).scalars())


def _attempted(db: Session, sq_ids: list[int]) -> set[int]:
    if not sq_ids:
        return set()
    return set(db.execute(select(Attempt.session_question_id).where(Attempt.session_question_id.in_(sq_ids))).scalars())


def blocked_reason(db: Session, unit: Unit, *, attempted: set[int] | None = None, photos: set[int] | None = None) -> str | None:
    """Why this unit cannot be swapped (None = it can). Swapping is never possible once a question
    has been answered or skipped."""
    if unit.sess.status in FINISHED:
        return "This session is finished, so its questions can no longer be swapped."
    ids = [x.id for x in unit.sqs]
    attempted = _attempted(db, ids) if attempted is None else attempted
    photos = _pending_photos(db, ids) if photos is None else photos
    answered = [x for x in unit.sqs if x.status in ANSWERED or x.id in attempted]
    if answered:
        if unit.passage:
            return "You have already answered a question on this passage, so the passage can no longer be swapped."
        if answered[0].status == "skipped":
            return "This question was skipped (its answer was shown), so it can no longer be swapped."
        return "You have already answered this question, so it can no longer be swapped."
    if any(x.id in photos for x in unit.sqs):
        return "You have added a photo of your working to this question. Remove the photo first if you still want to swap it."
    return None


def lock_offer(unit: Unit) -> dict | None:
    """The "Also mark <topic> as not taught yet" checkbox: ticked by default for Legal topics and
    English course topics, unticked for Mathematics subtopics. Never offered for an unseen passage
    (its plan item is all unseen-text practice, which is not taught first)."""
    if unit.passage:
        return None
    q = unit.questions[0]
    item = _plan_item(unit.sess, q)
    if item is None or item.status == LOCKED:
        return None
    default = unit.code == "LEGAL" or (unit.code == "ENGLISH" and q.category != "unseen")
    return {"item_id": item.id, "name": item_name(item), "default": bool(default)}


def _plan_item(sess: DailySession, q: Question) -> LearningPlanItem | None:
    from sqlalchemy.orm import object_session

    db = object_session(sess)
    return db.get(LearningPlanItem, q.plan_item_id) if (db is not None and q.plan_item_id) else None


def item_name(item: LearningPlanItem | None) -> str:
    if item is None:
        return "general practice"
    return f"{item.code} {item.title}" if item.chapter else item.title


# --------------------------------------------------------------- the search ---
def _windows(minutes: float, marks: int, passage: bool) -> list[tuple[float, int]]:
    if passage:
        return [(max(5.0, 0.35 * minutes), max(2, round(0.25 * marks))), (max(8.0, 0.6 * minutes), max(3, round(0.5 * marks)))]
    return [(max(3.0, 0.35 * minutes), max(1, round(0.25 * marks))), (max(5.0, 0.6 * minutes), max(2, round(0.5 * marks)))]


def earlier_swaps(db: Session, sess: DailySession) -> tuple[set[int], set[int], set[str]]:
    """From this session's swap log: the questions swapped out, and the plan items (and, for
    passages, the text forms) the student said they have not learnt yet. Later swaps in the same
    session respect both, so a "not learnt" topic does not come straight back."""
    from app.models import SessionSwap

    out: set[int] = set()
    items: set[int] = set()
    forms: set[str] = set()
    for rec in db.execute(select(SessionSwap).where(SessionSwap.session_id == sess.id)).scalars():
        out.update(int(i) for i in (rec.from_question_ids or []))
        if rec.reason == "not_learnt":
            form = (rec.details or {}).get("from_form")
            if form:
                forms.add(form)
            elif rec.plan_item_id:
                items.add(rec.plan_item_id)
    return out, items, forms


def swapped_out_ids(db: Session, sess: DailySession) -> set[int]:
    return earlier_swaps(db, sess)[0]


def context_for(db: Session, sess: DailySession, unit: Unit, today: date) -> tuple[StudentContext, set[int]]:
    """The engine's context for this session's day, with everything already in the session (and
    everything swapped out of it earlier) excluded."""
    load_subject_codes(db)
    out_before = swapped_out_ids(db, sess)
    exclude = {x.question_id for x in sess.questions} | out_before
    ctx = build_context(db, today, sess.mode, session_date=sess.session_date, exclude_ids=exclude)
    stims = set(unit.stimulus_ids)
    for qid in out_before:  # a passage swapped out earlier today does not come back
        q = db.get(Question, qid)
        if q is not None and q.stimulus_id:
            stims |= _reading_ids(q)
    ctx.exclude_stimuli |= stims
    return ctx, out_before


def _legal_ok(c: Question, orig: Question, others: list[Question]) -> bool:
    fmt = legal_format(c)
    fmts = [legal_format(q) for q in others]
    if fmt == "extended" and legal_format(orig) != "extended":
        return False  # an extended response comes only from the extended-response plan
    if fmt == "extended" and "extended" in fmts:
        return False
    stims = {q.stimulus_id for q in others if q.stimulus_id}
    if c.stimulus_id and stims and c.stimulus_id not in stims:
        return False  # one scenario or data set to read per day
    cap = 2 if ("extended" in fmts or fmt == "extended") else 1
    if fmt == "mcq" and legal_format(orig) != "mcq" and fmts.count("mcq") >= cap:
        return False
    return True


def _closeness(s: Scored, orig: Question, minutes: float, marks: int, code: str) -> float:
    pen = 0.8 * abs(s.minutes - minutes) / max(minutes, 1.0) + 0.15 * abs(int(s.question.marks or 0) - marks)
    if code == "LEGAL" and legal_format(s.question) != legal_format(orig):
        pen += 0.25
    if code == "MATHS":
        pen += 0.1 * abs((s.question.difficulty or 2) - (orig.difficulty or 2))
    return pen


def _single(ctx: StudentContext, pool: Pool, unit: Unit, reason: str, swapped_before: list[Question],
            avoid_items: set[int] = frozenset()) -> Replacement:
    orig = unit.questions[0]
    code = unit.code
    others = [x.question for x in unit.sess.questions if x.subject_code == code and x.id != unit.sqs[0].id]
    counts = {"pool": 0, "fresh": 0, "topic": 0, "rules": 0}
    stage: list[Scored] = []
    other_forms = {form_key(q) for q in others} if code == "MATHS" else set()
    orig_form = form_key(orig) if code == "MATHS" else None
    for s in pool.cands:
        q = s.question
        if code == "ENGLISH" and q.category == "unseen":
            continue  # a course task is replaced by a course task (a passage swaps as a whole set)
        counts["pool"] += 1
        if s.tier != FRESH:
            continue
        counts["fresh"] += 1
        if (reason == "not_learnt" and q.plan_item_id == orig.plan_item_id) or q.plan_item_id in avoid_items:
            continue
        counts["topic"] += 1
        if code == "MATHS":
            f = pool.form(s)
            if f == orig_form or f in other_forms:
                continue  # one question per form per session; a sibling with new numbers is not "different"
        if code == "LEGAL" and not _legal_ok(q, orig, others):
            continue
        counts["rules"] += 1
        stage.append(s)
    nearest = None
    for k, (dmin, dmarks) in enumerate(_windows(unit.minutes, unit.marks, False)):
        best, best_v = None, None
        for s in stage:
            if abs(s.minutes - unit.minutes) > dmin or abs(int(s.question.marks or 0) - unit.marks) > dmarks:
                continue
            pool.verify(s)  # near-duplicates of this week's questions drop out of the FRESH tier
            if s.tier != FRESH:
                continue
            if any(near_duplicate(s.question, o) for o in [*others, orig, *swapped_before]):
                continue
            v = s.score - _closeness(s, orig, unit.minutes, unit.marks, code)
            if best_v is None or v > best_v:
                best, best_v = s, v
        if best is not None:
            return Replacement([best], relaxed=k > 0, facts={"counts": counts, "window": [round(dmin, 1), dmarks]})
    if stage:
        nearest = min(stage, key=lambda s: abs(s.minutes - unit.minutes)).minutes
    return Replacement([], why_none=_why_none(unit, reason, counts, nearest), facts={"counts": counts})


def _passage(ctx: StudentContext, pool: Pool, unit: Unit, reason: str, avoid_forms: set[str] = frozenset()) -> Replacement:
    n = len(unit.sqs)
    options, _facts = pick_english(ctx, pool, n)
    fresh_units: set = set()
    topic_units: set = set()
    stage = []
    for o in options:
        key = o.facts.get("unit")
        if not key or key[0] == "q" or o.facts.get("course") or o.facts.get("course_only") or len(o.items) != n:
            continue
        if not o.facts.get("fresh_passage") or any(s.tier != FRESH for s in o.items):
            continue  # an unread passage only: a read passage is never offered again as unseen
        if set(key) & ctx.exclude_stimuli:
            continue
        fresh_units.add(key)
        if (reason == "not_learnt" and unit.form and o.facts.get("form") == unit.form) or o.facts.get("form") in avoid_forms:
            continue  # "not learnt" for a passage: not the same kind of text again
        topic_units.add(key)
        stage.append(o)
    pool_units = {unit_key(ctx, s) for s in pool.cands if s.question.category == "unseen" and s.question.stimulus_id}
    pool_units = {k for k in pool_units if not set(k) & ctx.exclude_stimuli}
    counts = {"pool": len(pool_units), "fresh": len(fresh_units), "topic": len(topic_units), "rules": len(topic_units)}
    for k, (dmin, dmarks) in enumerate(_windows(unit.minutes, unit.marks, True)):
        fits = [o for o in stage if abs(o.minutes - unit.minutes) <= dmin
                and abs(sum(int(s.question.marks or 0) for s in o.items) - unit.marks) <= dmarks]
        if fits:
            best = max(fits, key=lambda o: o.value - 0.8 * abs(o.minutes - unit.minutes) / max(unit.minutes, 1.0))
            return Replacement(sorted(best.items, key=lambda s: s.question.marks), relaxed=k > 0,
                               facts={"counts": counts, "window": [round(dmin, 1), dmarks], "minutes": best.minutes,
                                      "reading": best.reading})
    nearest = min((o.minutes for o in stage), key=lambda m: abs(m - unit.minutes)) if stage else None
    return Replacement([], why_none=_why_none(unit, reason, counts, nearest), facts={"counts": counts})


def _why_none(unit: Unit, reason: str, counts: dict, nearest: float | None) -> str:
    subj = SUBJECT_LABEL[unit.code]
    orig = unit.questions[0]
    if unit.passage:
        if counts.get("pool") == 0:
            return "there is no other passage in the question bank (add reading sets to have a choice)"
        if counts["fresh"] == 0:
            return "every passage in the bank has been read in the last few weeks, and a read passage is never offered again as unseen"
        if counts["topic"] == 0:
            return f"every unread passage left is {(unit.form or 'this kind of text').lower()}, which you said you have not studied yet"
        return (f"no unread passage takes a similar time: this set was about {round(unit.minutes)} minutes including reading"
                + (f"; the closest left is about {round(nearest)} minutes" if nearest else ""))
    if counts.get("pool") == 0:
        return (f"there are no other {subj} questions for the topics you have started (import or approve more questions "
                "to have a choice)")
    if counts["fresh"] == 0:
        return (f"every other {subj} question on the topics you have started has been answered recently, and an exact repeat "
                "is not allowed before its revision date")
    if counts["topic"] == 0:
        return f"the only new {subj} questions left are on {_explain_item(unit)}, which you have not learnt yet"
    if counts["rules"] == 0:
        return {
            "MATHS": "the new Mathematics questions left are the same kind of question as ones already in today's set "
                     "(one question of each kind per session)",
            "LEGAL": "the new Legal Studies questions left would break today's mix (at most one multiple-choice question, "
                     "one stimulus to read and one extended response)",
            "ENGLISH": "there is no other new course-linked task",
        }[unit.code]
    marks = int(orig.marks or 0)
    return (f"no new {subj} question takes a similar time: this one was {marks} mark{'s' if marks != 1 else ''} and about "
            f"{round(unit.minutes)} minutes" + (f"; the closest left takes about {round(nearest)} minutes" if nearest else ""))


def _explain_item(unit: Unit) -> str:
    return item_name(_plan_item(unit.sess, unit.questions[0]))


def find_replacement(db: Session, unit: Unit, reason: str, today: date) -> Replacement:
    """The engine's best replacement for ``unit`` (no database writes)."""
    if reason not in REASONS:
        raise ValueError("Choose why you want to swap this question.")
    ctx, out_before = context_for(db, unit.sess, unit, today)
    _out, avoid_items, avoid_forms = earlier_swaps(db, unit.sess)
    pool = Pool(db, ctx, unit.code)
    swapped_before = [q for q in (db.get(Question, i) for i in out_before) if q is not None]
    rep = (_passage(ctx, pool, unit, reason, avoid_forms) if unit.passage
           else _single(ctx, pool, unit, reason, swapped_before, avoid_items))
    for s in rep.items:
        s.reason = _explain.reason_for(ctx, s, unit.code)
    rep.ctx = ctx
    return rep


# ------------------------------------------------------------ explanation ---
def _scored_rows(ctx: StudentContext, sqs: list[SessionQuestion]) -> list[Scored]:
    out = []
    for x in sqs:
        bd = x.score_breakdown or {}
        bucket = bd.get("bucket") or learning_bucket(ctx, ctx.plan.get(x.question.plan_item_id or -1))
        out.append(Scored(x.question, float(bd.get("total") or 0.0), bd, bucket, x.reason or "", tier=int(bd.get("tier") or 0),
                          kind=bd.get("kind") or "fresh", facts={"flags": list(bd.get("flags") or [])}))
    return out


def subject_line(ctx: StudentContext, sess: DailySession, code: str) -> str | None:
    """The "Why these questions?" line for one subject, rebuilt from the engine's facts after a swap."""
    from app.selection import legal as _legal

    rows = [x for x in sess.questions if x.subject_code == code]
    if not rows:
        return None
    items = _scored_rows(ctx, rows)
    if code == "MATHS":
        return _explain.maths_line(ctx, items, {})
    if code == "ENGLISH":
        reading = stimulus_minutes([s.question for s in items if s.question.category == "unseen"])
        return _explain.english_line(ctx, items, {}, reading)
    week = _legal.week_so_far(ctx)
    targets = _legal.weekly_targets(ctx)
    facts = {"extended": _legal.extended_plan(ctx), "week": {"counts": week["counts"], "targets": {f: round(v, 1) for f, v in targets.items()}}}
    return _explain.legal_line(ctx, items, facts)


def refreshed_explanation(ctx: StudentContext, sess: DailySession, code: str) -> dict:
    """A copy of the session's explanation with the subject's line, minutes and total updated."""
    expl = dict(sess.explanation or {})
    line = subject_line(ctx, sess, code)
    prefix = LINE_PREFIX[code]
    lines, replaced = [], False
    for ln in expl.get("lines") or []:
        if ln.startswith(prefix):
            if line and not replaced:
                lines.append(line)
            replaced = True
            continue
        lines.append(ln)
    if line and not replaced:
        lines.insert(min(len(lines), ("MATHS", "ENGLISH", "LEGAL").index(code)), line)
    expl["lines"] = lines
    rows = [x.question for x in sess.questions if x.subject_code == code]
    reading = stimulus_minutes(rows) if rows else 0.0
    sm = dict(expl.get("subject_minutes") or {})
    sm[code] = round(sum(float(q.estimated_minutes or 0) for q in rows) + reading, 2)
    expl["subject_minutes"] = sm
    rd = dict(expl.get("reading") or {})
    rd[code] = round(reading, 1)
    expl["reading"] = rd
    t = dict(expl.get("time") or {})
    t["total"] = round(sum(sm.values()), 1)
    if t.get("lo") is not None and t.get("hi") is not None:
        t["in_window"] = t["lo"] <= t["total"] <= t["hi"]
    expl["time"] = t
    return expl


def reading_of(items: list[Scored]) -> float:
    stims = []
    seen = set()
    for s in items:
        for st in (s.question.stimulus.reading_set() if s.question.stimulus else []):
            if st.id not in seen:
                seen.add(st.id)
                stims.append(st)
    return reading_minutes(stims)
