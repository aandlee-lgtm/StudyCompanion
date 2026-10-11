"""Mastery, spaced repetition and revision scheduling (sections 12, 19 and 23).

v2 model (owner: adaptive):

* ``assess`` is an explicit confidence x correctness x corroboration table. A lucky correct guess
  is *unconfirmed* (checked again soon with a different question); a wrong answer given with
  great confidence is a *misconception* (highest priority); a slip is only treated as a slip when
  it is corroborated (strong prior mastery on the skill AND a slip pattern or a correct method).
* Evidence is weighted by how reliable the mark is (deterministic 1.0 ... offline estimate 0.2).
  Offline estimates never create weak revision items on their own.
* Revision items have a lifecycle: served items are closed first (with the attempt that served
  them and its outcome), then the next item is queued from the new result.
* Intervals start from the section-12 bands and adapt: repeated success grows the interval by the
  question's ease (capped at 180 days / the HSC); a lapse resets it and lowers the ease.
* Skills whose mastery stays very low enter a *rebuild* state (worked example -> faded example ->
  foundation question) until two correct answers.
* Every scheduling change is logged as an ``ExposureEvent`` and can be undone (used when a
  self-mark is changed or an offline estimate is confirmed).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, ExposureEvent, LearningPlanItem, Mastery, Question, QuestionExposure, RevisionQueue
from app.models.common import LEARNED, LEARNING, REVISION
from app.services.settings import REVIEW_INTERVALS

# Section-5C slip-like error types and section-23 slip-like topic tags.
SLIP_CATEGORIES = {"careless error", "careless", "arithmetic", "sign", "sign error", "notation", "calculator error"}
INTENSITY = {"light": 1.2, "normal": 1.0, "intense": 0.8}
CONFIDENCE_LEVELS = ("guess", "unsure", "confident", "very_confident")
CONFIDENCE_LABELS = {"guess": "Guess", "unsure": "Unsure", "confident": "Reasonably confident", "very_confident": "Very confident"}

# How much a mark can be trusted as evidence (adaptive-06).
RELIABILITY = {"deterministic": 1.0, "skipped": 1.0, "ai_official": 0.8, "ai": 0.6, "self": 0.6, "offline_estimate": 0.2}
REVISIT_GROUP = ("weak_revisit", "unconfirmed_check", "misconception", "slip_check", "rebuild", "pattern")
KIND_LABELS = {
    "weak_revisit": "Weak answer", "unconfirmed_check": "Unconfirmed (guess/unsure)", "misconception": "Misconception",
    "slip_check": "Slip check", "rebuild": "Step-by-step rebuild", "pattern": "Repeated error", "recycle": "Two-month recycle",
}
KIND_URGENCY = {"misconception": 6, "rebuild": 5, "pattern": 4.5, "weak_revisit": 4, "unconfirmed_check": 2, "slip_check": 1, "recycle": 0}
REBUILD_ENTER_MASTERY = 0.35
REBUILD_MIN_ATTEMPTS = 4
REBUILD_EXIT_CORRECT = 2
RECYCLE_DAYS = 60
MAX_INTERVAL = 180


@dataclass
class Outcome:
    kind: str  # strong|unconfirmed|adequate|slow|weak|very_weak|misconception|slip|skipped
    bucket: str  # exact-question interval band: strong|adequate|weak|very_weak
    evidence: float  # 0..1, before reliability weighting
    revisit_kind: str | None = None  # a DIFFERENT question on the same skill: weak_revisit|unconfirmed_check|misconception|slip_check
    revisit_days: int | None = None
    priority: float = 0.0


def reliability_of(method: str | None, official: bool = False) -> float:
    if method == "ai" and official:
        return RELIABILITY["ai_official"]
    return RELIABILITY.get(method or "deterministic", 0.6)


def assess(fraction: float, confidence: str | None, category: str | None, skipped: bool, *, prior_mastery: float | None = None,
           prior_attempts: int = 0, slip_evidence: bool = False, topic_tag: str | None = None) -> Outcome:
    """Confidence x correctness x corroboration (section 19, adaptive-05)."""
    conf = confidence if confidence in CONFIDENCE_LEVELS else None
    if skipped:
        return Outcome("skipped", "very_weak", 0.0, "weak_revisit", 2, 1.0)
    if fraction >= 0.85:
        if conf == "guess":
            return Outcome("unconfirmed", "weak", 0.5, "unconfirmed_check", 3, 0.7)
        if conf == "unsure":
            return Outcome("unconfirmed", "weak", 0.6, "unconfirmed_check", 5, 0.6)
        return Outcome("strong", "strong", 1.0)
    if fraction >= 0.6:
        factor = {"guess": 0.6, "unsure": 0.8}.get(conf or "", 1.0)
        ev = round(fraction * factor, 3)
        if ev >= 0.6:
            return Outcome("adequate", "adequate", ev)
        return Outcome("weak", "weak", ev, "weak_revisit", 5, 0.8)
    slip_like = (category or "").lower() in SLIP_CATEGORIES or (topic_tag or "").lower() in SLIP_CATEGORIES
    corroborated = slip_like and slip_evidence and prior_mastery is not None and prior_mastery >= 0.75 and prior_attempts >= 3
    if corroborated:
        return Outcome("slip", "adequate", round(min(prior_mastery, 0.6), 3), "slip_check", 10, 0.5)
    if conf == "very_confident":
        return Outcome("misconception", "very_weak", round(fraction * 0.5, 3), "misconception", 1, 1.2)
    if fraction >= 0.35:
        return Outcome("weak", "weak", round(fraction, 3), "weak_revisit", 5, 0.8)
    return Outcome("very_weak", "very_weak", round(fraction, 3), "weak_revisit", 2, 1.0)


def quality(fraction: float, confidence: str | None, category: str | None, skipped: bool, **kw) -> tuple[str, float]:
    """Backward-compatible wrapper: (interval bucket, mastery evidence 0..1)."""
    o = assess(fraction, confidence, category, skipped, **kw)
    return o.bucket, o.evidence


def interval_days(bucket: str, previous_interval: int | None, intensity: str = "normal") -> int:
    """Section-12 starting bands. Repeated success pushes towards the long end of the range."""
    lo, hi = REVIEW_INTERVALS[bucket]
    days = hi if previous_interval and previous_interval >= lo else lo
    return max(1, round(days * INTENSITY.get(intensity, 1.0)))


def scaled(days: int, intensity: str) -> int:
    return max(1, round(days * INTENSITY.get(intensity, 1.0)))


def nice_date(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


# ------------------------------------------------------------------ queue helpers ---
def _open_items(db: Session, plan_item_id: int | None, question_id: int | None = None) -> list[RevisionQueue]:
    db.flush()  # the session does not autoflush: items closed a moment ago must not be found as open
    q = select(RevisionQueue).where(RevisionQueue.status == "open")
    q = q.where(RevisionQueue.plan_item_id == plan_item_id) if plan_item_id else q.where(RevisionQueue.question_id == question_id)
    return [r for r in db.execute(q.order_by(RevisionQueue.due_date, RevisionQueue.id)).scalars() if r.status == "open"]


def _reason(kind: str, item: LearningPlanItem | None, tag: str | None = None) -> str:
    name = item.title if item else "this skill"
    return {
        "weak_revisit": f"Weak answer on {name}: practise this skill again with a different question.",
        "unconfirmed_check": f"Correct on {name}, but not yet confirmed (guess/unsure): check it with a different question.",
        "misconception": f"Wrong while very confident on {name}: the exact idea to fix, with a different question.",
        "slip_check": f"Probable slip on {name}: a quick re-check with a different question.",
        "rebuild": f"{name} needs attention: step-by-step practice (worked example first).",
        "pattern": f"Repeated error ({tag}) on {name}: a targeted question.",
        "recycle": f"Two-month recycle of {name}, which you answered well.",
    }.get(kind, f"Revision of {name}.")


def _snap_item(r: RevisionQueue) -> dict:
    return {"id": r.id, "due_date": r.due_date.isoformat(), "reason": r.reason, "priority": r.priority, "kind": r.kind, "status": r.status,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None, "served_by_attempt_id": r.served_by_attempt_id,
            "outcome": r.outcome, "tag": r.tag}


def queue_item(db: Session, *, plan_item_id: int | None, kind: str, due: date, priority: float, reason: str | None = None,
               tag: str | None = None, source_attempt_id: int | None = None, question_id: int | None = None, undo: dict | None = None) -> RevisionQueue:
    """Create or merge an open revision item. One open 'revisit' item and one open 'recycle' item per skill;
    a merge keeps the earlier date, the higher priority and the more urgent kind."""
    item = db.get(LearningPlanItem, plan_item_id) if plan_item_id else None
    group = "recycle" if kind == "recycle" else "revisit"
    existing = next((r for r in _open_items(db, plan_item_id, question_id)
                     if ("recycle" if r.kind == "recycle" else "revisit") == group and (kind != "pattern" or r.kind != "pattern" or r.tag == tag)), None)
    if existing is not None:
        if undo is not None:
            undo.setdefault("modified", []).append(_snap_item(existing))
        if group == "recycle":
            existing.due_date = due  # re-dated from the LAST success
        else:
            if KIND_URGENCY.get(kind, 0) >= KIND_URGENCY.get(existing.kind, 0):
                existing.kind, existing.tag = kind, tag or existing.tag
                existing.reason = reason or _reason(kind, item, tag)
                existing.source_attempt_id = source_attempt_id or existing.source_attempt_id
            existing.due_date = min(existing.due_date, due)
        existing.priority = max(existing.priority, priority)
        return existing
    r = RevisionQueue(plan_item_id=plan_item_id, question_id=question_id, due_date=due, reason=reason or _reason(kind, item, tag),
                      priority=priority, kind=kind, tag=tag, source_attempt_id=source_attempt_id)
    db.add(r)
    db.flush()
    if undo is not None:
        undo.setdefault("created", []).append(r.id)
    return r


def _close_served(db: Session, attempt: Attempt, question: Question, today: date, undo: dict) -> list[RevisionQueue]:
    """Close open items for this skill that were due: this counted attempt served them.

    A revisit asks for a DIFFERENT question, so the question that queued it does not serve it."""
    served = []
    for r in _open_items(db, question.plan_item_id, None if question.plan_item_id else question.id):
        if r.due_date > today:
            continue
        if r.kind in REVISIT_GROUP and r.source_attempt_id:
            src = db.get(Attempt, r.source_attempt_id)
            if src is not None and src.question_id == question.id:
                continue
        undo.setdefault("modified", []).append(_snap_item(r))
        r.status, r.completed_at, r.served_by_attempt_id, r.outcome = "done", today, attempt.id, round(attempt.fraction, 3)
        served.append(r)
    return served


# ----------------------------------------------------------------------- record ---
def _snapshot_exposure(exp: QuestionExposure | None) -> dict | None:
    if exp is None:
        return None
    return {"first_seen": exp.first_seen.isoformat(), "last_seen": exp.last_seen.isoformat(), "attempts": exp.attempts,
            "score_history": list(exp.score_history or []), "mastery": exp.mastery, "interval_days": exp.interval_days,
            "next_revision_date": exp.next_revision_date.isoformat() if exp.next_revision_date else None, "ease": exp.ease, "lapses": exp.lapses}


def _snapshot_mastery(m: Mastery | None) -> dict | None:
    if m is None:
        return None
    return {"mastery": m.mastery, "attempts": m.attempts, "last_seen": m.last_seen.isoformat() if m.last_seen else None,
            "next_revision_date": m.next_revision_date.isoformat() if m.next_revision_date else None, "state": m.state,
            "state_since": m.state_since.isoformat() if m.state_since else None, "rebuild_correct": m.rebuild_correct,
            "lapses": m.lapses, "ease": m.ease, "last_success": m.last_success.isoformat() if m.last_success else None}


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _days_to_hsc(today: date, hsc: str | None) -> int | None:
    try:
        return (date.fromisoformat(hsc) - today).days if hsc else None
    except ValueError:
        return None


def _mark_weight(marks: float) -> float:
    """A 15-mark extended response is stronger evidence than a 1-mark MCQ (adaptive-09)."""
    return max(0.75, min(1.5, 0.75 + 0.25 * math.log2(max(1.0, float(marks)))))


def touch_pending(db: Session, attempt: Attempt, question: Question, today: date) -> dict:
    """Mark a question as seen while its mark is pending (self-marking): no evidence yet, but it is
    not served again as 'fresh' and no exact repeat happens within a week."""
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == question.id)).scalar_one_or_none()
    if exp is None:
        exp = QuestionExposure(question_id=question.id, first_seen=today, last_seen=today, attempts=0, score_history=[], mastery=0.0,
                               interval_days=7, next_revision_date=today + timedelta(days=7))
        db.add(exp)
    else:
        exp.last_seen = today
        exp.next_revision_date = max(exp.next_revision_date or today, today + timedelta(days=7))
    db.flush()
    return {"pending": True, "headline": "Your mark is pending: record it below to update your schedule.",
            "next_revision": exp.next_revision_date.isoformat()}


def record(db: Session, attempt: Attempt, question: Question, today: date, intensity: str = "normal", category: str | None = None, *,
           topic_tag: str | None = None, slip_evidence: bool = False, method: str | None = None, official: bool | None = None,
           hsc_date: str | None = None) -> dict:
    """Update exposure, mastery and the revision queue after a COUNTED attempt; returns the schedule payload
    (including a learner-facing headline and the undo snapshot)."""
    method = method or attempt.marking_method or "deterministic"
    official = attempt.official_guideline_used if official is None else official
    estimated = method == "offline_estimate"
    reliability = reliability_of(method, official)
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == question.id)).scalar_one_or_none()
    m = db.execute(select(Mastery).where(Mastery.plan_item_id == question.plan_item_id)).scalar_one_or_none() if question.plan_item_id else None
    item = db.get(LearningPlanItem, question.plan_item_id) if question.plan_item_id else None
    undo: dict = {"exposure": _snapshot_exposure(exp), "mastery": _snapshot_mastery(m), "mastery_existed": m is not None,
                  "exposure_existed": exp is not None, "created": [], "modified": []}

    o = assess(attempt.fraction, attempt.confidence, category, attempt.skipped, prior_mastery=m.mastery if m else None,
               prior_attempts=m.attempts if m else 0, slip_evidence=slip_evidence, topic_tag=topic_tag)
    est_seconds = (question.estimated_minutes or 0) * 60
    if o.kind == "strong" and attempt.time_seconds and est_seconds and attempt.time_seconds > 2 * est_seconds + 60:
        o = Outcome("slow", "adequate", 0.8)  # correct but slow: not yet fluent
    bucket = o.bucket
    if estimated:  # an offline estimate is weak evidence: neither very short nor very long intervals
        bucket = {"strong": "adequate", "very_weak": "weak"}.get(bucket, bucket)

    # ---- exact question: interval with ease and lapses (adaptive-07)
    prev_interval = exp.interval_days if exp else None
    prev_success = bool(exp and exp.score_history and exp.score_history[-1] >= 0.85)
    ease = exp.ease if exp else 2.0
    lapses = exp.lapses if exp else 0
    if bucket == "strong" and prev_interval and prev_success and prev_interval >= REVIEW_INTERVALS["strong"][1]:
        cap = MAX_INTERVAL
        dth = _days_to_hsc(today, hsc_date)
        if dth and dth > REVIEW_INTERVALS["strong"][0]:
            cap = min(cap, dth)
        days = min(cap, round(prev_interval * ease))
    else:
        days = interval_days(bucket, prev_interval if (exp and bucket == "strong") else None, intensity)
    if o.kind in ("very_weak", "misconception", "skipped") and prev_success:
        lapses += 1
        ease = max(1.3, round(ease - 0.2, 2))
    elif o.kind == "strong" and prev_success and not estimated:
        ease = min(2.6, round(ease + 0.1, 2))
    if exp is None:
        exp = QuestionExposure(question_id=question.id, first_seen=today, last_seen=today, attempts=0, score_history=[])
        db.add(exp)
    exp.last_seen = today
    exp.attempts = (exp.attempts or 0) + 1
    exp.score_history = list(exp.score_history or []) + [round(attempt.fraction, 3)]
    exp.mastery = round(0.6 * (exp.mastery or 0) + 0.4 * o.evidence, 3) if exp.attempts > 1 else round(o.evidence, 3)
    exp.interval_days, exp.ease, exp.lapses = days, ease, lapses
    exp.next_revision_date = today + timedelta(days=days)

    revisit_due = None
    recycle_due = None
    if question.plan_item_id:
        if m is None:
            m = Mastery(plan_item_id=question.plan_item_id, mastery=0.5, attempts=0, state="normal", rebuild_correct=0, lapses=0, ease=2.0)
            db.add(m)
        alpha = 0.35 if m.attempts >= 3 else 0.5
        rate = min(0.8, alpha * reliability * _mark_weight(question.marks))
        m.mastery = round(m.mastery + rate * (o.evidence - m.mastery), 3)
        m.attempts += 1
        m.last_seen = today
        if attempt.fraction >= 0.85 and not attempt.skipped:
            m.last_success = today
        if o.kind in ("very_weak", "misconception") and m.last_success and m.last_success < today and m.mastery < 0.6:
            m.lapses = (m.lapses or 0) + 1

        # 1) close the items this attempt served (adaptive-03)
        _close_served(db, attempt, question, today, undo)
        # 2) queue the next item from the new result: a DIFFERENT question on the same skill
        if o.revisit_kind and not estimated:
            revisit_due = today + timedelta(days=scaled(o.revisit_days, intensity))
            queue_item(db, plan_item_id=question.plan_item_id, kind=o.revisit_kind, due=revisit_due, priority=o.priority,
                       tag=topic_tag, source_attempt_id=attempt.id, undo=undo)
        # 3) two-month recycle, anchored to the LAST success, only for learned/revision/Year 11 skills
        recyclable = item is not None and (item.status in (LEARNED, REVISION) or item.is_assumed_knowledge)
        if o.kind == "strong" and recyclable and not estimated:
            recycle_due = today + timedelta(days=scaled(RECYCLE_DAYS, intensity))
            queue_item(db, plan_item_id=question.plan_item_id, kind="recycle", due=recycle_due, priority=0.6,
                       source_attempt_id=attempt.id, undo=undo)
        # 4) rebuild state for struggling skills (adaptive-19)
        _update_rebuild(db, m, item, attempt, o, today, intensity, undo)
        m.next_revision_date = min((r.due_date for r in _open_items(db, question.plan_item_id)), default=None)

    ev = ExposureEvent(question_id=question.id, attempt_id=attempt.id, plan_item_id=question.plan_item_id, study_date=today,
                       fraction=round(attempt.fraction, 3), evidence=o.evidence, reliability=reliability, confidence=attempt.confidence,
                       method=method, outcome_kind=o.kind, bucket=bucket, interval_days=days, time_seconds=attempt.time_seconds or 0,
                       after_reveal=bool(attempt.after_reveal), counted=True)
    db.add(ev)
    db.flush()
    undo["event_id"] = ev.id
    sched = {"bucket": bucket, "kind": o.kind, "interval_days": days, "next_revision": exp.next_revision_date.isoformat(),
             "revisit": {"kind": o.revisit_kind, "due": revisit_due.isoformat()} if revisit_due else None,
             "recycle": recycle_due.isoformat() if recycle_due else None, "estimated": estimated, "reliability": reliability,
             "evidence": o.evidence, "rebuild": bool(m and m.state == "rebuild"), "undo": undo}
    sched["headline"] = headline(sched, attempt.confidence, item)
    return sched


def _update_rebuild(db: Session, m: Mastery, item: LearningPlanItem | None, attempt: Attempt, o: Outcome, today: date,
                    intensity: str, undo: dict) -> None:
    if m.state == "rebuild":
        if attempt.fraction >= 0.85 and not attempt.skipped:
            m.rebuild_correct = (m.rebuild_correct or 0) + 1
            if m.rebuild_correct >= REBUILD_EXIT_CORRECT:
                m.state, m.state_since, m.rebuild_correct = "normal", today, 0
                for r in _open_items(db, m.plan_item_id):
                    if r.kind == "rebuild":
                        undo.setdefault("modified", []).append(_snap_item(r))
                        r.status, r.completed_at, r.served_by_attempt_id, r.outcome = "done", today, attempt.id, round(attempt.fraction, 3)
        return
    if m.mastery < REBUILD_ENTER_MASTERY and m.attempts >= REBUILD_MIN_ATTEMPTS and o.kind not in ("strong", "unconfirmed", "adequate", "slow"):
        m.state, m.state_since, m.rebuild_correct = "rebuild", today, 0
        queue_item(db, plan_item_id=m.plan_item_id, kind="rebuild", due=today + timedelta(days=1), priority=1.1,
                   source_attempt_id=attempt.id, undo=undo)


# --------------------------------------------------------------- learner labels ---
def headline(sched: dict, confidence: str | None, item: LearningPlanItem | None = None) -> str:
    """Learner-facing scheduling message, separate from the internal bucket (adaptive-17)."""
    kind = sched.get("kind")
    nxt = date.fromisoformat(sched["next_revision"])
    rv = sched.get("revisit") or {}
    rv_day = nice_date(date.fromisoformat(rv["due"])) if rv.get("due") else None
    exact = f"this exact question returns after {nice_date(nxt)}"
    if kind == "strong":
        s = f"Correct — {exact} (about {round(sched['interval_days'] / 7)} weeks)."
        if sched.get("recycle"):
            s += f" The skill comes back for a two-month recycle around {nice_date(date.fromisoformat(sched['recycle']))}."
    elif kind == "unconfirmed":
        how = "you guessed" if confidence == "guess" else "you were unsure"
        s = f"Correct — but {how}, so this skill is checked again on {rv_day} with a different question; {exact}."
    elif kind == "slow":
        s = f"Correct, but it took more than twice the suggested time — {exact}, and the skill stays in regular practice."
    elif kind == "adequate":
        s = f"Mostly there — {exact}."
    elif kind == "slip":
        s = f"Not correct — this looks like a slip (your recent work on this skill is strong); a quick re-check with a different question on {rv_day}."
    elif kind == "misconception":
        s = f"Not correct, and you were very confident — this is the exact idea to fix. A different question on this skill comes on {rv_day}; {exact}."
    elif kind == "skipped":
        s = f"Skipped — recorded honestly, not as correct. This skill comes back on {rv_day} with a different question; {exact}."
    elif kind == "weak":
        s = f"Partly correct — this skill comes back on {rv_day} with a different question; {exact}."
    else:
        s = f"Not correct — this skill comes back on {rv_day} with a different question; {exact}."
    if sched.get("estimated"):
        s = (s.split(" — ")[0] + " (estimate)") + f" — {exact}. Mark confidence: low (offline estimate), so no extra revision was queued; confirm the mark against the criteria to update your schedule."
    if sched.get("rebuild"):
        s += " This skill is now in step-by-step practice: a worked example comes first."
    return s


# ------------------------------------------------------------------------ undo ---
def revert(db: Session, undo: dict | None) -> bool:
    """Undo one ``record`` call (self-mark changed, estimate confirmed). Refuses (returns False) when a later
    counted event exists for the same question or skill, because that evidence was built on this one."""
    if not undo or not undo.get("event_id"):
        return False
    ev = db.get(ExposureEvent, undo["event_id"])
    if ev is None:
        return False
    later = select(func.count(ExposureEvent.id)).where(ExposureEvent.id > ev.id, ExposureEvent.counted.is_(True))
    later = later.where((ExposureEvent.question_id == ev.question_id) | ((ExposureEvent.plan_item_id == ev.plan_item_id) if ev.plan_item_id else False))
    if db.execute(later).scalar_one():
        return False
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == ev.question_id)).scalar_one_or_none()
    snap = undo.get("exposure")
    if exp is not None:
        if snap is None:
            db.delete(exp)
        else:
            exp.first_seen, exp.last_seen = _d(snap["first_seen"]), _d(snap["last_seen"])
            exp.attempts, exp.score_history, exp.mastery = snap["attempts"], snap["score_history"], snap["mastery"]
            exp.interval_days, exp.next_revision_date = snap["interval_days"], _d(snap["next_revision_date"])
            exp.ease, exp.lapses = snap["ease"], snap["lapses"]
    if ev.plan_item_id:
        m = db.execute(select(Mastery).where(Mastery.plan_item_id == ev.plan_item_id)).scalar_one_or_none()
        ms = undo.get("mastery")
        if m is not None:
            if ms is None:
                db.delete(m)
            else:
                m.mastery, m.attempts, m.last_seen = ms["mastery"], ms["attempts"], _d(ms["last_seen"])
                m.next_revision_date, m.state, m.state_since = _d(ms["next_revision_date"]), ms["state"], _d(ms["state_since"])
                m.rebuild_correct, m.lapses, m.ease, m.last_success = ms["rebuild_correct"], ms["lapses"], ms["ease"], _d(ms["last_success"])
    for rid in undo.get("created", []):
        r = db.get(RevisionQueue, rid)
        if r is not None:
            db.delete(r)
    for s in reversed(undo.get("modified", [])):
        r = db.get(RevisionQueue, s["id"])
        if r is not None:
            r.due_date, r.reason, r.priority, r.kind, r.status = _d(s["due_date"]), s["reason"], s["priority"], s["kind"], s["status"]
            r.completed_at, r.served_by_attempt_id, r.outcome, r.tag = _d(s["completed_at"]), s["served_by_attempt_id"], s["outcome"], s["tag"]
    db.delete(ev)
    db.flush()
    return True


def log_rehearsal(db: Session, attempt: Attempt, question: Question, today: date) -> None:
    """Rehearsal (retry / practice of a not-yet-due or revealed question) is kept in the log but is never evidence."""
    db.add(ExposureEvent(question_id=question.id, attempt_id=attempt.id, plan_item_id=question.plan_item_id, study_date=today,
                         fraction=round(attempt.fraction, 3), evidence=0.0, reliability=0.0, confidence=attempt.confidence,
                         method=attempt.marking_method, outcome_kind="rehearsal", bucket="", interval_days=0,
                         time_seconds=attempt.time_seconds or 0, after_reveal=bool(attempt.after_reveal), counted=False))
    db.flush()


# --------------------------------------------------------------- read helpers ---
def calibration(db: Session, since: date | None = None) -> list[dict]:
    """How often answers at each confidence level were right (counted attempts only)."""
    q = select(Attempt).where(Attempt.counts_for_mastery.is_(True), Attempt.skipped.is_(False), Attempt.confidence.is_not(None))
    if since:
        q = q.where(Attempt.submitted_at >= datetime.combine(since, datetime.min.time()))
    stats: dict[str, list[int]] = {}
    for a in db.execute(q).scalars():
        if a.marking_method == "offline_estimate":
            continue
        s = stats.setdefault(a.confidence, [0, 0])
        s[1] += 1
        s[0] += 1 if a.fraction >= 0.85 else 0
    out = []
    for level in CONFIDENCE_LEVELS:
        if level in stats and stats[level][1]:
            right, n = stats[level]
            pct = round(100 * right / n)
            out.append({"level": level, "label": CONFIDENCE_LABELS[level], "n": n, "right": right, "pct": pct,
                        "text": f"Your '{CONFIDENCE_LABELS[level]}' answers were right {pct}% of the time ({right} of {n})."})
    return out


def recent_accuracy(db: Session, plan_item_id: int, n: int = 7) -> tuple[int, int]:
    """(correct, total) over the last ``n`` counted, reliably marked attempts on a skill — real accuracy, not mastery."""
    rows = db.execute(select(ExposureEvent).where(ExposureEvent.plan_item_id == plan_item_id, ExposureEvent.counted.is_(True),
                                                  ExposureEvent.method != "offline_estimate")
                      .order_by(ExposureEvent.id.desc()).limit(n)).scalars().all()
    return sum(1 for r in rows if r.fraction >= 0.85), len(rows)


def struggling(db: Session) -> list[tuple[LearningPlanItem, Mastery]]:
    """Skills in the rebuild state (for a calm 'needs attention' note)."""
    rows = db.execute(select(Mastery).where(Mastery.state == "rebuild")).scalars().all()
    return [(db.get(LearningPlanItem, m.plan_item_id), m) for m in rows]


def outcome_dict(o: Outcome) -> dict:
    return asdict(o)


__all__ = ["assess", "quality", "interval_days", "record", "revert", "touch_pending", "log_rehearsal", "queue_item", "headline",
           "calibration", "recent_accuracy", "struggling", "reliability_of", "LEARNING"]
