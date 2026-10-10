"""Assessment: deterministic Maths/MCQ marking, AI (or clearly labelled offline) marking for
written responses, structured feedback, 'Why did I lose the mark?', retries, error journal
and mastery updates."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

import sympy as sp
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.ai.offline import OFFLINE_LABEL, OfflineProvider
from app.ai.schemas import MarkingResult
from app.marking import maths as maths_marker
from app.marking import rubric
from app.models import Attempt, AttemptFeedback, ErrorJournal, LearningPlanItem, LegalEvidence, LegalEvidenceTopic, Question, SessionQuestion, Stimulus, Subject, SyllabusOutcome
from app.services import mastery
from app.services import settings as st

log = logging.getLogger(__name__)
NO_OFFICIAL = "AI-estimated mark based on NESA syllabus/performance criteria."
DISCLAIMER = "Legal Studies feedback is for education only and is not legal advice."

ENGLISH_ERRORS = {"insufficient textual evidence", "technique identification without analysis", "weak thesis", "descriptive response",
                  "poor comparison", "limited evaluation", "imprecise expression"}
LEGAL_ERRORS = {"missing authority", "outdated legislation", "weak judgement", "description instead of evaluation",
                "insufficient contemporary evidence", "poor use of cases", "failure to address directive verb"}
MARKS_EXPECTATION = {
    1: "one accurate point",
    2: "one clear, accurate point supported by a piece of evidence and briefly explained",
    3: "a clear point with apt evidence AND an explanation of its effect or significance (or two briefer points)",
    4: "two developed points, each linking evidence to a technique or concept and explaining how it shapes meaning or answers the question",
    5: "a sustained, coherent answer: 2–3 developed points, integrated evidence and an explicit judgement or comparison",
    6: "a structured mini-essay: a clear thesis, 3 developed points with integrated evidence, and sophisticated analysis of form and meaning",
}
VERBS = {
    "identify": "recognise and name", "explain": "relate cause and effect; make relationships evident", "analyse": "draw out how parts relate and what they imply",
    "evaluate": "make a judgement based on criteria", "assess": "make a judgement of value or effectiveness", "compare": "show similarities AND differences",
    "discuss": "provide points for and/or against", "compose": "create a purposeful text",
}


def subject_code(db: Session, q: Question) -> str:
    return db.get(Subject, q.subject_id).code


def answer_display(q: Question) -> str:
    a = q.answer or {}
    try:
        if a.get("type") == "mcq":
            opt = next((o for o in (q.options or []) if o.strip().upper().startswith(a["value"].upper())), a["value"])
            return opt
        if a.get("type") == "set":
            return ", ".join(sp.latex(sp.sympify(v, locals=maths_marker.LOCALS)) for v in a["values"])
        v = sp.sympify(a.get("value", ""), locals=maths_marker.LOCALS)
        s = sp.latex(v)
        if a.get("type") == "antiderivative":
            s += " + C"
        if a.get("units"):
            s += f"\\ \\text{{{a['units']}}}"
        return s
    except Exception:
        return str(a.get("value", ""))


def _plan_and_outcome(db: Session, q: Question) -> tuple[LearningPlanItem | None, str]:
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    outcome = db.get(SyllabusOutcome, q.syllabus_outcome_id) if q.syllabus_outcome_id else None
    topic = item.topic.name if item and item.topic else ""
    out = f"{topic} — {outcome.code}" if outcome else topic
    return item, out


def _divergence_step(category: str | None, steps: list[str]) -> int:
    if not steps:
        return 0
    if category in ("formula selection", "conceptual", "interpretation"):
        return 1
    return len(steps)


# ------------------------------------------------------------------ Maths / MCQ ---
def mark_deterministic(db: Session, q: Question, response: str, working: str | None, settings: dict) -> tuple[float, dict, list[str], str]:
    sol = q.solution or {}
    res = maths_marker.mark_answer(response, q.answer or {}, q.marks, sol.get("common_errors"))
    item, outcome = _plan_and_outcome(db, q)
    code = subject_code(db, q)
    if (q.answer or {}).get("type") == "mcq":
        payload = {
            "kind": "mcq", "mark": res.mark, "max": q.marks, "correct": res.correct, "student_answer": res.student_display or response,
            "correct_answer": answer_display(q), "explanation": sol.get("explanation") or " ".join(sol.get("steps", [])),
            "concept": sol.get("concept"), "outcome": outcome, "method": "deterministic",
            "label": "Marked automatically (multiple choice).",
        }
        cats = [] if res.correct else (["conceptual"] if code == "MATHS" else [])
        return res.mark, payload, cats, "deterministic"
    steps = sol.get("steps", [])
    step_no = _divergence_step(res.category, steps) if not res.correct else 0
    divergence = None
    if not res.correct:
        divergence = (res.diagnosis or "") + (f" Compare your working with step {step_no} of the worked solution." if step_no else "")
    method_note, mark = None, res.mark
    if not res.correct and working and working.strip() and q.marks >= 2:
        provider = get_provider(settings)
        if provider.generative:
            try:
                r = provider.mark_response(_written_ctx(db, q, f"FINAL ANSWER: {response}\nWORKING:\n{working}", settings, maths=True))
                mark = min(float(q.marks) - 1, max(mark, r.mark_awarded))  # method marks only; the answer is wrong
                method_note = f"Method marks assessed by AI from your working ({NO_OFFICIAL}): {r.marking_rationale or '; '.join(r.weaknesses[:2])}"
            except (AIError, AIUnavailable) as exc:
                method_note = f"Your working could not be assessed by AI ({exc}). Check it against the worked solution."
        else:
            method_note = "Your working was saved. Without an AI provider only the final answer is marked automatically; compare your working with the worked solution to see where method marks would be earned."
    rec = None
    if item:
        rec = f"Revise {item.code} {item.title}" + (" — focus on: " + res.category if res.category else "") + "."
    payload = {
        "kind": "maths", "mark": mark, "max": q.marks, "correct": res.correct, "student_answer": response, "student_parsed": res.student_display,
        "correct_answer": answer_display(q), "worked_solution": steps, "divergence": divergence, "divergence_step": step_no,
        "concept": sol.get("concept"), "quicker": sol.get("quicker"), "technique": sol.get("technique"), "outcome": outcome,
        "revision": rec, "error_category": res.category, "notes": res.notes + ([method_note] if method_note else []), "method": "deterministic",
        "label": "Final answer checked automatically with SymPy (equivalent forms accepted).",
    }
    return mark, payload, ([res.category] if res.category and not res.correct else []), "deterministic"


# ------------------------------------------------------------- Written (AI) ---
def evidence_for(db: Session, q: Question) -> list[dict]:
    if not q.topic_id:
        return []
    rows = db.execute(select(LegalEvidence).join(LegalEvidenceTopic).where(LegalEvidenceTopic.topic_id == q.topic_id)).scalars().all()
    return [{"title": e.title, "type": e.item_type, "date": e.date, "jurisdiction": e.jurisdiction, "summary": e.summary,
             "significance": e.legal_significance, "source_url": e.source_url,
             "verified": e.last_verified_date.isoformat() if e.last_verified_date else "UNVERIFIED"} for e in rows]


def _written_ctx(db: Session, q: Question, response: str, settings: dict, maths: bool = False, previous: str | None = None) -> dict:
    code = subject_code(db, q)
    item, outcome = _plan_and_outcome(db, q)
    subj = db.get(Subject, q.subject_id)
    stim = q.stimulus
    stim_text, paired = None, False
    if stim:
        stim_text = stim.body or ""
        partner = db.get(Stimulus, stim.paired_with_id) if stim.paired_with_id else db.execute(
            select(Stimulus).where(Stimulus.paired_with_id == stim.id)).scalars().first()
        if partner is not None:
            paired = True
            first, second = (stim, partner) if stim.paired_with_id else (partner, stim)
            stim_text = f"{first.title}\n{first.body}\n\n{second.title}\n{second.body}"
    return {
        "subject": code, "subject_name": subj.name, "syllabus": "NSW Stage 6, syllabus applicable to the 2027 HSC",
        "topic": item.title if item else "", "outcome": outcome, "marks": q.marks, "directive_verb": q.directive_verb,
        "source_context": f"{q.source.title} ({q.historical_or_generated})", "question": q.question_text, "stimulus": stim_text,
        "stimulus_attribution": stim.attribution if stim else None, "official_guideline": q.marking_guideline if q.guideline_official else None,
        "criteria": None if q.guideline_official else q.marking_guideline, "response": response, "model_answer": q.model_answer,
        "evidence": evidence_for(db, q) if code == "LEGAL" else [], "feedback_depth": settings.get("feedback_depth", "full"),
        "paired": paired, "previous_attempt": previous,
    }


CITATION = re.compile(r"\b([A-Z][A-Za-z()'’,\- ]{2,80}? Act \d{4}(?: \([A-Za-z]+\))?|[A-Z][A-Za-z]+ v (?:The )?[A-Z][A-Za-z]+(?: \(No \d\))?)")


def unverified_citations(text: str, evidence: list[dict]) -> list[str]:
    known = " ".join(e["title"] for e in evidence).lower()
    out = []
    for m in CITATION.findall(text or ""):
        name = m.strip()
        core = re.sub(r"\s*\(.*?\)\s*$", "", name).lower()
        if core and core not in known and name not in out:
            out.append(name)
    return out


def _offline_comparison(model: str | None, response: str, code: str) -> str:
    if not model:
        return ""
    fm, fs = rubric.features(model, code), rubric.features(response, code)
    rows = []
    if code == "ENGLISH":
        rows += [f"Quotations: model {fm['quotes']}, yours {fs['quotes']}.", f"Analytical verbs (how meaning is shaped): model {fm['analysis']}, yours {fs['analysis']}.",
                 f"Named techniques/features of form: model {fm['techniques']}, yours {fs['techniques']}."]
    else:
        rows += [f"Named legislation: model {len(fm['acts'])}, yours {len(fs['acts'])}.", f"Cases: model {len(fm['cases'])}, yours {len(fs['cases'])}.",
                 f"Judgement language: model {fm['judgement']}, yours {fs['judgement']}."]
    rows.append(f"Length: model {fm['words']} words, yours {fs['words']} words (length alone earns nothing; development does).")
    return " ".join(rows)


def _map_error_categories(code: str, result: MarkingResult, offline_gaps: list[str] | None) -> list[str]:
    cats: list[str] = []
    allowed = ENGLISH_ERRORS if code == "ENGLISH" else LEGAL_ERRORS
    for e in result.errors:
        c = e.category.strip().lower()
        match = next((a for a in allowed if a in c or c in a), None)
        cats.append(match or c)
    gap_map = {
        "Textual evidence": "insufficient textual evidence", "Analysis of effect": "descriptive response", "Judgement":
        "limited evaluation" if code == "ENGLISH" else "description instead of evaluation", "Comparison": "poor comparison",
        "Legal authority": "missing authority", "Contemporary evidence": "insufficient contemporary evidence",
        "Legal terminology": "imprecise expression" if code == "ENGLISH" else "failure to address directive verb",
    }
    for g in offline_gaps or []:
        if g in gap_map:
            cats.append(gap_map[g])
    return sorted(set(cats))


def mark_written(db: Session, q: Question, response: str, settings: dict, previous: str | None) -> tuple[float, dict, list[str], str]:
    code = subject_code(db, q)
    ctx = _written_ctx(db, q, response, settings, previous=previous)
    provider = get_provider(settings)
    method, note = "ai", None
    try:
        result = provider.mark_response(ctx)
        if not provider.generative:
            method = "offline_estimate"
    except (AIError, AIUnavailable) as exc:
        log.warning("AI marking failed, using offline estimate: %s", exc)
        note = f"AI marking was unavailable ({exc}); showing the offline estimate instead."
        result, method = OfflineProvider().mark_response(ctx), "offline_estimate"
    result.mark_possible = float(q.marks)
    result.mark_awarded = min(result.mark_awarded, float(q.marks))
    if method == "offline_estimate":
        label = OFFLINE_LABEL
    elif q.guideline_official:
        label = "Marked by AI against the official NESA marking guideline for this question (AI-applied, not an official NESA judgement)."
    else:
        label = NO_OFFICIAL
    offline_gaps = result.weaknesses if method == "offline_estimate" else None
    model = result.model_answer or q.model_answer or ""
    comparison = result.comparison or (_offline_comparison(q.model_answer, response, code) if method == "offline_estimate" else "")
    payload = {
        "kind": "written", "subject": code, "method": method, "label": label, "note": note,
        "mark": result.mark_awarded, "max": q.marks, "result": result.model_dump(),
        "model_answer": model, "model_answer_source": "AI-written for this question" if result.model_answer else ("Written for this question by HSC Companion" if q.model_answer else None),
        "comparison": comparison, "improved_answer": result.improved_answer or None,
        "guidance": (q.solution or {}).get("guidance"), "criteria_text": q.marking_guideline, "criteria_official": q.guideline_official,
    }
    if code == "LEGAL":
        ev = ctx["evidence"]
        verified = [e["verified"] for e in ev if e["verified"] != "UNVERIFIED"]
        payload["facts_checked"] = max(verified) if verified else None
        all_text = " ".join([model, result.improved_argument, " ".join(result.evidence_suggestions), result.improved_answer])
        payload["unverified_references"] = unverified_citations(all_text, ev) if method == "ai" else []
        payload["evidence"] = ev
        payload["disclaimer"] = DISCLAIMER
    return result.mark_awarded, payload, _map_error_categories(code, result, offline_gaps), method


# ---------------------------------------------------------------- Submission ---
def submit(db: Session, q: Question, response: str, *, sq: SessionQuestion | None = None, working: str | None = None,
           confidence: str | None = None, time_seconds: int = 0, skipped: bool = False, today: date | None = None) -> Attempt:
    from app.services.clock import today as clock_today

    settings = st.all_settings(db)
    today = today or clock_today(settings.get("timezone", "Australia/Sydney"))
    same_context = Attempt.session_question_id == sq.id if sq else Attempt.session_question_id.is_(None)
    prev_attempts = db.execute(select(Attempt).where(Attempt.question_id == q.id, same_context).order_by(Attempt.attempt_number)).scalars().all()
    if sq is None:  # practice outside a session: each day's practice starts with a fresh first attempt
        prev_attempts = [a for a in prev_attempts if a.submitted_at.date() == today]
    attempt_no = len(prev_attempts) + 1
    code = subject_code(db, q)
    if skipped:
        mark, payload, cats, method = 0.0, {"kind": "skipped", "mark": 0, "max": q.marks, "label": "Skipped — answer shown. Recorded as skipped, not correct."}, [], "skipped"
    elif q.answer is not None:
        mark, payload, cats, method = mark_deterministic(db, q, response, working, settings)
    elif code == "MATHS" and not get_provider(settings).generative:
        mark, payload, cats, method = 0.0, {
            "kind": "self_mark", "mark": 0, "max": q.marks, "method": "self",
            "label": "This imported question has no machine-checkable answer and no AI provider is configured. "
                     "Compare your working with the marking guideline below and record the mark you earned.",
            "guideline": q.marking_guideline, "guideline_official": q.guideline_official,
        }, [], "self"
    else:
        previous = prev_attempts[-1].response_text if prev_attempts else None
        mark, payload, cats, method = mark_written(db, q, response, settings, previous)
    attempt = Attempt(question_id=q.id, session_question_id=sq.id if sq else None, attempt_number=attempt_no, response_text=response or "",
                      skipped=skipped, mark_awarded=float(mark), mark_possible=float(q.marks), confidence=confidence, time_seconds=time_seconds,
                      marking_method=method, official_guideline_used=bool(q.guideline_official and method == "ai"),
                      submitted_at=datetime.combine(today, datetime.now().time()))  # local study day
    db.add(attempt)
    db.flush()
    if working:
        payload["working"] = working
    if prev_attempts:
        p = prev_attempts[-1]
        payload["previous"] = {"attempt_number": p.attempt_number, "mark": p.mark_awarded, "max": p.mark_possible,
                               "change": round(attempt.mark_awarded - p.mark_awarded, 1)}
    db.add(AttemptFeedback(attempt_id=attempt.id, payload=payload, error_categories=cats))
    for c in cats:
        db.add(ErrorJournal(attempt_id=attempt.id, question_id=q.id, subject_code=code, category=c, plan_item_id=q.plan_item_id,
                            description=_journal_text(payload, c)))
    if attempt_no == 1:  # retries improve the answer but do not reset the schedule
        sched = mastery.record(db, attempt, q, today, settings.get("revision_intensity", "normal"), cats[0] if cats else payload.get("error_category"))
        payload["schedule"] = sched
        fb = db.execute(select(AttemptFeedback).where(AttemptFeedback.attempt_id == attempt.id)).scalar_one()
        fb.payload = dict(payload)
    if sq is not None:
        sq.status = "skipped" if skipped else "submitted"
        sq.time_spent_seconds = max(sq.time_spent_seconds, time_seconds)
    db.flush()
    return attempt


def _journal_text(payload: dict, category: str) -> str:
    if payload.get("kind") == "maths":
        return payload.get("divergence") or category
    r = payload.get("result") or {}
    for e in r.get("errors", []):
        if e.get("category", "").lower() in category or category in e.get("category", "").lower():
            return e.get("description", category)
    return "; ".join(r.get("improvements", [])[:1]) or category


# ------------------------------------------------------------- Why lost ---
def why_lost(db: Session, attempt: Attempt) -> str:
    fb = attempt.feedback
    if fb.why_lost:
        return fb.why_lost
    q = attempt.question
    p = fb.payload
    if attempt.mark_awarded >= attempt.mark_possible:
        text = "You received full marks for this question — nothing was lost."
    elif p.get("kind") in ("maths", "mcq"):
        text = _why_lost_maths(q, p)
    elif p.get("kind") == "skipped":
        text = "The question was skipped, so no marks could be awarded. Skipping is recorded honestly so the app schedules it for revision."
    else:
        text = None
        provider = get_provider(st.all_settings(db))
        if provider.generative:
            try:
                text = provider.generate_feedback({
                    "subject_name": db.get(Subject, q.subject_id).name, "marks": q.marks, "directive_verb": q.directive_verb,
                    "question": q.question_text, "mark": attempt.mark_awarded, "response": attempt.response_text, "feedback": p.get("result", {}),
                }).explanation
            except (AIError, AIUnavailable) as exc:
                log.warning("why_lost AI failed: %s", exc)
        text = text or _why_lost_written(q, p, attempt)
    fb.why_lost = text
    db.flush()
    return text


def _why_lost_maths(q: Question, p: dict) -> str:
    cat = p.get("error_category") or "conceptual"
    lead = {
        "sign": "The method was probably right, but a sign changed somewhere.",
        "arithmetic": "Your approach looks right, but a calculation went wrong.",
        "careless error": "This looks like a slip rather than a misunderstanding.",
        "notation": "The value may be right, but it was not in the form the question asked for.",
        "formula selection": "The wrong formula (or the wrong version of it) was used.",
        "interpretation": "The question was answered, but not the question that was asked.",
        "incomplete reasoning": "The answer stopped short of what was asked.",
        "conceptual": "The underlying idea needs another look.",
    }.get(cat, "The answer did not match.")
    parts = [lead]
    if p.get("divergence"):
        parts.append(p["divergence"])
    if p.get("concept"):
        parts.append(f"Key idea: {p['concept']}")
    if q.marks >= 2:
        parts.append(f"In a {q.marks}-mark question, markers award marks for correct method as well as the answer, so writing each step (formula, substitution, simplification) protects marks even if the final line goes wrong.")
    if p.get("technique"):
        parts.append(f"Exam technique: {p['technique']}")
    return " ".join(parts)


def _why_lost_written(q: Question, p: dict, attempt: Attempt) -> str:
    verb = (q.directive_verb or "").lower()
    expect = MARKS_EXPECTATION.get(min(q.marks, 6), MARKS_EXPECTATION[6]) if q.marks < 10 else "a sustained, well-structured response with a clear thesis/judgement throughout, integrating relevant evidence in every paragraph"
    r = p.get("result", {})
    gaps = r.get("improvements") or r.get("weaknesses") or []
    s = f"This was a {q.marks}-mark '{q.directive_verb or 'response'}' question"
    if verb in VERBS:
        s += f" — '{q.directive_verb}' asks you to {VERBS[verb]}"
    s += f". At this mark value a marker expects {expect}. "
    s += f"Your response earned about {attempt.mark_awarded:g}/{q.marks}. "
    if gaps:
        s += "What held it back: " + " ".join(gaps[:3])
    if p.get("method") == "offline_estimate":
        s += " (Explanation based on the offline estimate; configure an AI provider for a fuller explanation.)"
    return s


def apply_self_mark(db: Session, attempt: Attempt, mark: float) -> None:
    from app.services.clock import today as clock_today

    attempt.mark_awarded = max(0.0, min(float(mark), attempt.mark_possible))
    fb = attempt.feedback
    payload = dict(fb.payload)
    payload["mark"] = attempt.mark_awarded
    payload["self_marked"] = True
    fb.payload = payload
    settings = st.all_settings(db)
    if attempt.attempt_number == 1:
        mastery.record(db, attempt, attempt.question, clock_today(settings.get("timezone", "Australia/Sydney")), settings.get("revision_intensity", "normal"))
    db.flush()
