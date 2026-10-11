"""Deterministic Mathematics marking (owner: maths).

Typed answers are read by the locked-down parser in :mod:`app.marking.maths_parser` (never by
``eval``/``sympify``), so a crafted answer cannot run code, hang a worker or raise.
:func:`mark_answer` never raises: anything unexpected becomes a "could not read" result.

Answer specs (JSON, stored in ``Question.answer``):

* ``{"type": "num", "value": "7/2"}`` exact value (decimal approximations lose a mark)
* ``{"type": "num", "value": "29449.6123", "dp": 0, "units": "$"}`` rounded answer: only the
  correctly rounded value earns full marks (``dp`` = decimal places, 0 = nearest whole number)
* ``{"type": "num", "value": "81.5", "tol": 0.5}`` genuinely approximate answer (absolute band)
* ``{"type": "expr", "value": "x*exp(2*x)", "vars": ["x"]}`` any equivalent expression
* ``{"type": "antiderivative", "value": "x**3/3", "var": "x"}`` any primitive (+C noted)
* ``{"type": "set", "values": ["2", "-3"], "ordered": false}`` several values
* ``{"type": "interval", "var": "x", "intervals": [["-2", "3", false, false]], "ends": "matter"}``
  a region of the number line (``"-oo"``/``"oo"`` for unbounded ends; ``"ends": "ignore"`` when
  strict/non-strict does not matter, e.g. increasing/decreasing)
* ``{"type": "mcq", "value": "B"}`` multiple choice
* ``{"type": "parts", "parts": [{"label": "a", "marks": 2, "answer": {...}}, ...]}`` multi-part
  question; the response is one line per part, ``(a) ...`` / ``(b) ...``

Common errors (in ``Question.solution["common_errors"]``) are
``{"answer", "category", "topic_tag", "diagnosis", "step"?, "marks"?, "part"?}``: ``category`` is
one of :data:`CATEGORIES` (spec 5C), ``topic_tag`` one of :data:`TOPIC_TAGS` (spec 23 + extensions),
``step`` the 1-based worked-solution step where that error happens and ``marks`` the method marks a
student who made exactly that error still earns.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import mpmath
import sympy as sp

from app.marking.maths_parser import (
    DEFAULT_VARS,
    MAX_CHARS,
    ParseError,
    evaluate,
    evaluate_mp,
    free_vars,
    has_decimal,
    normalise,
    parse_ast,
    to_latex,
    to_sympy,
    to_text,
)

__all__ = ["ParseError", "MathsResult", "mark_answer", "parse", "normalise", "CATEGORIES", "TOPIC_TAGS", "LOCALS",
           "read_value", "split_parts", "preview"]

# Spec 5C: what the error primarily was.
CATEGORIES = ("conceptual", "algebraic", "arithmetic", "interpretation", "formula selection", "incomplete reasoning",
              "insufficient working", "notation", "careless error")
# Spec 23 (sign error, chain rule, algebra, domain/range, calculator error, probability interpretation) + extensions.
TOPIC_TAGS = ("sign error", "chain rule", "algebra", "domain/range", "calculator error", "probability interpretation",
              "product rule", "quotient rule", "index laws", "log laws", "exact values", "rounding", "units",
              "constant of integration", "limits of integration", "area below the axis", "sequence formula", "series formula",
              "financial periods", "stationary points", "concavity", "trig exact values", "radians", "inequality direction",
              "transformations", "rates and motion", "expected value and variance", "normal distribution", "notation",
              "continuity and differentiability", "integration rules", "differentiation rules", "modelling")

MAX_RESPONSE_CHARS = 3000

# Trusted SymPy namespace for *stored* answers only (display); student input never goes to SymPy.
LOCALS = {
    "e": sp.E, "E": sp.E, "pi": sp.pi, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt,
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "abs": sp.Abs, "Abs": sp.Abs,
    "x": sp.Symbol("x"), "n": sp.Symbol("n"), "t": sp.Symbol("t"), "k": sp.Symbol("k"),
}

# ----------------------------------------------------------------- units ---
UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "units^2": ("units^2", "units^(2)", "unit^2", "u^2", "u^(2)", "u2", "units2", "sq units", "sq. units", "sq unit", "square units",
                "square unit", "units squared", "sq u", "sq. u.", "sq. u", "u squared"),
    "units^3": ("units^3", "units^(3)", "u^3", "u^(3)", "cubic units", "cubic unit", "units cubed", "cu units"),
    "mm^2": ("mm^2", "mm^(2)", "mm2", "sq mm", "square millimetres", "square millimeters"),
    "cm^2": ("cm^2", "cm^(2)", "cm2", "sq cm", "square cm", "square centimetres", "square centimeters", "cm squared"),
    "m^2": ("m^2", "m^(2)", "m2", "sq m", "square m", "square metres", "square meters", "metres squared", "meters squared", "m squared"),
    "km^2": ("km^2", "km^(2)", "km2", "sq km", "square kilometres", "square kilometers"),
    "cm^3": ("cm^3", "cm^(3)", "cm3", "cubic cm", "cubic centimetres", "cubic centimeters", "cc"),
    "m^3": ("m^3", "m^(3)", "m3", "cubic metres", "cubic meters"),
    "m/s^2": ("m/s^2", "m/s^(2)", "ms^-2", "ms^(-2)", "m s^-2", "m s^(-2)", "m/s/s", "m/sec^2", "metres per second squared",
              "meters per second squared", "metres per second per second", "meters per second per second"),
    "m/s": ("m/s", "ms^-1", "ms^(-1)", "m s^-1", "m s^(-1)", "m/sec", "metres per second", "meters per second", "mps"),
    "cm/s": ("cm/s", "cms^-1", "cm s^-1", "cm/sec", "centimetres per second", "centimeters per second"),
    "km/h": ("km/h", "km/hr", "kmh", "kph", "km h^-1", "kilometres per hour", "kilometers per hour"),
    "cm^3/s": ("cm^3/s", "cm^(3)/s", "cm3/s", "cubic centimetres per second", "cm^3 s^-1"),
    "m^3/s": ("m^3/s", "m^(3)/s", "m3/s", "m^3 s^-1"),
    "L/min": ("L/min", "l/min", "litres per minute", "liters per minute"),
    "mm": ("mm", "millimetres", "millimeters", "millimetre", "millimeter"),
    "cm": ("cm", "centimetres", "centimeters", "centimetre", "centimeter"),
    "km": ("km", "kilometres", "kilometers", "kilometre", "kilometer"),
    "m": ("m", "metres", "meters", "metre", "meter"),
    "kg": ("kg", "kilograms", "kilogram"),
    "g": ("g", "grams", "gram"),
    "mL": ("ml", "millilitres", "milliliters"),
    "L": ("l", "litres", "liters", "litre", "liter"),
    "s": ("s", "sec", "secs", "second", "seconds"),
    "min": ("min", "mins", "minute", "minutes"),
    "h": ("h", "hr", "hrs", "hour", "hours"),
    "days": ("days", "day"),
    "years": ("years", "year", "yrs", "yr"),
    "months": ("months", "month"),
    "$": ("$", "dollars", "dollar", "aud"),
    "%": ("%", "percent", "per cent", "pc"),
    "°": ("°", "degrees", "degree", "deg"),
    "units": ("units", "unit", "u"),
    "people": ("people", "persons"),
    "seats": ("seats",),
}
_ALIAS_TO_UNIT = sorted(((a.lower(), u) for u, als in UNIT_ALIASES.items() for a in als), key=lambda p: len(p[0]), reverse=True)


def canonical_unit(u: str | None) -> str | None:
    if not u:
        return None
    low = re.sub(r"\s+", " ", u.strip().lower())
    for alias, unit in _ALIAS_TO_UNIT:
        if low == alias:
            return unit
    return u.strip()


def split_units(s: str) -> tuple[str, str | None]:
    """'225 cm^2' -> ('225', 'cm^2'); '$1,234.57' -> ('1,234.57', '$'). Only a trailing/leading unit is removed."""
    s = s.strip()
    unit = None
    m = re.match(r"(?i)(aud|a\$)\s*", s)
    if m:
        unit, s = "$", s[m.end():]
    if s.startswith("$") or s.startswith("-$"):
        unit = "$"
        s = s.replace("$", "", 1).strip()
    low = s.lower()
    for alias, u in _ALIAS_TO_UNIT:
        if low.endswith(alias):
            head = s[: len(s) - len(alias)]
            if not head.strip():
                continue
            prev = head[-1]
            # the unit must be separated from the number (space, digit or closing bracket) and not part of a word
            if alias[0].isalpha() and not (prev.isspace() or prev.isdigit() or prev in ")."):
                continue
            if alias in ("e", "x", "n", "t", "k"):
                continue
            unit = unit or u
            s = head.strip()
            break
    if s.endswith("$"):
        unit = unit or "$"
        s = s[:-1].strip()
    return s, unit


def strip_units(s: str) -> str:
    return split_units(s)[0]


def strip_lhs(s: str) -> str:
    """'y = 3x+1', "f'(x) = ...", 'x = 4' -> the right-hand side."""
    if "=" in s and "<=" not in s and ">=" not in s:
        return s.split("=")[-1].strip()
    return s


# ------------------------------------------------------------- reading -----
def _clean_number_text(s: str) -> str:
    """Thousands separators and mixed numbers in a lone number: '1,234.5' '12 345' '1 1/2'."""
    t = s.strip()
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
        return t.replace(",", "")
    if re.fullmatch(r"-?\d{1,3}( \d{3})+(\.\d+)?", t):
        return t.replace(" ", "")
    m = re.fullmatch(r"(-?)(\d+) (\d+)/(\d+)", t)
    if m and int(m.group(3)) < int(m.group(4)):
        sign, whole, num, den = m.groups()
        return f"{sign}({whole} + {num}/{den})"
    return t


@dataclass
class Reading:
    ast: tuple
    text: str
    unit: str | None = None


def read_value(raw: str, allowed_vars=DEFAULT_VARS, with_units: bool = True, numeric: bool = True) -> Reading:
    s = normalise(raw)
    s = strip_lhs(s)
    unit = None
    if with_units:
        s, unit = split_units(s)
    if numeric:
        s = _clean_number_text(s)
        m = re.fullmatch(r"(?i)(?:the\s+)?(\d+)(?:st|nd|rd|th)(?:\s+term)?", s.strip())
        if m:
            s = m.group(1)
    s = s.replace("$", "")
    if not s:
        raise ParseError("empty answer")
    if len(s) > MAX_CHARS:
        raise ParseError("That answer is too long to read. Give just the final answer.")
    return Reading(parse_ast(s, allowed_vars, normalised=True), s, unit)


def _stored(value: str, allowed_vars=DEFAULT_VARS) -> tuple:
    """Parse a stored (trusted) answer string with the same safe parser."""
    return parse_ast(str(value).replace("**", "^"), tuple(allowed_vars) + tuple(v for v in DEFAULT_VARS if v not in allowed_vars))


def parse(text: str) -> sp.Expr:
    """Compatibility helper: the student's answer as a SymPy expression (built from the guarded AST)."""
    return to_sympy(read_value(text).ast)


# ------------------------------------------------------------ comparison ---
_POINTS = (0.37, 1.13, 2.71, -0.83, 3.3, 0.61, 1.9, -2.2, 4.4, 5.7, 7.3, 9.1, 12.4, -4.6, -7.9)


def _mpctx() -> mpmath.MPContext:
    ctx = mpmath.MPContext()
    ctx.dps = 40
    return ctx


def _const_value(ast) -> complex | None:
    try:
        return evaluate(ast)
    except (ZeroDivisionError, OverflowError, ValueError):
        return None


def _exact_equal(a, b) -> bool:
    """Equality of two constant ASTs to 40 significant digits (decimals are exact rationals)."""
    ctx = _mpctx()
    try:
        va, vb = evaluate_mp(a, ctx), evaluate_mp(b, ctx)
        diff = abs(va - vb)
        return bool(diff <= ctx.mpf(10) ** -30 * max(1, abs(vb)))
    except (ZeroDivisionError, OverflowError, ValueError, TypeError):
        return False


def _close(va: complex, vb: complex, rel: float = 1e-9) -> bool:
    return abs(va - vb) <= rel * max(1.0, abs(vb))


def _sample_envs(names: list[str]) -> list[dict[str, complex]]:
    return [{v: complex(p + 0.17 * i) for i, v in enumerate(names)} for p in _POINTS]


def _fn_equal(a, b, names: list[str]) -> bool:
    """Equal as functions: agree at every sample point where the correct one is defined and real."""
    compared = 0
    for env in _sample_envs(names):
        try:
            vb = evaluate(b, env)
        except (ZeroDivisionError, OverflowError, ValueError):
            continue
        if abs(vb.imag) > 1e-12 * max(1.0, abs(vb)):
            continue
        try:
            va = evaluate(a, env)
        except (ZeroDivisionError, OverflowError, ValueError):
            return False
        if abs(va.imag) > 1e-9 * max(1.0, abs(va)):
            continue  # e.g. ln(x) vs ln|x| at a negative point: compare only where both are real
        if not _close(va, vb):
            return False
        compared += 1
    return compared >= 3


def _differ_by_constant(a, b, names: list[str]) -> bool:
    diffs = []
    for env in _sample_envs(names):
        try:
            va, vb = evaluate(a, env), evaluate(b, env)
        except (ZeroDivisionError, OverflowError, ValueError):
            continue
        if abs(va.imag) > 1e-9 * max(1.0, abs(va)) or abs(vb.imag) > 1e-9 * max(1.0, abs(vb)):
            continue
        diffs.append(va - vb)
    if len(diffs) < 3:
        return False
    return all(_close(d, diffs[0], 1e-8) for d in diffs)


def _ratio_constant(a, b, names: list[str]) -> complex | None:
    ratios = []
    for env in _sample_envs(names):
        try:
            va, vb = evaluate(a, env), evaluate(b, env)
        except (ZeroDivisionError, OverflowError, ValueError):
            continue
        if abs(vb) < 1e-12:
            continue
        ratios.append(va / vb)
    if len(ratios) >= 3 and all(_close(r, ratios[0], 1e-8) for r in ratios):
        return ratios[0]
    return None


def same(student, correct, names: list[str] | None = None) -> bool:
    names = sorted(free_vars(student) | free_vars(correct)) if names is None else names
    if not free_vars(student) and not free_vars(correct):
        return _exact_equal(student, correct)
    return _fn_equal(student, correct, sorted(set(names) | free_vars(student) | free_vars(correct)))


def _round_half_up(value: complex, dp: int) -> Decimal:
    q = Decimal(1).scaleb(-dp)
    return Decimal(repr(float(value.real))).quantize(q, rounding=ROUND_HALF_UP)


def _exact_rounded(ast, dp: int) -> Decimal:
    ctx = _mpctx()
    v = evaluate_mp(ast, ctx)
    q = Decimal(1).scaleb(-dp)
    return Decimal(ctx.nstr(ctx.re(v), 30, min_fixed=-10**6, max_fixed=10**6)).quantize(q, rounding=ROUND_HALF_UP)


def _terminating(ast) -> bool:
    """Is the stored exact value a terminating decimal (so a decimal answer can be exact)?"""
    try:
        e = to_sympy(ast)
        if e.is_Rational:
            d = int(e.q)
            for p in (2, 5):
                while d % p == 0:
                    d //= p
            return d == 1
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- result ---
@dataclass
class MathsResult:
    correct: bool
    mark: float
    possible: float
    category: str | None = None  # spec 5C category when not correct
    diagnosis: str | None = None
    student_display: str = ""
    notes: list[str] = field(default_factory=list)
    parsed: bool = True
    topic_tag: str | None = None  # spec 23 tag
    step: int | None = None  # worked-solution step where the error happens (from a common error)
    latex: str | None = None  # how the answer was read, as LaTeX
    parts: list[dict] = field(default_factory=list)  # multi-part: one dict per part
    common_error: bool = False  # matched a documented common error

    def as_dict(self) -> dict:
        return {"correct": self.correct, "mark": self.mark, "possible": self.possible, "category": self.category,
                "topic_tag": self.topic_tag, "diagnosis": self.diagnosis, "student": self.student_display, "latex": self.latex,
                "notes": list(self.notes), "parsed": self.parsed, "step": self.step}


UNREADABLE = ("I could not read this as a mathematical answer. Type it in plain calculator style, e.g. 3x^2 - 2, "
              "sqrt(2)/2, e^(2x), 2pi/3, ln(5).")


def _unreadable(marks: float, resp: str, why: str | None = None) -> MathsResult:
    diag = UNREADABLE + (f" ({why})" if why and why != "empty answer" else "")
    return MathsResult(False, 0, marks, "notation", diag, resp[:200], parsed=False, topic_tag="notation")


def _vars_for(answer: dict) -> tuple[str, ...]:
    vs = list(answer.get("vars") or [])
    if answer.get("var"):
        vs.append(answer["var"])
    return tuple(dict.fromkeys(vs + list(DEFAULT_VARS)))


def _match_common_errors(student, common_errors, answer: dict, part: str | None = None) -> dict | None:
    names = list(_vars_for(answer))
    for ce in common_errors or []:
        if (ce.get("part") or None) != part:
            continue
        try:
            target = ce["answer"]
            if "," in str(target) and answer.get("type") != "set":
                continue
            t_ast = _stored(target, names)
            if answer.get("type") == "antiderivative":
                if _differ_by_constant(student, t_ast, names):
                    return ce
                continue
            if "dp" in answer and not free_vars(student) and not free_vars(t_ast):
                dp = int(answer["dp"])
                sv, tv = _const_value(student), _const_value(t_ast)
                if sv is not None and tv is not None and (_round_half_up(sv, dp) == _round_half_up(tv, dp) or abs(sv - tv) <= 10 ** -dp / 2):
                    return ce
                continue
            if same(student, t_ast, names):
                return ce
            tol = float(answer.get("tol") or 0)
            if tol and not free_vars(student) and not free_vars(t_ast):
                sv, tv = _const_value(student), _const_value(t_ast)
                if sv is not None and tv is not None and abs(sv - tv) <= tol:
                    return ce
        except (ParseError, KeyError, TypeError, ValueError):
            continue
    return None


def _heuristic(student, correct, kind: str, names: list[str]) -> tuple[str, str | None, str]:
    """Category, topic tag and diagnosis for a wrong answer that matches no documented error."""
    try:
        if not free_vars(student) and not free_vars(correct):
            sv, cv = _const_value(student), _const_value(correct)
            if sv is not None and cv is not None:
                if abs(cv) > 1e-12 and _close(sv, -cv):
                    return "careless error", "sign error", "Your answer has the right size but the wrong sign: track each negative carefully."
                if abs(cv) > 1e-12 and abs(sv - cv) / abs(cv) < 0.02:
                    return "arithmetic", None, "You are very close to the correct value, which suggests an arithmetic or rounding slip rather than a wrong method."
                if abs(cv) > 1e-12:
                    r = sv / cv
                    for f, word in ((2, "twice"), (0.5, "half"), (-2, "minus twice"), (-0.5, "minus half")):
                        if _close(r, complex(f), 1e-9):
                            return "arithmetic", None, f"Your answer is {word} the correct value: check a halving or doubling step (for example a factor of \\(\\frac{{1}}{{2}}\\), \\(\\frac{{n}}{{2}}\\) or a coefficient)."
                    if _close(r, complex(10), 1e-9) or _close(r, complex(0.1), 1e-9) or _close(r, complex(100), 1e-9) or _close(r, complex(0.01), 1e-9):
                        return "careless error", "calculator error", "Your answer is out by a power of ten: check the decimal point or a percentage conversion."
        else:
            if _fn_equal(student, ("neg", correct), names):
                return "careless error", "sign error", "Your expression is the negative of the correct one: a sign changed somewhere."
            ratio = _ratio_constant(student, correct, names)
            if ratio is not None and abs(ratio.imag) < 1e-9:
                k = ratio.real
                frac = Fraction(k).limit_denominator(100)
                shown = f"{frac.numerator}/{frac.denominator}" if frac.denominator != 1 else str(frac.numerator)
                return "algebraic", "algebra", f"Your expression is {shown} times the correct one: a constant factor (for example a chain-rule factor or a coefficient) is wrong."
            if kind != "antiderivative" and _differ_by_constant(student, correct, names):
                return "arithmetic", None, "Your expression differs from the correct one by a constant: check the constant term."
    except Exception:
        pass
    return "conceptual", None, "Your answer does not match a simple slip; compare your method with the worked solution step by step."


def _unit_check(res: MathsResult, given: str | None, answer: dict, marks: float) -> MathsResult:
    want = canonical_unit(answer.get("units"))
    if not want or not res.correct and res.mark == 0:
        return res
    got = canonical_unit(given)
    if got is None:
        if want not in ("units", "%"):
            res.notes.append(f"Include the units ({_unit_label(want)}) with your final answer.")
        return res
    if got == want:
        return res
    if want == "%" or got == "%":
        if got != want:
            res.notes.append(f"The answer is in {_unit_label(want)}, not {_unit_label(got)}.")
        return res
    # a different unit: the number means something else
    res.correct = False
    res.mark = max(0.0, res.mark - 1) if marks >= 2 else 0.0
    res.category, res.topic_tag = "notation", "units"
    res.diagnosis = f"The number is right but the units are not: the answer is in {_unit_label(want)}, you wrote {_unit_label(got)}."
    return res


def _unit_label(u: str) -> str:
    return {"units^2": "square units", "units^3": "cubic units", "$": "dollars", "%": "%"}.get(u, u)


# ------------------------------------------------------------------ MCQ ----
def mcq_letter(resp: str, options: list[str] | None = None) -> str:
    """Read the chosen option: 'B', '(B)', 'B.', 'Answer: B', 'the answer is c', or an option's text/yes/no."""
    s = (resp or "").strip()
    if not s:
        return ""
    m = re.fullmatch(r"[\s(\[]*([A-Da-d])[\s.):\]]*", s)
    if m:
        return m.group(1).upper()
    cleaned = re.sub(r"(?i)\b(?:my\s+)?(?:final\s+)?(?:answer|option|choice)\s*(?:is|:|=)?\s*", " ", s)
    cleaned = re.sub(r"(?i)\b(?:the|i\s+think|it\s+is|it's|is)\b", " ", cleaned)
    m = re.fullmatch(r"[\s(\[]*([A-Da-d])[\s.):\]]*", cleaned)
    if m:
        return m.group(1).upper()
    upper = set(re.findall(r"(?<![A-Za-z])([A-D])(?![A-Za-z])", s))
    if len(upper) == 1:
        return upper.pop()
    if options:
        low = s.lower().strip(" .")
        for opt in options:
            om = re.match(r"\s*\(?([A-Da-d])[.)]\s*(.*)", opt)
            if not om:
                continue
            letter, text = om.group(1).upper(), om.group(2).strip().lower().rstrip(".")
            first = text.split()[0].strip(",.") if text.split() else ""
            if low == text or (low in ("yes", "no", "true", "false") and first == low):
                return letter
    lower = set(re.findall(r"(?<![A-Za-z])([a-d])(?![A-Za-z])", s))
    if len(lower) == 1 and not upper:
        return lower.pop().upper()
    return ""


# ------------------------------------------------------------- intervals ---
@dataclass
class Iv:
    lo: tuple | None  # AST or None for -oo
    hi: tuple | None  # AST or None for +oo
    lo_closed: bool
    hi_closed: bool


_INF = {"oo", "inf", "infinity", "+oo", "+inf", "+infinity"}


def _end(text: str, allowed) -> tuple | None | str:
    t = text.strip().lower().replace(" ", "")
    if t in _INF:
        return "+inf"
    if t in {"-" + i.lstrip("+") for i in _INF}:
        return "-inf"
    ast = parse_ast(text, allowed, normalised=True)
    if free_vars(ast):
        raise ParseError("An interval end should be a number.")
    return ast


def _ival(v) -> float:
    if v == "-inf":
        return -math.inf
    if v == "+inf":
        return math.inf
    c = _const_value(v)
    if c is None:
        raise ParseError("That interval end can't be evaluated.")
    return c.real


def _parse_piece(piece: str, var: str, allowed) -> Iv:
    p = piece.strip()
    p = re.sub(rf"^\s*{var}\s+in\s+", "", p)
    m = re.fullmatch(r"([\[(])\s*([^,]+?)\s*,\s*([^,]+?)\s*([\])])", p)
    if m:
        lo, hi = _end(m.group(2), allowed), _end(m.group(3), allowed)
        if lo == "+inf" or hi == "-inf":
            raise ParseError("Write intervals from left to right, e.g. (-2, 3).")
        return Iv(None if lo == "-inf" else lo, None if hi == "+inf" else hi, m.group(1) == "[" and lo != "-inf", m.group(4) == "]" and hi != "+inf")
    p = p.replace("=<", "<=").replace("=>", ">=")
    parts = re.split(r"(<=|>=|<|>)", p)
    parts = [x.strip() for x in parts]
    if len(parts) == 3:
        left, op, right = parts
        if left == var:
            end = _end(right, allowed)
            if op in ("<", "<="):
                return Iv(None, None if end == "+inf" else end, False, op == "<=")
            return Iv(None if end == "-inf" else end, None, op == ">=", False)
        if right == var:
            end = _end(left, allowed)
            if op in ("<", "<="):  # a < x
                return Iv(None if end == "-inf" else end, None, op == "<=", False)
            return Iv(None, None if end == "+inf" else end, False, op == ">=")
    if len(parts) == 5 and parts[2] == var:
        a, op1, _, op2, b = parts
        ea, eb = _end(a, allowed), _end(b, allowed)
        if op1 in ("<", "<=") and op2 in ("<", "<="):
            return Iv(None if ea == "-inf" else ea, None if eb == "+inf" else eb, op1 == "<=", op2 == "<=")
        if op1 in (">", ">=") and op2 in (">", ">="):
            return Iv(None if eb == "-inf" else eb, None if ea == "+inf" else ea, op2 == ">=", op1 == ">=")
    raise ParseError(f"Write the region as an inequality such as -2 < {var} < 3, {var} <= 1 or {var} > 4, or as an interval such as (-2, 3).")


def parse_region(text: str, var: str = "x", allowed=DEFAULT_VARS) -> list[Iv]:
    s = normalise(text)
    if len(s) > MAX_CHARS:
        raise ParseError("That answer is too long to read.")
    s = re.sub(r"([\])])\s*[Uu]\s*([\[(])", r"\1 U \2", s)
    low = s.lower()
    if re.fullmatch(r"(all real (numbers|values|x)|all x|r|\(-oo,\s*oo\))", low.strip()):
        return [Iv(None, None, False, False)]
    # split into pieces: 'or', 'U', ';' and commas that are not inside brackets
    pieces, depth, cur = [], 0, ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and (ch in ",;" or s[i:i + 3] == " U " or s[i:i + 4].lower() == " or "):
            pieces.append(cur)
            cur = ""
            i += 4 if s[i:i + 4].lower() == " or " else (3 if s[i:i + 3] == " U " else 1)
            continue
        cur += ch
        i += 1
    pieces.append(cur)
    pieces = [p for p in (p.strip() for p in pieces) if p]
    if not pieces:
        raise ParseError("empty answer")
    return [_parse_piece(p, var, allowed) for p in pieces[:8]]


def _merge(ivs: list[Iv]) -> list[Iv]:
    keyed = sorted(ivs, key=lambda v: (_ival(v.lo) if v.lo is not None else -math.inf))
    out: list[Iv] = []
    for v in keyed:
        if out:
            last = out[-1]
            lh = _ival(last.hi) if last.hi is not None else math.inf
            vl = _ival(v.lo) if v.lo is not None else -math.inf
            if vl < lh or (vl == lh and (last.hi_closed or v.lo_closed)):
                vh = _ival(v.hi) if v.hi is not None else math.inf
                if vh > lh or (vh == lh and v.hi_closed):
                    last.hi, last.hi_closed = v.hi, v.hi_closed
                continue
        out.append(Iv(v.lo, v.hi, v.lo_closed, v.hi_closed))
    return out


def _end_equal(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return _exact_equal(a, b) or _close(complex(_ival(a)), complex(_ival(b)), 1e-12)


def _region_text(ivs: list[Iv], var: str) -> str:
    out = []
    for v in ivs:
        lo = to_text(v.lo) if v.lo is not None else None
        hi = to_text(v.hi) if v.hi is not None else None
        if lo is None and hi is None:
            out.append(f"all real {var}")
        elif lo is None:
            out.append(f"{var} {'<=' if v.hi_closed else '<'} {hi}")
        elif hi is None:
            out.append(f"{var} {'>=' if v.lo_closed else '>'} {lo}")
        else:
            out.append(f"{lo} {'<=' if v.lo_closed else '<'} {var} {'<=' if v.hi_closed else '<'} {hi}")
    return " or ".join(out)


def region_latex(ivs: list[Iv], var: str) -> str:
    out = []
    le_sym, ge_sym, reals = "\\le", "\\ge", "\\in \\mathbb{R}"
    for v in ivs:
        lo = to_latex(v.lo) if v.lo is not None else None
        hi = to_latex(v.hi) if v.hi is not None else None
        if lo is None and hi is None:
            out.append(f"{var} {reals}")
        elif lo is None:
            out.append(f"{var} {le_sym if v.hi_closed else '<'} {hi}")
        elif hi is None:
            out.append(f"{var} {ge_sym if v.lo_closed else '>'} {lo}")
        else:
            out.append(f"{lo} {le_sym if v.lo_closed else '<'} {var} {le_sym if v.hi_closed else '<'} {hi}")
    return " \\text{ or } ".join(out)


def stored_region(answer: dict) -> list[Iv]:
    var = answer.get("var", "x")
    out = []
    for lo, hi, lc, hc in answer["intervals"]:
        lo_ast = None if str(lo) in ("-oo", "-inf") else _stored(lo, [var])
        hi_ast = None if str(hi) in ("oo", "+oo", "inf") else _stored(hi, [var])
        out.append(Iv(lo_ast, hi_ast, bool(lc) and lo_ast is not None, bool(hc) and hi_ast is not None))
    return _merge(out)


def _same_region(a: list[Iv], b: list[Iv], ends_matter: bool) -> bool:
    if len(a) != len(b) or not all(_end_equal(g.lo, w.lo) and _end_equal(g.hi, w.hi) for g, w in zip(a, b)):
        return False
    return not ends_matter or all(g.lo_closed == w.lo_closed and g.hi_closed == w.hi_closed for g, w in zip(a, b))


def _interval_common_error(got: list[Iv], answer: dict, common_errors, marks: float, shown: str, latex: str) -> MathsResult | None:
    var = answer.get("var", "x")
    for ce in common_errors or []:
        try:
            region = _merge(parse_region(str(ce["answer"]), var, _vars_for(answer)))
        except (ParseError, KeyError, TypeError, ValueError):
            continue
        if _same_region(got, region, answer.get("ends", "matter") != "ignore"):
            cm = min(float(ce.get("marks", 0) or 0), max(0.0, marks - 1))
            return MathsResult(False, cm, marks, ce.get("category") or "conceptual", ce.get("diagnosis"), shown,
                               topic_tag=ce.get("topic_tag"), step=ce.get("step"), latex=latex, common_error=True)
    return None


def _mark_interval(resp: str, answer: dict, marks: float, common_errors=None) -> MathsResult:
    var = answer.get("var", "x")
    allowed = _vars_for(answer)
    want = stored_region(answer)
    ends_matter = answer.get("ends", "matter") != "ignore"
    try:
        got = _merge(parse_region(resp, var, allowed))
    except ParseError as exc:
        # a bare list of endpoints ('-1, 3') says where the boundaries are but not which side
        try:
            vals = [read_value(p, allowed).ast for p in re.split(r"\s*[,;]\s*", normalise(resp)) if p.strip()]
            ends = [e for iv in want for e in (iv.lo, iv.hi) if e is not None]
            if vals and len(vals) == len(ends) and all(any(same(v, e) for e in ends) for v in vals):
                return MathsResult(False, max(0.0, marks - 1) if marks >= 2 else 0.0, marks, "incomplete reasoning",
                                   f"Your endpoints are right, but you did not say which region: write it as an inequality, e.g. {_region_text(want, var)}.",
                                   resp[:200], topic_tag="inequality direction")
        except (ParseError, Exception):
            pass
        return _unreadable(marks, resp, str(exc))
    shown, latex = _region_text(got, var), region_latex(got, var)
    if len(got) == len(want) and all(_end_equal(g.lo, w.lo) and _end_equal(g.hi, w.hi) for g, w in zip(got, want)):
        closed_ok = all(g.lo_closed == w.lo_closed and g.hi_closed == w.hi_closed for g, w in zip(got, want))
        if closed_ok or not ends_matter:
            return MathsResult(True, marks, marks, student_display=shown, latex=latex)
        return MathsResult(False, max(0.0, marks - 1), marks, "notation",
                           "The region is right but an endpoint is wrongly included or excluded: check < versus ≤.", shown,
                           topic_tag="inequality direction", latex=latex)
    ce = _interval_common_error(got, answer, common_errors, marks, shown, latex)
    if ce is not None:
        return ce
    g_ends = [e for iv in got for e in (iv.lo, iv.hi) if e is not None]
    w_ends = [e for iv in want for e in (iv.lo, iv.hi) if e is not None]
    if g_ends and len(g_ends) == len(w_ends) and all(any(_end_equal(a, b) for b in w_ends) for a in g_ends):
        return MathsResult(False, 0, marks, "interpretation",
                           "Your boundary values are right but you described the wrong region (the other side of them): "
                           "test a value in each region to decide where the inequality holds.", shown, topic_tag="inequality direction", latex=latex)
    return MathsResult(False, 0, marks, "conceptual", "Your region's boundaries do not match: find where the expression equals zero first, then test each region.",
                       shown, latex=latex)


# ----------------------------------------------------------------- parts ---
_LABEL_RE = re.compile(r"(?:^|\n|;)\s*\(\s*([a-h]|i{1,3}|iv|v|vi)\s*\)\s*|(?:^|\n)\s*([a-h])\s*[).:]\s+", re.I)


def split_parts(resp: str, labels: list[str]) -> dict[str, str]:
    """'(a) 3\\n(b) x^2' -> {'a': '3', 'b': 'x^2'}; unlabelled lines are taken in order."""
    text = (resp or "").strip()
    found = list(_LABEL_RE.finditer(text))
    out: dict[str, str] = {}
    if found:
        for i, m in enumerate(found):
            lab = (m.group(1) or m.group(2)).lower()
            end = found[i + 1].start() if i + 1 < len(found) else len(text)
            if lab in labels and lab not in out:
                out[lab] = text[m.end():end].strip().strip(";").strip()
        if out:
            return out
    lines = [ln.strip() for ln in re.split(r"\n|;", text) if ln.strip()]
    if len(lines) == len(labels):
        return dict(zip(labels, lines))
    if len(labels) == 1:
        return {labels[0]: text}
    return out


def _mark_parts(resp: str, answer: dict, marks: float, common_errors, options) -> MathsResult:
    parts = answer.get("parts") or []
    labels = [p["label"] for p in parts]
    given = split_parts(resp, labels)
    total, results, first_bad = 0.0, [], None
    notes: list[str] = []
    for p in parts:
        lab = p["label"]
        sub = given.get(lab, "")
        r = mark_answer(sub, p["answer"], p.get("marks", 1), [dict(ce, part=None) for ce in common_errors or [] if ce.get("part") == lab],
                        options=p.get("options"))
        total += r.mark
        d = r.as_dict()
        d.update(label=lab, given=sub, answered=bool(sub.strip()))
        results.append(d)
        notes.extend(f"({lab}) {n}" for n in r.notes)
        if not r.correct and first_bad is None:
            first_bad = (lab, r)
    ok = all(d["correct"] for d in results)
    shown = "; ".join(f"({d['label']}) {d['student'] or '—'}" for d in results)
    if ok:
        return MathsResult(True, marks, marks, student_display=shown, notes=notes, parts=results)
    lab, r = first_bad
    diag = f"Part ({lab}): {r.diagnosis}" if r.diagnosis else f"Part ({lab}) is not right."
    res = MathsResult(False, min(total, marks), marks, r.category, diag, shown, notes, parsed=all(d["parsed"] or not d["answered"] for d in results),
                      topic_tag=r.topic_tag, step=r.step, parts=results)
    res.common_error = r.common_error
    return res


# ------------------------------------------------------------------ main ---
def mark_answer(response: str, answer: dict, marks: int, common_errors: list[dict] | None = None, options: list[str] | None = None) -> MathsResult:
    """Mark a typed answer against an answer spec. Never raises."""
    try:
        return _mark(response, answer or {}, marks, common_errors or [], options)
    except Exception as exc:  # pragma: no cover - defence in depth: a crafted answer must never 500
        return _unreadable(marks, str(response or "")[:200], type(exc).__name__)


def _mark(response: str, answer: dict, marks: int, common_errors: list[dict], options) -> MathsResult:
    kind = answer.get("type", "num")
    resp = (response or "").strip()
    if len(resp) > MAX_RESPONSE_CHARS:
        return _unreadable(marks, resp[:200], "too long")
    if not resp:
        return MathsResult(False, 0, marks, "incomplete reasoning", "No answer was given.", parsed=False)

    if kind == "mcq":
        letter = mcq_letter(resp, options or answer.get("options"))
        ok = letter == str(answer.get("value", "")).upper()
        if not letter:
            return MathsResult(False, 0, marks, "notation", "Give the letter of one option (A, B, C or D).", resp[:60], parsed=False)
        if not ok:
            ce = next((c for c in common_errors if str(c.get("answer", "")).strip().upper() == letter), None)
            if ce:
                return MathsResult(False, 0, marks, ce.get("category") or "conceptual", ce.get("diagnosis"), letter,
                                   topic_tag=ce.get("topic_tag"), step=ce.get("step"), common_error=True)
        return MathsResult(ok, marks if ok else 0, marks, None if ok else "conceptual", None, letter)

    if kind == "parts":
        return _mark_parts(resp, answer, marks, common_errors, options)

    if kind == "interval":
        return _mark_interval(resp, answer, marks, common_errors)

    allowed = _vars_for(answer)
    names = list(allowed)

    if kind == "set" and re.search(r"[<>]|≤|≥|\\le|\\ge", resp):
        try:
            region = _merge(parse_region(resp, "x", allowed))
        except ParseError as exc:
            return _unreadable(marks, resp, str(exc))
        if len(region) == 1 and region[0].lo is not None and region[0].hi is not None:
            resp = f"{to_text(region[0].lo)}, {to_text(region[0].hi)}"
        else:
            return MathsResult(False, 0, marks, "interpretation", "That region is not a single interval between two values: check which side of the boundaries the condition holds.",
                               _region_text(region, "x"), topic_tag="inequality direction", latex=region_latex(region, "x"))

    if kind == "set":
        bare = re.sub(r"^[\s(\[{]+|[\s)\]}]+$", "", normalise(resp))
        parts = [p for p in re.split(r"\s*(?:,|;|\bor\b|\band\b)\s*", bare) if p.strip()][:12]
        try:
            got = [read_value(p, allowed, numeric=False).ast for p in parts]
        except ParseError as exc:
            return MathsResult(False, 0, marks, "notation", f"I could not read one of the values ({exc}). Enter them separated by commas, e.g. 2, -3.",
                               resp[:200], parsed=False, topic_tag="notation")
        want = [_stored(v, names) for v in answer["values"]]
        if answer.get("ordered"):
            matched = sum(1 for g, w in zip(got, want) if same(g, w, names))
        else:
            remaining = list(want)
            matched = 0
            for g in got:
                for w in remaining:
                    if same(g, w, names):
                        remaining.remove(w)
                        matched += 1
                        break
        extra = max(0, len(got) - len(want))
        ok = matched == len(want) and extra == 0
        mark = marks if ok else math.floor(marks * max(0, matched - extra) / max(1, len(want)))
        shown = ", ".join(to_text(g) for g in got)
        latex = ", ".join(to_latex(g) for g in got)
        if ok:
            return MathsResult(True, mark, marks, student_display=shown, latex=latex)
        ce = None
        joined = ", ".join(to_text(g) for g in got)
        for c in common_errors:
            try:
                vals = [_stored(v.strip(), names) for v in str(c["answer"]).split(",")]
                if len(vals) != len(got):
                    continue
                if answer.get("ordered"):
                    hit = all(same(g, v, names) for g, v in zip(got, vals))
                else:
                    left = list(vals)
                    for g in got:
                        j = next((i for i, v in enumerate(left) if same(g, v, names)), None)
                        if j is None:
                            break
                        left.pop(j)
                    hit = not left
                if hit:
                    ce = c
                    break
            except (ParseError, KeyError):
                continue
        if ce:
            return MathsResult(False, max(mark, float(ce.get("marks", 0))), marks, ce["category"], ce["diagnosis"], joined,
                               topic_tag=ce.get("topic_tag"), step=ce.get("step"), latex=latex, common_error=True)
        cat = "incomplete reasoning" if matched and len(got) < len(want) else ("interpretation" if extra else "conceptual")
        diag = f"{matched} of {len(want)} required values correct" + (f"; {extra} extra value(s) given" if extra else "") + "."
        if cat == "interpretation":
            diag += " Check each solution against any restriction in the question (domain, x > 0, 0 ≤ x ≤ 2π)."
        return MathsResult(False, mark, marks, cat, diag, joined, topic_tag="domain/range" if extra else None, latex=latex)

    # ---- single value / expression / primitive ----
    has_c = False
    text = resp
    if kind == "antiderivative":
        has_c = bool(re.search(r"\+\s*[cCK]\b(?!\s*[\^(*/])", text) or re.match(r"\s*[cCK]\s*\+", text))
        text = re.sub(r"\+\s*[cCK]\b(?!\s*[\^(*/])", "", text)
        text = re.sub(r"^\s*[cCK]\s*\+", "", text)
    try:
        reading = read_value(text, allowed, with_units=kind == "num", numeric=kind == "num")
    except ParseError as exc:
        return _unreadable(marks, resp, str(exc))
    student = reading.ast
    display, latex = to_text(student), to_latex(student)
    correct = _stored(answer["value"], names)
    notes: list[str] = []

    def done(res: MathsResult) -> MathsResult:
        res.latex = latex
        if kind == "num":
            res = _unit_check(res, reading.unit, answer, marks)
        return res

    if kind == "antiderivative":
        if _differ_by_constant(student, correct, names) or (_fn_equal(student, correct, names)):
            if not has_c:
                notes.append("Remember '+ C' for an indefinite integral.")
            return done(MathsResult(True, marks, marks, None, None, display, notes))
    elif kind == "expr":
        if same(student, correct, names):
            return done(MathsResult(True, marks, marks, None, None, display, notes))
    else:  # num
        if free_vars(student):
            v = ", ".join(sorted(free_vars(student)))
            return done(MathsResult(False, 0, marks, "incomplete reasoning",
                                    f"Your answer still contains {v}; the question asks for a number, so substitute and simplify.",
                                    display, notes, topic_tag="algebra"))
        sv = _const_value(student)
        cv = _const_value(correct)
        if sv is None:
            return _unreadable(marks, resp, "the value can't be evaluated")
        if "dp" in answer:
            dp = int(answer["dp"])
            target = _exact_rounded(correct, dp)
            got = Decimal(repr(sv.real))
            unit = Decimal(1).scaleb(-dp)
            if abs(sv.imag) < 1e-12 and abs(got - target) <= unit * Decimal("1e-6"):
                return done(MathsResult(True, marks, marks, None, None, display, notes))
            if abs(sv.imag) < 1e-12 and cv is not None and abs(sv.real - cv.real) < float(unit) / 2 * 1.000001:
                # the right value, but not rounded as asked (more decimal places, or an exact form)
                mk = max(0.0, marks - 1) if marks >= 2 else float(marks)
                return done(MathsResult(mk == marks, mk, marks, None if mk == marks else "notation",
                                        f"Your value is right but not rounded as asked: give it to {_dp_words(dp)}, i.e. {target}.",
                                        display, notes if mk != marks else notes + [f"Round as asked: {target}."], topic_tag="rounding"))
            if abs(sv.imag) < 1e-12 and cv is not None and abs(sv.real - cv.real) < float(unit) * 1.5:
                ce = _match_common_errors(student, common_errors, answer)
                if ce is None:
                    mk = max(0.0, marks - 1) if marks >= 2 else 0.0
                    return done(MathsResult(False, mk, marks, "careless error",
                                            f"Your value is rounded incorrectly: to {_dp_words(dp)} the answer is {target} (round half up; don't truncate).",
                                            display, notes, topic_tag="rounding"))
        else:
            tol = float(answer.get("tol", 0) or 0)
            if tol and cv is not None and abs(sv - cv) <= tol + 1e-12:
                return done(MathsResult(True, marks, marks, None, None, display, notes))
            if not tol and _exact_equal(student, correct):
                return done(MathsResult(True, marks, marks, None, None, display, notes))
            if answer.get("units") == "%" and reading.unit != "%" and cv is not None and abs(sv * 100 - cv) <= max(tol, 1e-9 * abs(cv)):
                return MathsResult(False, max(0.0, marks - 1), marks, "notation",
                                   "That is the proportion; the question asks for a percentage (multiply by 100).",
                                   display, notes, topic_tag="units", latex=latex)
            if not tol:
                if cv is not None and not _terminating(correct) and abs(sv - cv) <= 0.005 * max(1.0, abs(cv)) and has_decimal(student):
                    return done(MathsResult(False, max(0, marks - 1), marks, "notation",
                                            "Your decimal value is right, but the question asks for an exact value (fractions, surds, \\(\\pi\\), \\(e\\) or logs).",
                                            display, notes, topic_tag="exact values"))

    ce = _match_common_errors(student, common_errors, answer)
    if ce:
        cm = min(float(ce.get("marks", 0) or 0), max(0.0, marks - 1))
        return done(MathsResult(False, cm, marks, ce.get("category") or "conceptual", ce.get("diagnosis"), display, notes,
                                topic_tag=ce.get("topic_tag"), step=ce.get("step"), common_error=True))
    cat, tag, diag = _heuristic(student, correct, kind, names)
    return done(MathsResult(False, 0, marks, cat, diag, display, notes, topic_tag=tag))


def _dp_words(dp: int) -> str:
    return {0: "the nearest whole number", 1: "1 decimal place", 2: "2 decimal places"}.get(dp, f"{dp} decimal places")


# --------------------------------------------------------------- preview ---
def preview(text: str, kind: str = "expr", labels: list[str] | None = None, var: str = "x") -> dict:
    """LaTeX preview of how an answer will be read, aware of the answer type. Never raises."""
    try:
        raw = (text or "").strip()
        if not raw:
            return {"ok": False, "message": ""}
        if len(raw) > MAX_RESPONSE_CHARS or (kind != "parts" and len(raw) > MAX_CHARS * 2):
            return {"ok": False, "message": "That is too long: give just the final answer."}
        if kind == "mcq":
            letter = mcq_letter(raw)
            return {"ok": bool(letter), "latex": f"\\text{{Option {letter}}}" if letter else "", "message": "" if letter else "Type a letter A–D."}
        if kind == "interval":
            ivs = _merge(parse_region(raw, var))
            return {"ok": True, "latex": region_latex(ivs, var)}
        if kind == "set":
            bare = re.sub(r"^[\s(\[{]+|[\s)\]}]+$", "", normalise(raw))
            vals = [p for p in re.split(r"\s*(?:,|;|\bor\b|\band\b)\s*", bare) if p.strip()][:12]
            return {"ok": True, "latex": ",\\ ".join(to_latex(read_value(v, numeric=False).ast) for v in vals)}
        if kind == "antiderivative":
            had_c = bool(re.search(r"\+\s*[cC]\b", raw))
            ast = read_value(re.sub(r"\+\s*[cC]\b", "", raw), with_units=False, numeric=False).ast
            return {"ok": True, "latex": to_latex(ast) + (" + C" if had_c else "")}
        if kind == "num":
            r = read_value(raw)
            unit = f"\\ \\text{{{_unit_label(r.unit)}}}" if r.unit and r.unit not in ("$",) else ""
            return {"ok": True, "latex": ("\\$" if r.unit == "$" else "") + to_latex(r.ast) + unit}
        ast = read_value(raw, with_units=False, numeric=False).ast
        return {"ok": True, "latex": to_latex(ast)}
    except ParseError as exc:
        return {"ok": False, "message": str(exc) if str(exc) != "empty answer" else ""}
    except Exception:
        return {"ok": False, "message": "Keep typing… (e.g. 3x^2 - 2, sqrt(2)/2, e^(2x), 2pi/3)"}


# Public names for the assessment layer (stored, trusted answer strings only).
stored_ast = _stored
rounded_value = _exact_rounded
unit_label = _unit_label
