"""Submission: attempts, feedback records, error journal, mastery updates, self-marking (owner: adaptive).

One attempt chain per question (adaptive-02). Each attempt is classified:

* ``first``        — the first time the question is answered: counted evidence.
* ``due_repeat``   — an exact repeat on/after its ``next_revision_date``: counted evidence.
* ``early_repeat`` — the first attempt in a daily session on a question that was not yet due
                     (the selection engine chose it): counted evidence.
* ``retry``        — a later attempt in the same sitting (Try again): rehearsal, never evidence.
* ``rehearsal``    — practice of a not-yet-due question, or of a question already answered or
                     revealed today: shown in history, never changes mastery or schedules.

Only counted attempts update exposure, mastery, revision items and the error journal."""
from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.ai.factory import get_provider
from app.marking import rubric
from app.models import Attempt, AttemptFeedback, ErrorJournal, Question, QuestionExposure, SessionQuestion
from app.services import error_journal, mastery
from app.services import settings as st
from app.services.assessment.common import subject_code
from app.services.assessment.maths import mark_deterministic
from app.services.assessment.written import mark_written

TOKEN_ANSWERS = {"idk", "i dont know", "i don't know", "dont know", "don't know", "dunno", "no idea", "?", "??", "???", ".", "..", "...",
                 "-", "--", "…", "pass", "skip", "n/a", "na", "none", "nothing", "no clue", "not sure", "unsure", "help", "x", "xx", "xxx"}
REHEARSAL_LABEL = "Practice — doesn't change your schedule."


def counted_clause():
    """SQL filter for attempts that are evidence (for analytics/selection)."""
    return Attempt.counts_for_mastery.is_(True)


def is_token_answer(code: str, response: str | None, working: str | None = None, marks: int = 1) -> bool:
    """A non-attempt such as 'idk', '.', '?' (adaptive-23). For Maths an answer like 'x' can be legitimate,
    so only explicit non-answers count there."""
    t = re.sub(r"\s+", " ", (response or "").strip().lower()).strip(" !")
    if not t:
        return False
    if code == "MATHS":
        return t in TOKEN_ANSWERS - {"x", "xx", "none", "nothing"} and not (working or "").strip()
    return t in TOKEN_ANSWERS


def short_answer_warning(code: str, response: str | None, marks: int) -> str | None:
    """Client and server share this rule: a written answer under ~8 words for a 2+ mark question looks like a skip."""
    n = len((response or "").split())
    if code != "MATHS" and marks >= 2 and n < 8:
        return f"This answer has {n} word{'s' if n != 1 else ''}. This looks like a skip — record it as skipped and show the answer, or go back and write more?"
    return None


def _study_date(a: Attempt) -> date:
    return a.submitted_at.date()


def revealing(a: Attempt) -> bool:
    """Did this attempt show the student the answer (solution, correct option, model or guideline)?"""
    if a.skipped or a.model_viewed_at is not None:
        return True
    p = (a.feedback.payload if a.feedback else {}) or {}
    if p.get("kind") in ("mcq", "skipped", "self_mark"):
        return True
    if p.get("kind") == "maths" and (p.get("correct") or p.get("solution_shown", True)):
        return True
    return False


def classify(db: Session, q: Question, sq: SessionQuestion | None, today: date) -> dict:
    """Decide whether the next attempt on ``q`` is evidence, and why."""
    chain = list(db.execute(select(Attempt).where(Attempt.question_id == q.id).order_by(Attempt.submitted_at, Attempt.id)).scalars())
    context = [a for a in chain if (a.session_question_id == sq.id if sq else a.session_question_id is None)]
    if sq is None:  # a practice sitting is one study day
        context = [a for a in context if _study_date(a) == today]
    today_chain = [a for a in chain if _study_date(a) == today]
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == q.id)).scalar_one_or_none()
    due = exp is None or exp.next_revision_date is None or exp.next_revision_date <= today
    if context:
        role, counts = "retry", False
        after = any(revealing(a) for a in context)
    elif today_chain:
        role, counts = "rehearsal", False
        after = any(revealing(a) for a in today_chain)
    elif sq is not None:
        role, counts, after = ("first" if not chain and exp is None else ("due_repeat" if due else "early_repeat")), True, False
    elif due:
        role, counts, after = ("first" if not chain and exp is None else "due_repeat"), True, False
    else:
        role, counts, after = "rehearsal", False, True
    label = {
        "first": "First attempt — counts towards your schedule.",
        "due_repeat": "Scheduled repeat — counts towards your schedule.",
        "early_repeat": "Counts towards your schedule.",
        "retry": "Retry — your first attempt is what counts; this shows your improvement.",
        "rehearsal": REHEARSAL_LABEL,
    }[role]
    if not counts and after:
        label += " (You had already seen the answer.)"
    return {"role": role, "counts": counts, "after_reveal": after, "context": context, "chain": chain, "exposure": exp, "label": label}


def _improvement(code: str, prev: Attempt, cur_payload: dict, response: str) -> dict:
    """What changed between attempts (adaptive-15, english-21): per criterion and per observable feature."""
    pp = (prev.feedback.payload if prev.feedback else {}) or {}
    out: dict = {"after_model": prev.model_viewed_at is not None}
    if cur_payload.get("kind") == "written" and pp.get("kind") == "written":
        before = {c.get("name"): c.get("judgement", "") for c in (pp.get("result") or {}).get("criteria", [])}
        after = {c.get("name"): c.get("judgement", "") for c in (cur_payload.get("result") or {}).get("criteria", [])}
        rows = []
        for name in list(before) + [n for n in after if n not in before]:
            b, a = before.get(name, "—"), after.get(name, "—")
            good = lambda j: j in ("met", "present") or j.startswith("fully")  # noqa: E731
            status = "improved" if good(a) and not good(b) else ("still missing" if not good(a) else ("kept" if good(b) else "changed"))
            rows.append({"criterion": name, "before": b, "after": a, "status": status})
        out["criteria"] = rows
        prev_weak = set((pp.get("result") or {}).get("weaknesses") or [])
        cur_weak = set((cur_payload.get("result") or {}).get("weaknesses") or [])
        out["addressed"] = sorted(prev_weak - cur_weak)
        out["still_missing"] = sorted(prev_weak & cur_weak)
        fp, fc = rubric.features(prev.response_text or "", code), rubric.features(response or "", code)
        keys = [("quotes", "Quotations"), ("analysis", "Analytical verbs"), ("techniques", "Named techniques")] if code == "ENGLISH" else \
               [("legal_terms", "Legal terms"), ("judgement", "Judgement language")]
        feats = [{"feature": label, "before": fp[k], "after": fc[k]} for k, label in keys]
        if code == "LEGAL":
            feats += [{"feature": "Legislation named", "before": len(fp["acts"]), "after": len(fc["acts"])},
                      {"feature": "Cases named", "before": len(fp["cases"]), "after": len(fc["cases"])}]
        feats.append({"feature": "Words", "before": fp["words"], "after": fc["words"]})
        out["features"] = feats
        prev_sents = {s.strip() for s in re.split(r"(?<=[.!?])\s+", prev.response_text or "") if s.strip()}
        out["added_sentences"] = [s.strip() for s in re.split(r"(?<=[.!?])\s+", response or "") if s.strip() and s.strip() not in prev_sents][:8]
    elif cur_payload.get("kind") == "maths":
        out["now_correct"] = bool(cur_payload.get("correct")) and not bool(pp.get("correct"))
    return out


def submit(db: Session, q: Question, response: str, *, sq: SessionQuestion | None = None, working: str | None = None,
           confidence: str | None = None, time_seconds: int = 0, skipped: bool = False, today: date | None = None,
           skip_reason: str | None = None) -> Attempt:
    from app.services.clock import today as clock_today

    settings = st.all_settings(db)
    today = today or clock_today(settings.get("timezone", "Australia/Sydney"))
    code = subject_code(db, q)
    if not skipped and is_token_answer(code, response, working, q.marks):
        skipped, skip_reason = True, skip_reason or f"“{(response or '').strip()[:40]}” is not an attempt, so it was recorded as skipped."
    cls = classify(db, q, sq, today)
    prev_attempts = cls["context"]
    attempt_no = len(prev_attempts) + 1
    if skipped:
        mark, payload, cats, method = 0.0, {"kind": "skipped", "mark": 0, "max": q.marks,
                                            "label": "Skipped — answer shown. Recorded as skipped, not correct."}, [], "skipped"
        if skip_reason:
            payload["skip_reason"] = skip_reason
    elif q.answer is not None:
        mark, payload, cats, method = mark_deterministic(db, q, response, working, settings)
    elif code == "MATHS" and not get_provider(settings).generative:
        mark, payload, cats, method = 0.0, {
            "kind": "self_mark", "mark": 0, "max": q.marks, "method": "self", "pending_mark": True,
            "label": "This imported question has no machine-checkable answer and no AI provider is configured. "
                     "Compare your working with the marking guideline below and record the mark you earned.",
            "guideline": q.marking_guideline, "guideline_official": q.guideline_official,
        }, [], "self"
    else:
        previous = prev_attempts[-1].response_text if prev_attempts else None
        mark, payload, cats, method = mark_written(db, q, response, settings, previous)
    if payload.get("kind") == "maths" and not payload.get("correct"):
        payload.setdefault("solution_shown", attempt_no >= 2)  # hint first; full solution on request or after the retry
    if payload.get("kind") == "mcq":
        payload.setdefault("chosen", (response or "").strip()[:1].upper())
    attempt = Attempt(question_id=q.id, session_question_id=sq.id if sq else None, attempt_number=attempt_no, response_text=response or "",
                      skipped=skipped, mark_awarded=float(mark), mark_possible=float(q.marks), confidence=confidence, time_seconds=time_seconds,
                      marking_method=method, official_guideline_used=bool(q.guideline_official and method == "ai"),
                      submitted_at=datetime.combine(today, datetime.now().time()),  # local study day
                      counts_for_mastery=cls["counts"], after_reveal=cls["after_reveal"], evidence_role=cls["role"])
    db.add(attempt)
    db.flush()
    if working:
        payload["working"] = working
    # "evidence_role", not "evidence": Legal feedback stores its evidence-bank items under payload["evidence"]
    payload["evidence_role"] = {"role": cls["role"], "counts": cls["counts"], "after_reveal": cls["after_reveal"], "label": cls["label"]}
    if prev_attempts:
        p = prev_attempts[-1]
        payload["previous"] = {"attempt_number": p.attempt_number, "attempt_id": p.id, "mark": p.mark_awarded, "max": p.mark_possible,
                               "change": round(attempt.mark_awarded - p.mark_awarded, 1), "after_model": p.model_viewed_at is not None}
        if not skipped:
            payload["improvement"] = _improvement(code, p, payload, response)

    items = error_journal.items_for(code, q, payload, cats, method)
    pending = payload.get("pending_mark") or payload.get("kind") == "self_mark" or method == "self"
    estimated = method == "offline_estimate"
    fb = AttemptFeedback(attempt_id=attempt.id, payload=dict(payload), error_categories=[] if estimated else [i["category"] for i in items])
    db.add(fb)
    db.flush()
    if cls["role"] == "retry":
        error_journal.mark_fixed_on_retry(db, [a.id for a in prev_attempts], {i["category"] for i in items})

    if cls["counts"]:
        if pending:
            payload["schedule"] = mastery.touch_pending(db, attempt, q, today)
        else:
            if estimated:
                payload["estimated_items"] = items  # journalled only once the student confirms the mark
            elif items:
                error_journal.add_entries(db, attempt, q, code, items, today, _source(method, payload))
            payload["schedule"] = _record(db, attempt, q, today, settings, payload, items, method)
    else:
        mastery.log_rehearsal(db, attempt, q, today)
        payload["schedule"] = {"rehearsal": True, "headline": cls["label"]}
    fb.payload = dict(payload)
    flag_modified(fb, "payload")  # JSON column: always persist the final payload
    if sq is not None:
        sq.status = "skipped" if skipped else "submitted"
        sq.time_spent_seconds = max(sq.time_spent_seconds, time_seconds)
    db.flush()
    return attempt


def _source(method: str, payload: dict) -> str:
    if payload.get("kind") == "mcq":
        return "mcq"
    return {"deterministic": "deterministic", "ai": "ai", "self": "self"}.get(method, method)


def _record(db: Session, attempt: Attempt, q: Question, today: date, settings: dict, payload: dict, items: list[dict], method: str) -> dict:
    """Counted evidence -> mastery.record, then journal follow-ups (auto-resolve, repeated-error patterns)."""
    first = items[0] if items else {}
    category = payload.get("error_category") or first.get("category")
    topic_tag = payload.get("topic_tag") or first.get("topic_tag")
    slip_evidence = bool(payload.get("slip_pattern") or payload.get("method_correct")
                         or (topic_tag or "") in ("sign error", "calculator error") or (category or "") == "sign"
                         or (payload.get("kind") == "maths" and not payload.get("correct") and float(payload.get("mark") or 0) > 0))
    sched = mastery.record(db, attempt, q, today, settings.get("revision_intensity", "normal"), category, topic_tag=topic_tag,
                           slip_evidence=slip_evidence, method=method, hsc_date=settings.get("hsc_start_date"))
    if method != "offline_estimate":
        if attempt.fraction >= 0.85:
            error_journal.auto_resolve(db, q.plan_item_id, today)
        _maybe_pattern(db, attempt, q, today, items, settings)
    return sched


def _maybe_pattern(db: Session, attempt: Attempt, q: Question, today: date, items: list[dict], settings: dict) -> None:
    """A tag (or category) seen 3+ times in 30 days becomes a targeted revision item (adaptive-12)."""
    from datetime import timedelta

    code = subject_code(db, q)
    for it in items:
        key = it.get("topic_tag") or it["category"]
        if key.startswith("other") or not q.plan_item_id:
            continue
        if error_journal.recent_count(db, code, key, today) >= 3:
            mastery.queue_item(db, plan_item_id=q.plan_item_id, kind="pattern", tag=key, due=today + timedelta(days=1), priority=0.9,
                               reason=f"Targets a repeated error: {key}.", source_attempt_id=attempt.id)
            break


# ------------------------------------------------------------- self-marking ---
def apply_self_mark(db: Session, attempt: Attempt, mark: float, *, categories: list | None = None, criteria: list | None = None,
                    note: str | None = None) -> None:
    """Record (or change) the student's own mark. The schedule is updated once, when the mark is final;
    changing it later replaces that evidence instead of adding to it (adaptive-16). Also used to confirm an
    offline estimate (guided self-marking), which then replaces the low-reliability estimate.

    ``categories``: optional journal items (strings or {category, topic_tag, description}) from guided self-marking.
    ``criteria``: optional per-criterion self-assessment, stored with the feedback."""
    from app.services.clock import today as clock_today

    settings = st.all_settings(db)
    today = clock_today(settings.get("timezone", "Australia/Sydney"))
    fb = attempt.feedback
    payload = dict(fb.payload)
    was_estimate = attempt.marking_method == "offline_estimate"
    if was_estimate:
        payload.setdefault("estimate_mark", attempt.mark_awarded)
    attempt.mark_awarded = max(0.0, min(float(mark), attempt.mark_possible))
    payload["mark"] = attempt.mark_awarded
    payload["self_marked"] = True
    payload["pending_mark"] = False
    if criteria is not None:
        payload["self_criteria"] = criteria
    if note:
        payload["self_note"] = note
    if attempt.marking_method in ("offline_estimate", "self"):
        attempt.marking_method = "self"
    q = attempt.question
    code = subject_code(db, q)
    if attempt.counts_for_mastery:
        if categories is not None:
            items = [i if isinstance(i, dict) else {"category": i} for i in categories]
            items = [error_journal._item(code, i.get("category"), i.get("description"), i.get("topic_tag")) for i in items if i.get("category")]
        elif was_estimate or payload.get("estimated_items"):
            items = (payload.get("estimated_items") or []) if attempt.fraction < 0.85 else []
        else:
            items = []
        old = payload.get("schedule") or {}
        reverted = True
        if old.get("undo"):
            reverted = mastery.revert(db, old["undo"])
        if reverted:
            if attempt.fraction >= 0.85 and categories is None:
                items = []
            error_journal.replace_entries(db, attempt, q, code, items, today, "self")
            payload["schedule"] = _record(db, attempt, q, today, settings, payload, items, "self")
            fb.error_categories = [i["category"] for i in items]
        else:
            sched = dict(old)
            sched["headline"] = ("Your mark was updated. Later answers on this skill were already scheduled from the earlier mark, "
                                 "so the schedule itself is unchanged.")
            payload["schedule"] = sched
    fb.payload = payload
    flag_modified(fb, "payload")
    db.flush()


def mark_model_viewed(db: Session, attempt: Attempt) -> bool:
    """Record that the model response (or the full worked solution) was opened for this attempt (english-21)."""
    if attempt.model_viewed_at is None:
        attempt.model_viewed_at = datetime.now()
        fb = attempt.feedback
        if fb is not None:
            p = dict(fb.payload)
            p["model_viewed"] = True
            if p.get("kind") == "maths":
                p["solution_shown"] = True
            fb.payload = p
            flag_modified(fb, "payload")
        db.flush()
        return True
    return False


def chain_for(db: Session, q: Question) -> list[Attempt]:
    return list(db.execute(select(Attempt).where(Attempt.question_id == q.id).order_by(Attempt.submitted_at, Attempt.id)).scalars())


def journal_for_attempt(db: Session, attempt: Attempt) -> list[ErrorJournal]:
    return list(db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == attempt.id)).scalars())
