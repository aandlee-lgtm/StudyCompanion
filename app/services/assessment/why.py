"""'Why did I lose the mark?' dispatcher (section 24; owner: adaptive).

A dedicated mark-gap explainer, separate from the marking feedback (adaptive-13):

* MCQ (all subjects): why the chosen distractor is tempting and why it is wrong, why the key is
  right (``solution.option_rationales``), and how to eliminate options next time.
* Skipped: the first step (or the first band of the criteria) and how the first mark is earned.
* Maths: the subject explainer (``assessment.maths.why_lost_maths``) with anything already shown in
  the feedback removed, plus a near-miss contrast of the student's value with the correct one and
  where the lost marks sit in the worked solution.
* Written (English/Legal): AI with stimulus, criteria, model answer and (Legal) the verified
  evidence bank, citation-checked (adaptive-14); otherwise the subject explainers
  (``english.why_lost`` / ``legal.why_lost``) and finally the generic ladder explainer in
  ``written.why_lost_written``.

Paragraphs are separated by blank lines; the page renders each as its own paragraph."""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.ai.schemas import WhyLost
from app.models import Attempt, Subject
from app.services import settings as st
from app.services.assessment import english, legal
from app.services.assessment.common import MARKS_EXPECTATION, VERBS, subject_code
from app.services.assessment.maths import why_lost_maths
from app.services.assessment.written import criteria_ladder, why_lost_written

log = logging.getLogger(__name__)

FEEDBACK_FIELDS = ("divergence", "concept", "technique", "quicker", "explanation", "revision", "label")


def why_lost(db: Session, attempt: Attempt) -> str:
    fb = attempt.feedback
    if fb.why_lost:
        return fb.why_lost
    q = attempt.question
    p = fb.payload or {}
    code = subject_code(db, q)
    kind = p.get("kind")
    if kind == "skipped" or attempt.skipped:
        text = explain_skipped(q, p, code)
    elif attempt.mark_awarded >= attempt.mark_possible:
        text = "You received full marks for this question — nothing was lost."
    elif kind == "mcq":
        text = explain_mcq(q, p)
    elif kind == "maths":
        text = explain_maths(q, p)
    elif kind == "self_mark":
        text = explain_self_marked(q, p, attempt)
    else:
        text = None
        if code == "ENGLISH" and get_provider(st.all_settings(db)).generative:
            text = english.ai_why_lost(db, q, p, attempt)  # v2-english-logic: ladder, passage and a verified sentence upgrade
        if text is None:
            text = _ai_written(db, q, p, attempt, code)
        if text is None:
            text = legal.why_lost(q, p, attempt) if code == "LEGAL" else english.why_lost(q, p, attempt)
        text = text or why_lost_written(q, p, attempt)
    fb.why_lost = text
    db.flush()
    return text


# ----------------------------------------------------------------------- helpers ---
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def strip_repeats(text: str, payload: dict) -> str:
    """Remove passages that the feedback already shows word for word (the why box must teach, not repeat)."""
    out = text or ""
    for k in FEEDBACK_FIELDS:
        v = payload.get(k)
        if isinstance(v, str) and len(v.strip()) >= 20:
            out = out.replace(v.strip(), "")
    out = _norm(out)
    # a label whose content was removed ("Key idea: " followed by the next label or the end)
    return _norm(re.sub(r"\b(Key idea|Exam technique):\s*\.?\s*(?=Key idea|Exam technique|In a \d|$)", "", out))


def _option_text(q, letter: str) -> str:
    for o in q.options or []:
        if o.strip().upper().startswith(letter.upper()):
            return o.strip()
    return letter


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def near_miss(student, correct) -> str | None:
    """A specific contrast between the student's value and the correct one (sign, place value, rounding)."""
    a, b = _num(student), _num(correct)
    if a is None or b is None or b == 0:
        return None
    if a == -b:
        return "Your value has the right size but the opposite sign — the method was probably right and a sign changed (subtracting a negative, or the order of a subtraction)."
    ratio = a / b
    for k in (10, 100, 1000):
        if abs(ratio - k) < 1e-9 or abs(ratio - 1 / k) < 1e-9:
            return f"Your value is out by a factor of {k} — a place-value or unit conversion slip rather than a method problem."
    if abs(a - b) <= max(0.01 * abs(b), 0.006):
        return "Your value is very close to the answer — check the rounding instruction (decimal places or significant figures) and avoid rounding before the final line."
    if abs(ratio - 2) < 1e-9 or abs(ratio - 0.5) < 1e-9:
        return "Your value is exactly double (or half) the answer — a factor of 2 was gained or lost (for example in a chain-rule factor, a doubled term, or an area of a triangle)."
    return None


# ----------------------------------------------------------------------------- MCQ ---
def explain_mcq(q, p: dict) -> str:
    sol = q.solution or {}
    rats = {str(k).upper(): v for k, v in (sol.get("option_rationales") or {}).items()}
    chosen = (p.get("chosen") or str(p.get("student_answer") or "")[:1]).upper()
    correct = str((q.answer or {}).get("value") or "").upper()[:1]
    parts = []
    if chosen and chosen in rats:
        parts.append(f"You chose {_option_text(q, chosen)}. Why it is tempting, and why it is wrong: {rats[chosen]}")
    elif chosen:
        parts.append(f"You chose {_option_text(q, chosen)}, which does not answer the question as asked.")
    if correct and correct in rats:
        parts.append(f"Why {correct} is right: {rats[correct]}")
    elif correct:
        parts.append(f"The answer is {_option_text(q, correct)}." + (f" The idea it tests: {sol['concept']}" if sol.get("concept") else ""))
    others = [f"{k} — {v}" for k, v in sorted(rats.items()) if k not in (chosen, correct)]
    if others:
        parts.append("The other options: " + " ".join(others))
    parts.append("Technique: before choosing, test each option against the key idea and cross out any that contradict it; "
                 "an option that is true in general but does not answer this question is the most common trap.")
    return "\n\n".join(parts)


# -------------------------------------------------------------------------- Skipped ---
def explain_skipped(q, p: dict, code: str) -> str:
    sol = q.solution or {}
    parts = ["No marks could be awarded because no answer was given. The skip is recorded honestly (not as correct) and this skill comes back soon with a different question."]
    if code == "MATHS" or (q.answer and (q.answer or {}).get("type") != "mcq"):
        steps = sol.get("steps") or []
        hint = sol.get("hint") or (steps[0] if steps else None)
        if hint:
            parts.append(f"How the first mark is earned: {hint}")
        if q.marks >= 2:
            parts.append(f"In a {q.marks}-mark question, markers award marks for correct method, so writing the first step — the formula you would use "
                         "and the values you would substitute — usually earns a mark even if you cannot finish.")
    elif (q.answer or {}).get("type") == "mcq":
        parts.append("For multiple choice, eliminating even one option before guessing improves your odds; a recorded guess also tells the app what to revise.")
        if sol.get("concept"):
            parts.append(f"The idea being tested: {sol['concept']}")
    else:
        ladder = criteria_ladder(q)
        if ladder:
            low = ladder[-1]
            parts.append(f"How the first mark is earned ({low['mark']} mark band): {low['descriptor']}")
        checklist = sol.get("checklist") or []
        if checklist:
            parts.append(f"A first move for this question: {checklist[0]}")
        expect = MARKS_EXPECTATION.get(min(q.marks, 6))
        if expect:
            parts.append(f"For full marks at {q.marks} marks a marker expects {expect}.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------- Maths ---
def explain_maths(q, p: dict) -> str:
    base = strip_repeats(why_lost_maths(q, p) or "", p)
    parts = [base] if base else []
    nm = near_miss(p.get("student_parsed") or p.get("student_answer"), (q.answer or {}).get("value"))
    if nm:
        parts.append(f"Your value against the answer: {nm}")
    steps = p.get("worked_solution") or []
    k = p.get("divergence_step") or 0
    mark, marks = float(p.get("mark") or 0), int(q.marks or 1)
    if marks >= 2:
        lost = marks - mark
        where = f" The first mark you lost sits at step {k} of {len(steps)}: “{steps[k - 1]}”." if steps and 1 <= k <= len(steps) else ""
        parts.append(f"Marks: {mark:g} of {marks} earned, {lost:g} lost. The final-answer mark needs the exact value in the required form; "
                     f"method marks need each step written so a marker can follow it.{where}")
    cat = p.get("error_category")
    tag = p.get("topic_tag")
    if cat or tag:
        from app.services.error_journal import DESCRIPTIONS, normalise

        c, t = normalise("MATHS", cat, tag)
        desc = DESCRIPTIONS.get(c)
        label = c + (f" · {t}" if t else "")
        if desc:
            parts.append(f"Error type ({label}): {desc}")
    if not parts:
        parts.append("The final answer did not match. Compare each line of your working with the worked solution to find the first line that differs.")
    return "\n\n".join(parts)


def explain_self_marked(q, p: dict, attempt: Attempt) -> str:
    lost = attempt.mark_possible - attempt.mark_awarded
    s = (f"You recorded {attempt.mark_awarded:g} of {attempt.mark_possible:g}. Look at the marking guideline line by line: each line you could not "
         f"tick is where the {lost:g} mark{'s' if lost != 1 else ''} went.")
    if q.marks >= 2:
        s += " In multi-mark questions most marks are for method, so a missing intermediate step costs a mark even when the final line is right."
    return s


# --------------------------------------------------------------------------- Written ---
def why_prompt(ctx: dict) -> str:
    verb = (ctx.get("directive_verb") or "").lower()
    lines = [
        "TASK: Explain to the student, in 100-180 words, WHY they did not receive full marks. This is NOT a repeat of the marking "
        "feedback. For each mark lost: name the band step from the criteria, quote ONE short phrase from the student's own response, and "
        "show the ONE move that would earn the next mark, grounded in the stimulus where there is one. Teach the principle (how the "
        "required depth changes with the mark value and the directive verb).",
        f"SUBJECT: {ctx['subject_name']}",
        f"QUESTION ({ctx['marks']} marks, directive verb: {ctx.get('directive_verb') or 'none'}"
        + (f" = {VERBS[verb]}" if verb in VERBS else "") + f"):\n{ctx['question']}",
    ]
    if ctx.get("stimulus"):
        lines.append(f"STIMULUS:\n<<<STIMULUS\n{ctx['stimulus'][:6000]}\nSTIMULUS>>>")
    if ctx.get("criteria"):
        lines.append(f"MARKING CRITERIA (app-authored unless stated official):\n{ctx['criteria']}")
    if ctx.get("model_answer"):
        lines.append(f"MODEL RESPONSE (for your reference; do not paste it):\n{ctx['model_answer'][:4000]}")
    if ctx.get("evidence") is not None and ctx.get("subject") == "LEGAL":
        lines.append("LEGAL EVIDENCE BANK (verification status per item) — cite ONLY these items, by exact title, and describe an "
                     "UNVERIFIED item as 'to be verified'; never name any other Act, case, report or statistic:\n"
                     + json.dumps([{"title": e["title"], "type": e.get("type"), "verified": e.get("verified")} for e in ctx["evidence"]], ensure_ascii=False))
    lines += [
        f"MARK AWARDED: {ctx['mark']} / {ctx['marks']}",
        f"STUDENT RESPONSE:\n<<<RESPONSE\n{ctx['response']}\nRESPONSE>>>",
        f"MARKER'S NOTES (already shown to the student — do not repeat): {json.dumps(ctx.get('feedback', {}), ensure_ascii=False)[:2500]}",
        'Reply ONLY with JSON: {"explanation": "..."}',
    ]
    return "\n\n".join(lines)


def _ai_written(db: Session, q, p: dict, attempt: Attempt, code: str) -> str | None:
    settings = st.all_settings(db)
    provider = get_provider(settings)
    if not provider.generative:
        return None
    stim = q.stimulus.body if q.stimulus else None
    evidence = legal.evidence_for(db, q) if code == "LEGAL" else None
    ladder = criteria_ladder(q)
    criteria = "\n".join(f"{c['mark']} marks: {c['descriptor']}" for c in ladder) or q.marking_guideline
    ctx = {"subject": code, "subject_name": db.get(Subject, q.subject_id).name, "marks": q.marks, "directive_verb": q.directive_verb,
           "question": q.question_text, "stimulus": stim, "criteria": criteria, "model_answer": q.model_answer or p.get("model_answer"),
           "evidence": evidence, "mark": attempt.mark_awarded, "response": attempt.response_text, "feedback": p.get("result", {})}
    for _try in range(2):
        try:
            text = provider.complete_json(prompts.SYSTEM, why_prompt(ctx), WhyLost).explanation
        except (AIError, AIUnavailable) as exc:
            log.warning("why_lost AI failed: %s", exc)
            return None
        if code != "LEGAL":
            return text
        bad = legal.unverified_citations(text, evidence or [])
        if not bad:
            checked = [e["verified"] for e in (evidence or []) if e.get("verified") and e["verified"] != "UNVERIFIED"]
            if checked:
                text += f"\n\nCurrent information checked: {max(checked)}."
            return text
        log.warning("why_lost cited unverified authorities %s; %s", bad, "regenerating" if _try == 0 else "falling back to offline")
    return None
