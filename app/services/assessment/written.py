"""Written-response marking shared by English and Legal: AI marking (or the labelled
offline fallback), feedback payload, error categories and the generic why-lost text."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.ai.offline import OFFLINE_LABEL, OfflineProvider
from app.ai.schemas import MarkingResult
from app.marking import rubric
from app.models import Attempt, Question, Stimulus, Subject
from app.services.assessment import english, legal
from app.services.assessment.common import (
    ENGLISH_ERRORS,
    LEGAL_ERRORS,
    MARKS_EXPECTATION,
    NO_OFFICIAL,
    VERBS,
    plan_and_outcome,
    subject_code,
)

log = logging.getLogger(__name__)


def written_ctx(db: Session, q: Question, response: str, settings: dict, maths: bool = False, previous: str | None = None) -> dict:
    code = subject_code(db, q)
    item, outcome = plan_and_outcome(db, q)
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
        "evidence": legal.evidence_for(db, q) if code == "LEGAL" else [], "feedback_depth": settings.get("feedback_depth", "full"),
        "paired": paired, "previous_attempt": previous,
        "english": english.prompt_extra(q) if code == "ENGLISH" else None,  # v2-english-logic: ladder, checklist, reference model
    }


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
    ctx = written_ctx(db, q, response, settings, previous=previous)
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
        legal.post_process(db, q, ctx, result, payload, method)
    elif code == "ENGLISH":
        english.post_process(db, q, ctx, result, payload, method)
    return result.mark_awarded, payload, _map_error_categories(code, result, offline_gaps), method


# ---------------------------------------------------------------- Submission ---


def why_lost_written(q: Question, p: dict, attempt: Attempt) -> str:
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

