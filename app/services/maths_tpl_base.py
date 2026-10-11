"""Shared building blocks for the Mathematics question templates (owner: maths).

A template is ``fn(rng, difficulty) -> Generated``. Difficulty is real:

* 1 = foundation: one skill, friendly numbers, 1–2 marks;
* 2 = HSC-standard: two or three steps, 2–3 marks;
* 3 = challenging: an HSC-style multi-part question (parts (a), (b), (c) …, 4–6 marks) chaining
  sub-skills, or a single 4-mark multi-step problem.

Every common error is tagged on two axes — ``category`` (spec 5C) and ``topic_tag`` (spec 23) — and
may name the worked-solution ``step`` where it happens. ``params`` carries the generating values so
the test-suite can recompute every answer independently; it is never stored with the question."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction

import sympy as sp

x, n, t, k = sp.symbols("x n t k")
L = sp.latex
Rng = random.Random


@dataclass
class Generated:
    text: str
    answer: dict
    marks: int
    difficulty: int
    steps: list[str]
    concept: str
    technique: str
    quicker: str | None = None
    common_errors: list[dict] = field(default_factory=list)
    directive_verb: str = "Find"
    question_type: str = "working"
    skill: str = ""
    checkpoints: list[dict] = field(default_factory=list)
    params: dict = field(default_factory=dict)  # for independent verification only (not stored)
    options: list[str] | None = None

    def solution(self) -> dict:
        return {
            "steps": self.steps,
            "concept": self.concept,
            "quicker": self.quicker,
            "technique": self.technique,
            "common_errors": self.common_errors,
            "skill": self.skill,
            "checkpoints": self.checkpoints,
        }


# ------------------------------------------------------------- formatting ---
def ex(e) -> str:
    """A stored answer string the marker's parser reads back (SymPy ``sstr``)."""
    if isinstance(e, str):
        return e
    if isinstance(e, Fraction):
        return str(e.numerator) if e.denominator == 1 else f"{e.numerator}/{e.denominator}"
    if isinstance(e, float):
        e = sp.nsimplify(e)
    return sp.sstr(sp.sympify(e))


def lt(e) -> str:
    return L(sp.sympify(e))


def sgn(c, first: bool = False) -> str:
    """'+ 3' / '- 3' for building expressions in text; never '+ -3' or '+ 0'."""
    c = sp.sympify(c)
    if first:
        return L(c)
    if c == 0:
        return ""
    return f"- {L(-c)}" if c.is_negative else f"+ {L(c)}"


def marks_word(m: int) -> str:
    return f"{m} mark" + ("" if m == 1 else "s")


def multipart(stem: str, parts: list[tuple[str, str, int]]) -> str:
    """HSC layout: the stem, then each part on its own paragraph with its marks."""
    out = [stem.strip()] if stem else []
    for lab, txt, mk in parts:
        out.append(f"({lab}) {txt.strip()} ({marks_word(mk)})")
    return "\n\n".join(out)


def money(v, dp: int = 2) -> str:
    v = float(v)
    return f"\\${v:,.{dp}f}".replace(",", "{,}")


def dollars(v, dp: int = 2) -> str:
    """Plain-text dollars for question text (outside maths mode)."""
    return f"${float(v):,.{dp}f}"


def ordinal(m: int) -> str:
    suf = "th" if 10 <= m % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(m % 10, "th")
    return f"{m}{suf}"


# ---------------------------------------------------------------- answers ---
def A_num(v) -> dict:
    return {"type": "num", "value": ex(v)}


def A_units(v, units: str) -> dict:
    return {"type": "num", "value": ex(v), "units": units}


def A_round(v, dp: int, units: str | None = None) -> dict:
    a = {"type": "num", "value": ex(v), "dp": dp}
    if units:
        a["units"] = units
    return a


def A_approx(v, tol: float, units: str | None = None) -> dict:
    a = {"type": "num", "value": ex(v), "tol": tol}
    if units:
        a["units"] = units
    return a


def A_expr(v, vars_=("x",)) -> dict:
    return {"type": "expr", "value": ex(v), "vars": list(vars_)}


def A_prim(v, var: str = "x") -> dict:
    return {"type": "antiderivative", "value": ex(v), "var": var}


def A_set(vals, ordered: bool = False) -> dict:
    a = {"type": "set", "values": [ex(v) for v in vals]}
    if ordered:
        a["ordered"] = True
    return a


def A_iv(intervals, var: str = "x", ends: str = "matter") -> dict:
    """intervals: [(lo, hi, lo_closed, hi_closed)] with None for an unbounded end."""
    rows = []
    for lo, hi, lc, hc in intervals:
        rows.append(["-oo" if lo is None else ex(lo), "oo" if hi is None else ex(hi), bool(lc) and lo is not None, bool(hc) and hi is not None])
    return {"type": "interval", "var": var, "intervals": rows, "ends": ends}


def A_mcq(letter: str, options: list[str] | None = None) -> dict:
    a = {"type": "mcq", "value": letter}
    if options:
        a["options"] = list(options)
    return a


def P(label: str, marks: int, answer: dict, prompt: str | None = None, options: list[str] | None = None) -> dict:
    d = {"label": label, "marks": marks, "answer": answer}
    if prompt:
        d["prompt"] = prompt
    if options:
        d["options"] = options
    return d


def A_parts(*parts: dict) -> dict:
    return {"type": "parts", "parts": list(parts)}


def err(answer, category: str, topic_tag: str | None, diagnosis: str, step: int | None = None, marks: float = 0,
        part: str | None = None) -> dict:
    d = {"answer": answer if isinstance(answer, str) and "," in answer else ex(answer), "category": category,
         "topic_tag": topic_tag, "diagnosis": diagnosis}
    if step:
        d["step"] = step
    if marks:
        d["marks"] = marks
    if part:
        d["part"] = part
    return d


def cp(value, label: str, step: int | None = None, marks: float = 1, part: str | None = None, vars_=("x",)) -> dict:
    """An intermediate result that earns a method mark when it appears in the student's working."""
    d = {"value": ex(value), "label": label, "marks": marks, "vars": list(vars_)}
    if step:
        d["step"] = step
    if part:
        d["part"] = part
    return d


def model_response(answer: dict) -> str:
    """A correct typed response for an answer spec (used by the self-test and tests)."""
    kind = answer.get("type")
    if kind == "set":
        return ", ".join(answer["values"])
    if kind == "mcq":
        return answer["value"]
    if kind == "interval":
        var = answer.get("var", "x")
        out = []
        for lo, hi, lc, hc in answer["intervals"]:
            lo_inf, hi_inf = str(lo) in ("-oo",), str(hi) in ("oo",)
            if lo_inf and hi_inf:
                out.append("all real x")
            elif lo_inf:
                out.append(f"{var} {'<=' if hc else '<'} {hi}")
            elif hi_inf:
                out.append(f"{var} {'>=' if lc else '>'} {lo}")
            else:
                out.append(f"{lo} {'<=' if lc else '<'} {var} {'<=' if hc else '<'} {hi}")
        return " or ".join(out)
    if kind == "parts":
        return "\n".join(f"({p['label']}) {model_response(p['answer'])}" for p in answer["parts"])
    if "dp" in answer:
        from app.marking.maths import rounded_value, stored_ast

        return str(rounded_value(stored_ast(answer["value"]), int(answer["dp"])))
    return answer["value"]


def pick(r: Rng, seq):
    return seq[r.randrange(len(seq))]


def nonzero(r: Rng, lo: int, hi: int) -> int:
    v = 0
    while v == 0:
        v = r.randint(lo, hi)
    return v


def series(terms) -> str:
    """'3 - 6 + 12' rather than '3 + -6 + 12'."""
    terms = [sp.sympify(v) for v in terms]
    s = L(terms[0])
    for v in terms[1:]:
        s += f" - {L(-v)}" if v.is_negative else f" + {L(v)}"
    return s


def S(*vals) -> str:
    """A comma-separated answer string for a set / ordered-pair common error."""
    return ", ".join(ex(v) for v in vals)


def region(intervals, var: str = "x") -> str:
    """The typed form of a region, for interval common errors: [(lo, hi, lo_closed, hi_closed)]."""
    return model_response(A_iv(intervals, var))


def mcq_options(*texts: str) -> list[str]:
    return [f"{chr(65 + i)}. {t}" for i, t in enumerate(texts)]


def pl(e, var=x) -> str:
    """LaTeX for a polynomial in descending powers of ``var`` even when it has symbolic coefficients
    (SymPy alone would print 'k x + x^{3} + 4 x^{2}')."""
    e = sp.expand(sp.sympify(e))
    try:
        poly = sp.Poly(e, var)
    except sp.PolynomialError:
        return L(e)
    out = ""
    for (deg,), coeff in sorted(poly.terms(), key=lambda t: -t[0][0]):
        tl = L(coeff * var**deg).strip()
        if not out:
            out = tl
        elif tl.startswith("-"):
            out += " - " + tl[1:].lstrip()
        else:
            out += " + " + tl
    return out or "0"
