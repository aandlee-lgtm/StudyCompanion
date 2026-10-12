"""v2 maths marking: locked-down parser, never-raising marker, units, rounding, MCQ letters,
intervals, multi-part answers and two-axis error tags (audit maths-01..05, 08, 14, 19; adaptive-10)."""
from __future__ import annotations

import time

import pytest

from app.marking import maths as mm
from app.marking.maths_parser import ParseError, parse_ast

NUM6 = {"type": "num", "value": "6"}
EXPR = {"type": "expr", "value": "x^2", "vars": ["x"]}
PRIM = {"type": "antiderivative", "value": "x^3/3", "var": "x"}
SET = {"type": "set", "values": ["1", "2"]}
IV = {"type": "interval", "var": "x", "intervals": [["-2", "3", False, False]]}
MCQ = {"type": "mcq", "value": "B"}
PARTS = {"type": "parts", "parts": [{"label": "a", "marks": 1, "answer": {"type": "num", "value": "2"}},
                                     {"label": "b", "marks": 2, "answer": {"type": "expr", "value": "x", "vars": ["x"]}}]}
ALL_SPECS = [NUM6, EXPR, PRIM, SET, IV, MCQ, PARTS]

HOSTILE = [
    "9^9^9^9", "(x+1)^5000", "factorial(3000)", "__import__('os').system('ls')", "gamma(5)", "Integral(x,x)",
    "Sum(k,(k,1,5))", "Derivative(x,x)", "conjugate(x)", "I", "zoo", "oo", "Symbol('y')", "exp(exp(exp(100)))", "10^10^10",
    "(" * 60 + "x" + ")" * 60, "x" * 5000, "1e999", "9" * 400, "2^1000000", "lambda: 1", "().__class__", "x.__class__",
    "\\frac{1}{0}", "0/0", "1/0", "sqrt(-1)", "ln(0)", "tan(pi/2)", "e^(e^(e^(e^9)))", "x^x^x^x^x^x", "|||x|||", "((", "))",
    "1..2", "1.2.3", "{{7*7}}", "%s%s%s", "\x00\x01", "<script>alert(1)</script>", "eval('1')", "open('/etc/passwd')",
    "1" + "+1" * 400, "-" * 200 + "1", "sin(" * 50 + "x" + ")" * 50, "2**2**2**2**2", "1e-999", "(1/3)^1000", "\\sqrt[1000]{2}",
]


@pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s["type"])
def test_hostile_input_never_raises_or_hangs(spec):
    for raw in HOSTILE:
        t0 = time.perf_counter()
        res = mm.mark_answer(raw, spec, 2)
        mm.preview(raw, spec["type"])
        assert time.perf_counter() - t0 < 1.0, raw[:40]
        assert isinstance(res, mm.MathsResult)
        assert not (res.correct and spec is NUM6), raw[:40]


@pytest.mark.parametrize("raw", ["factorial(3)", "gamma(5)", "Integral(x,x)", "Symbol('y')", "__import__('os')", "I", "zoo", "y + 1"])
def test_names_outside_the_whitelist_are_rejected(raw):
    with pytest.raises(ParseError):
        parse_ast(raw)
    res = mm.mark_answer(raw, NUM6, 2)
    assert not res.correct and not res.parsed


def test_size_and_exponent_caps():
    for raw in ("9^9^9^9", "2^1000000", "10^10^10", "9" * 40):
        with pytest.raises(ParseError):
            parse_ast(raw)
    assert mm.mark_answer("2^10", {"type": "num", "value": "1024"}, 1).correct


@pytest.mark.parametrize("given,value", [
    ("sin2x", "sin(2*x)"), ("4xcos4x + sin4x", "4*x*cos(4*x) + sin(4*x)"), ("2^x ln2", "2**x*log(2)"),
    ("ln|2x+4|", "log(Abs(2*x+4))"), ("1/2 ln|2x+4|", "log(Abs(2*x+4))/2"), ("sin^2 x", "sin(x)**2"), ("x⁴", "x**4"),
    ("\\frac{1}{2}x^{2}", "x**2/2"), ("e^(2x)", "exp(2*x)"), ("2pi/3", "2*pi/3"), ("√(x+1)", "sqrt(x+1)"),
])
def test_natural_notation(given, value):
    assert mm.mark_answer(given, {"type": "expr", "value": value, "vars": ["x"]}, 1).correct, given


@pytest.mark.parametrize("given,value", [("1 1/2", "3/2"), ("10 2/3", "32/3"), ("12 345", "12345"), ("$ 1 234.57", "1234.57"),
                                         ("1,234.5", "1234.5"), ("log_2 8", "3"), ("log2(8)", "3"), ("the 14th term", "14")])
def test_number_notation(given, value):
    assert mm.mark_answer(given, {"type": "num", "value": value}, 1).correct, given


def test_units_are_checked_not_ignored():
    area = {"type": "num", "value": "225", "units": "cm^2"}
    assert mm.mark_answer("225 cm^2", area, 2).correct
    assert mm.mark_answer("225 square centimetres", area, 2).correct
    wrong = mm.mark_answer("225 cm", area, 2)
    assert not wrong.correct and wrong.mark == 1 and wrong.topic_tag == "units" and wrong.category == "notation"
    assert not mm.mark_answer("225 m^2", area, 2).correct
    acc = {"type": "num", "value": "-4", "units": "m/s^2"}
    assert mm.mark_answer("-4 ms^-2", acc, 2).correct
    assert not mm.mark_answer("-4 m", acc, 2).correct
    bare = mm.mark_answer("225", area, 2)  # number right, unit omitted: full marks with a reminder
    assert bare.correct and any("units" in n for n in bare.notes)


def test_rounding_semantics_nearest_dollar_and_cent():
    dollar = {"type": "num", "value": "29449.6123", "dp": 0, "units": "$"}
    assert mm.mark_answer("$29450", dollar, 2).correct
    for off in ("29449", "29451"):
        r = mm.mark_answer(off, dollar, 2)
        assert not r.correct and r.topic_tag == "rounding", off
    unrounded = mm.mark_answer("29449.61", dollar, 2)
    assert not unrounded.correct and unrounded.mark == 1 and unrounded.category == "notation"
    cent = {"type": "num", "value": "1244.245", "dp": 2, "units": "$"}
    assert mm.mark_answer("1244.25", cent, 2).correct  # half up
    assert not mm.mark_answer("1244.24", cent, 2).correct
    approx = {"type": "num", "value": "81.5", "tol": 0.5}
    assert mm.mark_answer("81.3", approx, 2).correct and not mm.mark_answer("82.1", approx, 2).correct


def test_exact_value_required_but_decimal_loses_one_mark():
    r = mm.mark_answer("0.333", {"type": "num", "value": "1/3"}, 2)
    assert not r.correct and r.mark == 1 and r.topic_tag == "exact values"
    assert mm.mark_answer("0.25", {"type": "num", "value": "1/4"}, 2).correct  # terminating decimal is exact


@pytest.mark.parametrize("given,letter", [("B", "B"), ("(B)", "B"), ("b.", "B"), ("Answer: B", "B"), ("The answer is C", "C"),
                                          ("option d", "D"), ("I think it is A", "A"), ("A)", "A")])
def test_mcq_letters(given, letter):
    assert mm.mcq_letter(given) == letter


def test_mcq_yes_no_maps_to_option_text():
    opts = ["A. Yes, it is a term", "B. No, it is not a term"]
    assert mm.mark_answer("No", {"type": "mcq", "value": "B", "options": opts}, 1).correct
    assert not mm.mark_answer("yes", {"type": "mcq", "value": "B", "options": opts}, 1).correct


def test_interval_direction_matters():
    dec = {"type": "interval", "var": "x", "intervals": [["-2", "3", False, False]]}
    for ok in ("-2 < x < 3", "(-2, 3)", "-2<x<3", "3 > x > -2", "x in (-2, 3)"):
        assert mm.mark_answer(ok, dec, 2).correct, ok
    wrong = mm.mark_answer("x < -2 or x > 3", dec, 2)
    assert not wrong.correct and wrong.mark == 0 and wrong.category == "interpretation" and wrong.topic_tag == "inequality direction"
    ends_only = mm.mark_answer("-2, 3", dec, 2)
    assert not ends_only.correct and ends_only.mark == 1 and ends_only.category == "incomplete reasoning"
    closed = mm.mark_answer("-2 <= x <= 3", dec, 2)
    assert not closed.correct and closed.mark == 1
    ignore = dict(dec, ends="ignore")
    assert mm.mark_answer("-2 <= x <= 3", ignore, 2).correct
    two = {"type": "interval", "var": "x", "intervals": [["-oo", "-1", False, True], ["4", "oo", True, False]]}
    assert mm.mark_answer("x <= -1 or x >= 4", two, 2).correct
    assert mm.mark_answer("(-oo, -1] U [4, oo)", two, 2).correct
    assert not mm.mark_answer("-1 <= x <= 4", two, 2).correct


def test_multi_part_marks_each_part():
    r = mm.mark_answer("(a) 2\n(b) x", PARTS, 3)
    assert r.correct and r.mark == 3
    r = mm.mark_answer("(a) 2\n(b) 2x", PARTS, 3)
    assert not r.correct and r.mark == 1 and [p["correct"] for p in r.parts] == [True, False]
    assert r.diagnosis.startswith("Part (b)")
    # unlabelled lines are taken in order; a missing part scores 0 for that part only
    assert mm.mark_answer("2\nx", PARTS, 3).correct
    assert mm.mark_answer("(b) x", PARTS, 3).mark == 2


def test_part_common_errors_and_two_axis_tags():
    spec = {"type": "parts", "parts": [{"label": "a", "marks": 2, "answer": {"type": "num", "value": "12"}}]}
    ces = [{"answer": "-12", "category": "careless error", "topic_tag": "sign error", "diagnosis": "Sign.", "step": 2, "part": "a", "marks": 1}]
    r = mm.mark_answer("(a) -12", spec, 2, ces)
    assert not r.correct and r.category == "careless error" and r.topic_tag == "sign error" and r.common_error
    assert r.mark == 1 and r.step == 2


def test_set_common_error_matches_in_any_order():
    spec = {"type": "set", "values": ["2", "-3"]}
    ces = [{"answer": "-2, 3", "category": "careless error", "topic_tag": "sign error", "diagnosis": "Signs swapped."}]
    r = mm.mark_answer("3, -2", spec, 2, ces)
    assert r.common_error and r.topic_tag == "sign error"


def test_categories_are_the_spec_lists():
    assert set(mm.CATEGORIES) == {"conceptual", "algebraic", "arithmetic", "interpretation", "formula selection",
                                  "incomplete reasoning", "insufficient working", "notation", "careless error"}
    for tag in ("sign error", "chain rule", "algebra", "domain/range", "calculator error", "probability interpretation"):
        assert tag in mm.TOPIC_TAGS
    neg = mm.mark_answer("-6", NUM6, 2)
    assert neg.category == "careless error" and neg.topic_tag == "sign error"
    chain = mm.mark_answer("3*cos(3x)", {"type": "expr", "value": "cos(3*x)", "vars": ["x"]}, 2)
    assert chain.category == "algebraic"


def test_antiderivative_plus_c():
    assert mm.mark_answer("x^3/3 + C", PRIM, 2).correct
    r = mm.mark_answer("x^3/3", PRIM, 2)
    assert r.correct and any("+ C" in n for n in r.notes)
    assert mm.mark_answer("x^3/3 + 5", PRIM, 2).correct
    assert not mm.mark_answer("x^3", PRIM, 2).correct


@pytest.mark.parametrize("kind,text,ok", [
    ("set", "3, 5", True), ("interval", "-2 < x <= 3", True), ("antiderivative", "x^2 + C", True), ("mcq", "B", True),
    ("num", "$1,234.50", True), ("expr", "C + x", False), ("expr", "factorial(3)", False), ("interval", "nonsense <", False),
])
def test_preview_is_type_aware(kind, text, ok):
    out = mm.preview(text, kind)
    assert out["ok"] is ok


def test_preview_keeps_c_for_non_antiderivatives():
    # 'C' is not a whitelisted name, so an expression containing it is not silently accepted
    assert not mm.preview("x + C", "expr")["ok"]
    assert mm.preview("x + C", "antiderivative")["latex"].endswith("+ C")


def test_preview_route_never_errors(client):
    for raw in HOSTILE[:20]:
        for kind in ("num", "expr", "set", "interval", "antiderivative", "mcq", "parts", "bogus"):
            r = client.post("/api/math-preview", data={"text": raw, "kind": kind, "var": "x"})
            assert r.status_code == 200 and "ok" in r.json()
    r = client.post("/api/math-preview", data={"text": "x" * 20000, "kind": "expr"})
    assert r.status_code == 200 and r.json()["ok"] is False
