"""Deterministic Mathematics marking with SymPy.

Accepts typed answers in plain calculator style (``3x^2 - 2``, ``sqrt(2)/2``, ``e^(2x)``,
``2pi/3``), simple LaTeX (``\\frac{1}{3}``, ``\\sqrt{2}``) and common unicode (``√``, ``π``).
Supports exact values, equivalent algebraic forms, numerical tolerances, units, unordered or
ordered lists of answers, primitives (+C) and multiple-choice letters."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
LOCALS = {
    "e": sp.E, "E": sp.E, "pi": sp.pi, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt,
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "abs": sp.Abs,
    "x": sp.Symbol("x"), "n": sp.Symbol("n"), "t": sp.Symbol("t"), "k": sp.Symbol("k"),
}
UNIT_WORDS = r"(square\s+units|units\^?2|units|cm\^?2|cm²|m²|m\^?2|m/s\^?2|m/s²|m/s|cm|mm|km|kg|seconds|s|metres|m|dollars|%)"


class ParseError(ValueError):
    pass


def _latex_to_plain(s: str) -> str:
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", "").replace("\\!", "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    for _ in range(6):  # nested \frac{..}{..}
        s2 = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", s)
        s2 = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", s2)
        s2 = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", s2)
        if s2 == s:
            break
        s = s2
    s = s.replace("\\pi", "pi").replace("\\ln", "ln").replace("\\log", "log")
    s = s.replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    s = s.replace("{", "(").replace("}", ")").replace("\\", "")
    return s


def normalise(text: str) -> str:
    s = (text or "").strip()
    s = s.strip("$").replace("\\(", "").replace("\\)", "")
    s = s.replace("−", "-").replace("–", "-").replace("×", "*").replace("÷", "/").replace("·", "*")
    s = s.replace("π", "pi").replace("√", "sqrt").replace("²", "^2").replace("³", "^3")
    s = _latex_to_plain(s)
    s = re.sub(r"sqrt\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", s)
    s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s.replace("$", "").strip()) else s
    s = s.replace("$", "")
    return s.strip()


def strip_units(s: str) -> str:
    return re.sub(rf"\s*{UNIT_WORDS}\s*$", "", s, flags=re.I).strip()


def strip_lhs(s: str) -> str:
    # "y = 3x+1", "f'(x) = ...", "x = 4" -> right-hand side
    if "=" in s:
        return s.split("=")[-1].strip()
    return s


def parse(text: str) -> sp.Expr:
    s = strip_units(strip_lhs(normalise(text)))
    if not s:
        raise ParseError("empty answer")
    try:
        expr = parse_expr(s, local_dict=dict(LOCALS), transformations=TRANSFORMS, evaluate=True)
    except Exception as exc:  # SyntaxError, TokenError, TypeError...
        raise ParseError(str(exc)) from exc
    if not isinstance(expr, sp.Basic):
        raise ParseError("not an expression")
    return sp.sympify(expr)


def equivalent(a: sp.Expr, b: sp.Expr, tol: float = 0.0) -> bool:
    try:
        diff = sp.simplify(a - b)
        if diff == 0:
            return True
    except Exception:
        pass
    free = sorted((a.free_symbols | b.free_symbols), key=str)
    points = [0.37, 1.13, 2.71, -0.83, 3.3]
    try:
        for p in points:
            subs = {s: p + i * 0.17 for i, s in enumerate(free)}
            va, vb = complex(sp.N(a.subs(subs))), complex(sp.N(b.subs(subs)))
            if math.isnan(va.real) or math.isnan(vb.real):
                return False
            scale = max(1.0, abs(vb))
            limit = tol if tol else 1e-9 * scale
            if abs(va - vb) > limit:
                return False
            if not free:
                break
        return True
    except Exception:
        return False


@dataclass
class MathsResult:
    correct: bool
    mark: float
    possible: float
    category: str | None = None  # error category when not correct
    diagnosis: str | None = None
    student_display: str = ""
    notes: list[str] = field(default_factory=list)
    parsed: bool = True


def _match_common_errors(student: sp.Expr, common_errors: list[dict]) -> dict | None:
    for ce in common_errors or []:
        try:
            if "," in ce["answer"]:
                continue
            if equivalent(student, sp.sympify(ce["answer"], locals=LOCALS)):
                return ce
        except Exception:
            continue
    return None


def _heuristic_category(student: sp.Expr, correct: sp.Expr) -> tuple[str, str]:
    try:
        if equivalent(student, -correct):
            return "sign", "Your answer has the right size but the wrong sign; track each negative carefully."
        sv, cv = float(sp.N(student)), float(sp.N(correct))
        if cv != 0 and abs(sv - cv) / abs(cv) < 0.1:
            return "arithmetic", "You are very close to the correct value, which suggests an arithmetic or rounding slip rather than a wrong method."
        if cv != 0 and (abs(sv / cv - 2) < 1e-9 or abs(sv / cv - 0.5) < 1e-9):
            return "careless error", "Your answer is out by a factor of 2: check a halving/doubling step (e.g. \\(\\frac{n}{2}\\) or a chain-rule factor)."
    except Exception:
        pass
    return "conceptual", "Your answer does not match a simple slip; compare your method with the worked solution step by step."


def mark_answer(response: str, answer: dict, marks: int, common_errors: list[dict] | None = None) -> MathsResult:
    kind = answer.get("type", "num")
    resp = (response or "").strip()
    if not resp:
        return MathsResult(False, 0, marks, "incomplete reasoning", "No answer was given.", parsed=False)

    if kind == "mcq":
        letter = re.sub(r"[^A-Da-d]", "", resp)[:1].upper()
        ok = letter == answer["value"].upper()
        return MathsResult(ok, marks if ok else 0, marks, None if ok else "conceptual", None, letter)

    if kind == "set":
        bare = re.sub(r"^[\s(\[{]+|[\s)\]}]+$", "", resp)  # "(2, 5)" -> "2, 5"
        parts = [p for p in re.split(r"\s*(?:,|;|\bor\b|\band\b)\s*", bare) if p.strip()]
        try:
            got = [parse(p) for p in parts]
        except ParseError:
            return MathsResult(False, 0, marks, "notation", "I could not read one of the values. Enter them separated by commas, e.g. 2, -3.", resp, parsed=False)
        want = [sp.sympify(v, locals=LOCALS) for v in answer["values"]]
        if answer.get("ordered"):
            matched = sum(1 for g, w in zip(got, want) if equivalent(g, w))
        else:
            remaining = list(want)
            matched = 0
            for g in got:
                for w in remaining:
                    if equivalent(g, w):
                        remaining.remove(w)
                        matched += 1
                        break
        extra = max(0, len(got) - len(want))
        ok = matched == len(want) and extra == 0
        mark = marks if ok else math.floor(marks * max(0, matched - extra) / len(want))
        cat, diag = (None, None)
        if not ok:
            cat = "incomplete reasoning" if matched and len(got) < len(want) else ("interpretation" if extra else "conceptual")
            diag = f"{matched} of {len(want)} required values correct" + (f"; {extra} extra value(s) given" if extra else "") + "."
        return MathsResult(ok, mark, marks, cat, diag, ", ".join(sp.sstr(g) for g in got))

    has_c = bool(re.search(r"\+\s*[cC]\s*$", resp))
    text = re.sub(r"\+\s*[cC]\s*$", "", resp) if kind == "antiderivative" else resp
    try:
        student = parse(text)
    except ParseError:
        return MathsResult(False, 0, marks, "notation",
                           "I could not read this as a mathematical expression. Try plain calculator style, e.g. 3x^2 - 2, sqrt(2)/2, e^(2x), 2pi/3.",
                           resp, parsed=False)
    correct = sp.sympify(answer["value"], locals=LOCALS)
    display = sp.sstr(student)
    notes: list[str] = []

    if kind == "antiderivative":
        var = sp.Symbol(answer.get("var", "x"))
        ok = equivalent(sp.diff(student, var), sp.diff(correct, var))
        if ok and not has_c:
            notes.append("Remember '+ C' for an indefinite integral.")
        if ok:
            return MathsResult(True, marks, marks, None, None, display, notes)
    else:
        tol = float(answer.get("tol", 0) or 0)
        ok = equivalent(student, correct, tol)
        if ok:
            return MathsResult(True, marks, marks, None, None, display, notes)
        # numerically right but not exact (exact value required)
        if not tol and not (student.free_symbols or correct.free_symbols):
            try:
                if abs(float(sp.N(student)) - float(sp.N(correct))) <= 0.005 * max(1, abs(float(sp.N(correct)))):
                    return MathsResult(False, max(0, marks - 1), marks, "notation",
                                       "Your decimal value is right, but the question asks for an exact value (fractions, surds, \\(\\pi\\), \\(e\\) or logs).",
                                       display, notes)
            except Exception:
                pass

    ce = _match_common_errors(student, common_errors or [])
    if ce:
        return MathsResult(False, 0, marks, ce["category"], ce["diagnosis"], display, notes)
    cat, diag = _heuristic_category(student, correct)
    return MathsResult(False, 0, marks, cat, diag, display, notes)
