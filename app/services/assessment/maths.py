"""Mathematics (and multiple-choice) deterministic marking, feedback and 'why did I lose the mark?'
(owner: maths).

Feedback covers the ten elements of spec 5C: the student's answer, the mark, the correct answer,
the complete worked solution, the exact step where the reasoning diverged, the concept, a quicker
method, exam technique, the syllabus focus area / skill, and a revision recommendation. Errors are
tagged on two axes: ``error_category`` (spec 5C list) and ``error_topic_tag`` (spec 23 list)."""
from __future__ import annotations

import re

import sympy as sp
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.marking import maths as maths_marker
from app.marking.maths_parser import ParseError
from app.models import Question
from app.services.assessment.common import NO_OFFICIAL, plan_and_outcome, subject_code
from app.services.assessment.written import written_ctx

METHOD_LABEL = "Method marks estimated automatically from your working (offline check, not an official mark)."


# ---------------------------------------------------------------- display ---
def _latex_value(v: str) -> str:
    try:
        return sp.latex(sp.sympify(v, locals=maths_marker.LOCALS))
    except Exception:
        return str(v)


def spec_display(a: dict, options: list[str] | None = None) -> str:
    """LaTeX for the correct answer of an answer spec (trusted, stored values only)."""
    kind = a.get("type")
    if kind == "mcq":
        opts = options or a.get("options") or []
        return next(("\\text{" + o.replace("{", "").replace("}", "") + "}" for o in opts if o.strip().upper().startswith(str(a["value"]).upper())),
                    str(a["value"]))
    if kind == "set":
        return ", ".join(_latex_value(v) for v in a["values"])
    if kind == "interval":
        try:
            return maths_marker.region_latex(maths_marker.stored_region(a), a.get("var", "x"))
        except Exception:
            return str(a.get("intervals"))
    if kind == "parts":
        return " \\quad ".join(f"\\text{{({p['label']})}}\\ {spec_display(p['answer'], p.get('options'))}" for p in a.get("parts", []))
    if "dp" in a:
        try:
            val = maths_marker.rounded_value(maths_marker.stored_ast(a["value"]), int(a["dp"]))
            s = f"{val:,}" if a.get("units") == "$" else str(val)
            s = s.replace(",", "{,}")
        except Exception:
            s = str(a.get("value"))
    else:
        s = _latex_value(a.get("value", ""))
    if kind == "antiderivative":
        s += " + C"
    u = a.get("units")
    if u == "$":
        s = "\\$" + s
    elif u == "%":
        s += "\\%"
    elif u:
        s += f"\\ \\text{{{maths_marker.unit_label(maths_marker.canonical_unit(u) or u)}}}"
    return s


def answer_display(q: Question) -> str:
    a = q.answer or {}
    try:
        return spec_display(a, q.options)
    except Exception:
        return str(a.get("value", ""))


# -------------------------------------------------------- divergence / method ---
def _part_first_steps(steps: list[str]) -> dict[str, int]:
    """Steps that start '(a)', '(b)' ... begin each part (1-based index)."""
    out: dict[str, int] = {}
    for i, s in enumerate(steps, 1):
        m = re.match(r"\s*\(([a-h])\)", s)
        if m and m.group(1) not in out:
            out[m.group(1)] = i
    return out


def _divergence_step(category: str | None, steps: list[str], part: str | None = None, explicit: int | None = None) -> int:
    if not steps:
        return 0
    if explicit and 1 <= explicit <= len(steps):
        return explicit
    firsts = _part_first_steps(steps)
    if part and part in firsts:
        start = firsts[part]
        later = sorted(v for v in firsts.values() if v > start)
        end = (later[0] - 1) if later else len(steps)
        return start if category in ("formula selection", "conceptual", "interpretation") else end
    if category in ("formula selection", "conceptual", "interpretation"):
        return 1
    return len(steps)


def _working_candidates(working: str) -> list[str]:
    out = []
    for line in (working or "").splitlines()[:60]:
        for piece in re.split(r"=|⇒|=>|\btherefore\b|∴|,|;", line):
            piece = piece.strip().rstrip(".")
            if piece and len(piece) <= 120 and re.search(r"[0-9a-z]", piece, re.I):
                out.append(piece)
    return out[:200]


def checkpoint_marks(working: str | None, checkpoints: list[dict], part: str | None = None) -> tuple[float, list[dict]]:
    """Match the template's intermediate results (e.g. the correct derivative) in the student's
    working. Returns the method marks earned and the checkpoints found."""
    if not working or not checkpoints:
        return 0.0, []
    cands = []
    for c in _working_candidates(working):
        try:
            cands.append(maths_marker.read_value(c, numeric=True).ast)
        except ParseError:
            continue
        except Exception:
            continue
    found, total = [], 0.0
    for cp in checkpoints:
        if (cp.get("part") or None) != part:
            continue
        try:
            names = list(cp.get("vars") or ["x", "n", "t", "k"])
            target = maths_marker.stored_ast(cp["value"], names)
        except Exception:
            continue
        if any(maths_marker.same(c, target, names) for c in cands):
            found.append(cp)
            total += float(cp.get("marks", 1))
    return total, found


# ------------------------------------------------------------------ outcome ---
def _syllabus(db: Session, q: Question, item, outcome: str) -> tuple[str, str | None]:
    """Spec element 9 without placeholder text: focus area + learning-plan subtopic + the skill tested.
    Official outcome codes are shown only once they have been imported."""
    if outcome and "not yet imported" in outcome:
        outcome = outcome.split(" — ")[0].strip()
    parts = []
    if outcome:
        parts.append(outcome)
    if item is not None:
        parts.append(f"Learning plan {item.code} {item.title}")
    skill = (q.solution or {}).get("skill")
    return " · ".join(parts) or "Mathematics Advanced", skill


# ---------------------------------------------------------------- marking ---
def mark_deterministic(db: Session, q: Question, response: str, working: str | None, settings: dict) -> tuple[float, dict, list[str], str]:
    sol = q.solution or {}
    answer = q.answer or {}
    res = maths_marker.mark_answer(response, answer, q.marks, sol.get("common_errors"), options=q.options)
    item, outcome = plan_and_outcome(db, q)
    code = subject_code(db, q)
    if answer.get("type") == "mcq":
        rationale = (sol.get("option_rationales") or {}).get(res.student_display) if res.student_display else None
        payload = {
            "kind": "mcq", "mark": res.mark, "max": q.marks, "correct": res.correct, "student_answer": res.student_display or response,
            "correct_answer": answer_display(q), "explanation": sol.get("explanation") or " ".join(sol.get("steps", [])),
            "concept": sol.get("concept"), "outcome": outcome, "method": "deterministic",
            "label": "Marked automatically (multiple choice).",
        }
        if rationale:
            payload["chosen_rationale"] = rationale
        if not res.correct and code == "MATHS":
            payload["error_category"] = res.category or "conceptual"
            payload["error_topic_tag"] = res.topic_tag
        cats = [] if res.correct else (["conceptual"] if code == "MATHS" else [])
        return res.mark, payload, cats, "deterministic"

    steps = sol.get("steps", [])
    syllabus, skill = _syllabus(db, q, item, outcome)
    notes = list(res.notes)
    mark = float(res.mark)
    parts_fb: list[dict] = []
    error_tags: list[dict] = []
    first_wrong_part = None

    if answer.get("type") == "parts":
        for pspec, pr in zip(answer.get("parts", []), res.parts):
            pm = float(pr["mark"])
            entry = {"label": pspec["label"], "marks": pspec.get("marks", 1), "mark": pm, "correct": pr["correct"], "given": pr.get("given", ""),
                     "student": pr.get("student"), "latex": pr.get("latex"), "correct_answer": spec_display(pspec["answer"], pspec.get("options")),
                     "category": pr.get("category"), "topic_tag": pr.get("topic_tag"), "diagnosis": pr.get("diagnosis"),
                     "prompt": pspec.get("prompt")}
            if not pr["correct"]:
                if first_wrong_part is None:
                    first_wrong_part = pspec["label"]
                # offline method marks for this part from its checkpoints
                cm, found = checkpoint_marks(working, sol.get("checkpoints", []), pspec["label"])
                cap = max(0.0, float(pspec.get("marks", 1)) - 1)
                if cm and min(cm, cap) > pm:
                    entry["method_marks"] = min(cm, cap) - pm
                    entry["checkpoints_found"] = [c.get("label") for c in found]
                    pm = min(cm, cap)
                    entry["mark"] = pm
                if pr.get("category"):
                    error_tags.append({"category": pr["category"], "topic_tag": pr.get("topic_tag"), "part": pspec["label"], "diagnosis": pr.get("diagnosis")})
            parts_fb.append(entry)
        mark = min(float(q.marks), sum(e["mark"] for e in parts_fb))
        if any("method_marks" in e for e in parts_fb):
            notes.append(METHOD_LABEL)
    elif not res.correct:
        if res.category:
            error_tags.append({"category": res.category, "topic_tag": res.topic_tag, "part": None, "diagnosis": res.diagnosis})
        cm, found = checkpoint_marks(working, sol.get("checkpoints", []))
        cap = max(0.0, float(q.marks) - 1)
        if cm and min(cm, cap) > mark:
            mark = min(cm, cap)
            notes.append(METHOD_LABEL + " Found in your working: " + "; ".join(c.get("label", "an intermediate result") for c in found) + ".")
        if res.common_error and res.mark > 0:
            notes.append(METHOD_LABEL)

    correct = bool(res.correct)
    step_no, divergence = 0, None
    if not correct:
        step_no = _divergence_step(res.category, steps, first_wrong_part, res.step)
        if answer.get("type") != "parts" and not res.step:
            # a matched checkpoint means the reasoning was right up to that step
            _, found = checkpoint_marks(working, sol.get("checkpoints", []))
            later = [c.get("step") for c in found if c.get("step")]
            if later and max(later) < len(steps):
                step_no = max(later) + 1
        divergence = (res.diagnosis or "") + (f" Compare your working with step {step_no} of the worked solution." if step_no else "")

    method_note = None
    from app.services import working_photos as wp

    photos = wp.pending_any(db, q.id)  # photos of handwritten working, attached to the attempt after marking
    if photos:
        working = (working or "").strip() or f"(handwritten working: {len(photos)} photo{'s' if len(photos) != 1 else ''} attached)"
    if not correct and working and working.strip() and q.marks >= 2:
        provider = get_provider(settings)
        if provider.generative:
            try:
                ctx = written_ctx(db, q, f"FINAL ANSWER: {response}\nWORKING:\n{working}", settings, maths=True)
                imgs = wp.images(photos) if photos and getattr(provider, "vision", False) else None
                r = provider.mark_response(ctx, images=imgs) if imgs else provider.mark_response(ctx)
                mark = min(float(q.marks) - 1, max(mark, r.mark_awarded))  # method marks only; the answer is wrong
                method_note = f"Method marks assessed by AI from your working ({NO_OFFICIAL}): {r.marking_rationale or '; '.join(r.weaknesses[:2])}"
            except (AIError, AIUnavailable) as exc:
                method_note = f"Your working could not be assessed by AI ({exc}). Check it against the worked solution."
        elif mark == 0:
            method_note = ("Your working was saved. Without an AI provider only the final answer and recognisable intermediate results are "
                           "checked automatically; compare your working with the worked solution to see where method marks would be earned.")
    elif not correct and (not working or not working.strip()) and q.marks >= 3 and res.category == "conceptual" and not res.common_error:
        # nothing to diagnose from: spec 5C 'insufficient working'
        res.category = "insufficient working"
        if error_tags:
            error_tags[0]["category"] = "insufficient working"
        divergence = ("No working was shown, so it is not possible to see where the reasoning went wrong — and no method marks can be "
                      "awarded. " + (divergence or ""))
    if method_note:
        notes.append(method_note)

    category = None if correct else (error_tags[0]["category"] if error_tags else res.category)
    topic_tag = None if correct else (error_tags[0].get("topic_tag") if error_tags else res.topic_tag)
    rec = None
    if item:
        focus = f" — focus on: {category}" + (f" ({topic_tag})" if topic_tag else "") if category else ""
        rec = f"Revise {item.code} {item.title}{focus}."
    payload = {
        "kind": "maths", "mark": mark, "max": q.marks, "correct": correct, "student_answer": response, "student_parsed": res.student_display,
        "student_latex": res.latex, "correct_answer": answer_display(q), "worked_solution": steps, "divergence": divergence,
        "divergence_step": step_no, "concept": sol.get("concept"), "quicker": sol.get("quicker"), "technique": sol.get("technique"),
        "outcome": syllabus, "skill": skill, "revision": rec, "error_category": category, "error_topic_tag": topic_tag,
        "error_tags": error_tags, "parts": parts_fb, "notes": notes, "method": "deterministic",
        "label": "Final answer checked automatically (equivalent forms accepted).",
    }
    cats = []
    for t in error_tags:
        if t["category"] and t["category"] not in cats:
            cats.append(t["category"])
    if not correct and not cats and category:
        cats = [category]
    return mark, payload, cats, "deterministic"


# --------------------------------------------------------------- why lost ---
_LEADS = {
    "careless error": "This looks like a slip rather than a misunderstanding.",
    "arithmetic": "Your approach looks right, but a calculation went wrong.",
    "algebraic": "The set-up was reasonable, but an algebraic step (expanding, factorising, rearranging or simplifying) went wrong.",
    "notation": "The value may be right, but it was not in the form the question asked for.",
    "formula selection": "The wrong formula (or the wrong version of it) was used.",
    "interpretation": "The question was answered, but not the question that was asked.",
    "incomplete reasoning": "The answer stopped short of what was asked.",
    "insufficient working": "Without working, a marker can only judge the final line — and it was wrong, so no method marks could be given.",
    "conceptual": "The underlying idea needs another look.",
    "sign": "The method was probably right, but a sign changed somewhere.",
}
_TAG_ADVICE = {
    "sign error": "Rewrite each subtraction of a bracket with the sign distributed, and check the sign of every term at the end.",
    "chain rule": "Every time you differentiate a function of a function, multiply by the derivative of the inside.",
    "algebra": "Check each rearrangement by substituting a simple number into both lines.",
    "domain/range": "Test each solution against the restrictions in the question before you finalise it.",
    "calculator error": "Re-enter the calculation in one line with brackets, and check the calculator mode (radians/degrees).",
    "probability interpretation": "Translate the words into a probability statement (P(A ∪ B), P(X ≥ 2) …) before calculating.",
    "rounding": "Keep full calculator accuracy until the last line, then round once, exactly as the question asks.",
    "units": "State the units the question uses, and convert before calculating if they differ.",
    "exact values": "'Exact' means fractions, surds, π, e or logs — no decimals.",
    "constant of integration": "Use the given condition to find the constant before evaluating.",
    "limits of integration": "Substitute the upper limit, then subtract the value at the lower limit.",
    "area below the axis": "Split the region at the x-intercepts and take the absolute value of each part below the axis.",
    "financial periods": "Match the rate to the period: an annual rate compounded monthly is r/12 per month for 12n months.",
    "inequality direction": "Find the boundary values, then test one value in each region to see where the condition holds.",
    "product rule": "For a product use u'v + uv'; write u, v, u', v' first.",
    "quotient rule": "For a quotient use (vu' − uv')/v²; the order in the numerator matters.",
    "log laws": "log(ab) = log a + log b and log(aⁿ) = n log a — there is no rule for log(a + b).",
    "stationary points": "Stationary points need f'(x) = 0 and a justification of their nature.",
    "sequence formula": "Write a, d (or r) and n explicitly before substituting into Tₙ.",
    "series formula": "Check whether the question wants a term (Tₙ) or a sum (Sₙ).",
}


def why_lost_maths(q: Question, p: dict) -> str:
    cat = p.get("error_category") or "conceptual"
    parts = [_LEADS.get(cat, "The answer did not match.")]
    if p.get("parts"):
        lost = [e for e in p["parts"] if e.get("mark", 0) < e.get("marks", 0)]
        if lost:
            parts.append("Marks were lost in " + ", ".join(f"part ({e['label']}) ({e.get('mark', 0):g}/{e.get('marks')})" for e in lost) + ".")
    if p.get("divergence"):
        parts.append(p["divergence"])
    tag = p.get("error_topic_tag")
    if tag and _TAG_ADVICE.get(tag):
        parts.append(f"Fix for next time ({tag}): {_TAG_ADVICE[tag]}")
    if p.get("concept"):
        parts.append(f"Key idea: {p['concept']}")
    if q.marks >= 2:
        parts.append(f"In a {q.marks}-mark question, markers award marks for correct method as well as the answer, so writing each step (formula, substitution, simplification) protects marks even if the final line goes wrong.")
    if p.get("technique"):
        parts.append(f"Exam technique: {p['technique']}")
    return " ".join(parts)
