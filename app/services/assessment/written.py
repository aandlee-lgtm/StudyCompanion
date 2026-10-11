"""Written-response marking shared by English and Legal: AI marking (or the labelled
offline fallback), feedback payload, error categories and the generic why-lost text."""
from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.ai.offline import OFFLINE_LABEL, OfflineProvider
from app.ai.schemas import MarkingResult
from app.marking import rubric
from app.models import Attempt, Question, Stimulus, Subject
from app.services import error_journal
from app.services.assessment import english, legal
from app.services.assessment.common import (
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
    """Category names only (kept for callers that expect strings); see ``error_journal.written_items``."""
    method = "offline_estimate" if offline_gaps is not None else "ai"
    return [i["category"] for i in error_journal.written_items(code, result.model_dump(), method)]


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
    # each category with its OWN description (legal-20); subject packages may replace payload["journal_items"]
    payload["journal_items"] = error_journal.written_items(code, payload["result"], method)
    if code == "LEGAL":
        legal.post_process(db, q, ctx, result, payload, method)
    elif code == "ENGLISH":
        english.post_process(db, q, ctx, result, payload, method)
    return result.mark_awarded, payload, [i["category"] for i in payload.get("journal_items") or []], method


# ---------------------------------------------------------------- Submission ---


# -------------------------------------------------------- 'why did I lose the mark?' ---
_LADDER_LINE = re.compile(r"^\s*(?:[-•*]\s*)?(\d+(?:\.\d+)?)\s*(?:marks?|–|-|:|\))\s*[:–-]?\s*(.+)$", re.I)

# The one move that earns the next mark, per journal category (used with the student's own sentence).
NEXT_MOVE = {
    "insufficient textual evidence": "embed a short, precise quotation from the text in this sentence and build your point on it",
    "technique identification without analysis": "after naming the technique, say what it reveals or how it shapes the reader's understanding of the idea in the question",
    "descriptive response": "replace retelling with analysis: say HOW the writer creates the effect and WHY it matters to the question",
    "weak thesis": "open with one arguable sentence that answers the question directly, and return to it in each paragraph",
    "poor comparison": "put both texts in the same sentence with a comparative connective (whereas, similarly, unlike) and say what the difference shows",
    "limited evaluation": "finish the paragraph with a judgement of how effectively (or to what extent) this answers the question",
    "imprecise expression": "replace the general word with the precise term and cut filler so each sentence makes one claim",
    "missing authority": "support the point with a named Act or case from your evidence bank and say what it establishes",
    "weak judgement": "state your judgement (how effective, to what extent) and keep it consistent to the conclusion",
    "description instead of evaluation": "after describing the law, measure it against a criterion (justice, access, protection of rights, resource efficiency) and judge it",
    "insufficient contemporary evidence": "add a recent, dated example (a reform, case, inquiry or report) from your evidence bank",
    "poor use of cases": "after naming the case, explain its legal significance for the point you are making",
    "failure to address directive verb": "do what the directive verb asks — for 'evaluate' or 'assess', that means a judgement, not a description",
    "imprecise legal terminology": "use the precise legal term (e.g. 'standard of proof', 'mens rea', 'judicial discretion') rather than an everyday word",
    "no law reform": "explain one law reform: what changed, why it changed, and whether it worked",
    "stimulus not used": "refer explicitly to a detail of the stimulus and apply the law to it",
    "unverified/invented authority": "only cite authorities in your verified evidence bank; remove or verify the others",
}


def criteria_ladder(q: Question) -> list[dict]:
    """The question's mark ladder, highest first: ``solution.criteria`` ([{mark, descriptor}]) or parsed guideline lines."""
    sol = q.solution or {}
    rows = []
    for c in sol.get("criteria") or []:
        if isinstance(c, dict) and c.get("descriptor") is not None:
            try:
                rows.append({"mark": float(c.get("mark")), "descriptor": str(c["descriptor"]).strip()})
            except (TypeError, ValueError):
                continue
    if not rows and q.marking_guideline:
        for line in q.marking_guideline.splitlines():
            m = _LADDER_LINE.match(line)
            if m and float(m.group(1)) <= max(q.marks, 1):
                rows.append({"mark": float(m.group(1)), "descriptor": m.group(2).strip()})
    for r in rows:
        r["mark"] = int(r["mark"]) if float(r["mark"]).is_integer() else r["mark"]
    return sorted(rows, key=lambda r: -float(r["mark"]))


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(x.strip().split()) >= 3]


def _evidence_sentence(code: str, category: str, response: str) -> str | None:
    """The student's own sentence that best shows a category (quoted back in the explanation)."""
    sents = _sentences(response)
    if not sents:
        return None
    def feats(s):  # noqa: E306
        return rubric.features(s, code)
    if category in ("technique identification without analysis",):
        pick = [s for s in sents if feats(s)["techniques"] and not feats(s)["analysis"]]
    elif category in ("insufficient textual evidence",):
        pick = [s for s in sents if not feats(s)["quotes"]]
    elif category in ("missing authority", "poor use of cases"):
        pick = [s for s in sents if not feats(s)["acts"] and not feats(s)["cases"]] if code == "LEGAL" else []
    elif category in ("weak judgement", "description instead of evaluation", "limited evaluation", "failure to address directive verb"):
        pick = [s for s in sents if not feats(s)["judgement"]]
    else:
        pick = []
    pick = pick or sents
    s = pick[0]
    return s if len(s) <= 220 else s[:217].rsplit(" ", 1)[0] + "…"


def _stimulus_suggestion(q: Question, response: str) -> str | None:
    """A short line from the stimulus the student did not use (grounds the 'next move')."""
    if not q.stimulus or not q.stimulus.body:
        return None
    low = (response or "").lower()
    for s in _sentences(q.stimulus.body):
        words = s.split()
        if 5 <= len(words) <= 22 and s.lower()[:40] not in low:
            return s
    return None


def why_lost_written(q: Question, p: dict, attempt: Attempt) -> str:
    """Generic mark-gap explainer for written answers: the band reached, the next band's demand, the student's
    own sentence and the one move per missing element (adaptive-13). Subject packages may supply richer text."""
    code = p.get("subject") or ("LEGAL" if (p.get("evidence") is not None) else "ENGLISH")
    verb = (q.directive_verb or "").lower()
    mark = float(attempt.mark_awarded or 0)
    parts: list[str] = []
    s = f"This was a {q.marks}-mark '{q.directive_verb or 'response'}' question"
    if verb in VERBS:
        s += f" — '{q.directive_verb}' asks you to {VERBS[verb]}"
    expect = MARKS_EXPECTATION.get(min(q.marks, 6), MARKS_EXPECTATION[6]) if q.marks < 10 else \
        "a sustained, well-structured response with a clear thesis/judgement throughout, integrating relevant evidence in every paragraph"
    parts.append(s + f". At this mark value a marker expects {expect}.")
    ladder = criteria_ladder(q)
    if ladder:
        reached = next((r for r in ladder if float(r["mark"]) <= mark + 1e-9), None)
        nxt = next((r for r in reversed(ladder) if float(r["mark"]) > mark + 1e-9), None)
        if reached:
            parts.append(f"Your answer sits in the {reached['mark']}-mark band: \u201c{reached['descriptor']}\u201d")
        if nxt:
            parts.append(f"The next band ({nxt['mark']} marks) asks for: \u201c{nxt['descriptor']}\u201d")
    items = p.get("journal_items") or []
    seen = 0
    for it in items[:3]:
        cat = it.get("category", "")
        move = NEXT_MOVE.get(cat)
        if not move:
            continue
        own = _evidence_sentence(code, cat, attempt.response_text or "")
        line = f"You wrote \u201c{own}\u201d — to earn the next mark, {move}." if own and seen == 0 else f"Also: {move} ({cat})."
        parts.append(line)
        seen += 1
    if seen == 0:
        r = p.get("result", {})
        gap = (r.get("next_level") or "").strip()
        if gap:
            parts.append(f"The step up: {gap}")
    if code == "ENGLISH":
        sug = _stimulus_suggestion(q, attempt.response_text or "")
        if sug and any(i.get("category") in ("insufficient textual evidence", "descriptive response", "technique identification without analysis") for i in items):
            parts.append(f"For example, a line from the text you did not use: \u201c{sug}\u201d — what does its language or form suggest about the idea in the question?")
    checklist = (q.solution or {}).get("checklist") or []
    if checklist:
        low = (attempt.response_text or "").lower()
        missing = [c for c in checklist if not any(w in low for w in re.findall(r"[a-z]{6,}", c.lower())[:3])]
        if missing:
            parts.append("Not yet in your answer: " + "; ".join(missing[:2]) + ".")
    if p.get("method") == "offline_estimate":
        parts.append("(Based on the offline estimate, which is approximate; configure an AI provider for a fuller explanation.)")
    return "\n\n".join(parts)
