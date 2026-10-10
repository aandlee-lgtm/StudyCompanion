"""Mathematics (and multiple-choice) deterministic marking, feedback and 'why did I lose the mark?'."""
from __future__ import annotations

import sympy as sp
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.marking import maths as maths_marker
from app.models import Question
from app.services.assessment.common import NO_OFFICIAL, plan_and_outcome, subject_code
from app.services.assessment.written import written_ctx

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
    item, outcome = plan_and_outcome(db, q)
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
                r = provider.mark_response(written_ctx(db, q, f"FINAL ANSWER: {response}\nWORKING:\n{working}", settings, maths=True))
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


def why_lost_maths(q: Question, p: dict) -> str:
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

