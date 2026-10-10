import pytest

from app.marking.maths import mark_answer, parse


@pytest.mark.parametrize("given,expected", [
    ("1/3", "1/3"), ("2/6", "1/3"), ("\\frac{1}{3}", "1/3"), ("0.5", "1/2"), ("√3/2", "sqrt(3)/2"), ("sqrt(12)", "2*sqrt(3)"),
    ("2pi/3", "2*pi/3"), ("e^2 - 1", "exp(2) - 1"), ("ln(5/2)/3", "log(5/2)/3"), ("1/3 ln 2.5", "log(5/2)/3"), ("-5", "-5"),
])
def test_equivalent_numbers(given, expected):
    assert mark_answer(given, {"type": "num", "value": expected}, 2).correct


@pytest.mark.parametrize("given,expected", [
    ("3x^2 + 2x", "x*(3*x + 2)"), ("y = 2x(x+1)", "2*x**2 + 2*x"), ("e^(2x)(1 + 2x)", "exp(2*x) + 2*x*exp(2*x)"),
    ("2^x ln 2", "2**x*log(2)"), ("1/(x ln 3)", "1/(x*log(3))"), ("\\frac{3}{3x+1}", "3/(3*x+1)"),
])
def test_equivalent_expressions(given, expected):
    assert mark_answer(given, {"type": "expr", "value": expected, "vars": ["x"]}, 2).correct


def test_wrong_expression_not_accepted():
    assert not mark_answer("3x^2", {"type": "expr", "value": "x*(3*x + 2)"}, 2).correct


def test_primitive_accepts_any_constant_and_notes_missing_c():
    r = mark_answer("x^3/3 + 5x", {"type": "antiderivative", "value": "x**3/3 + 5*x", "var": "x"}, 1)
    assert r.correct and any("+ C" in n for n in r.notes)
    assert mark_answer("x^3/3 + 5x + C", {"type": "antiderivative", "value": "x**3/3 + 5*x + 7", "var": "x"}, 1).correct


def test_numeric_tolerance_and_units():
    assert mark_answer("$1,234.57", {"type": "num", "value": "1234.57", "tol": 0.01, "units": "$"}, 2).correct
    assert mark_answer("16 cm^2", {"type": "num", "value": "16"}, 2).correct
    assert mark_answer("81.5%", {"type": "num", "value": "81.5", "tol": 0.05}, 2).correct
    assert not mark_answer("1234.60", {"type": "num", "value": "1234.57", "tol": 0.01}, 2).correct


def test_exact_value_required():
    r = mark_answer("0.333", {"type": "num", "value": "1/3"}, 2)
    assert not r.correct and r.category == "notation" and r.mark == 1


def test_sets_unordered_and_partial():
    assert mark_answer("x = 2 or x = -3", {"type": "set", "values": ["-3", "2"]}, 2).correct
    assert mark_answer("2", {"type": "set", "values": ["-3", "2"]}, 2).mark == 1
    assert mark_answer("(1, -6)", {"type": "set", "values": ["1", "-6"], "ordered": True}, 4).correct
    assert not mark_answer("(-6, 1)", {"type": "set", "values": ["1", "-6"], "ordered": True}, 4).correct


def test_error_classification():
    r = mark_answer("-5", {"type": "num", "value": "5"}, 2)
    assert r.category == "careless error" and r.topic_tag == "sign error"  # v2: two axes (5C category + spec-23 tag)
    r = mark_answer("7", {"type": "num", "value": "5"}, 2, [{"answer": "7", "category": "formula selection", "diagnosis": "Used a + nd"}])
    assert r.category == "formula selection" and "a + nd" in r.diagnosis
    assert mark_answer("abc((", {"type": "num", "value": "5"}, 2).category == "notation"


def test_mcq():
    assert mark_answer("B", {"type": "mcq", "value": "B"}, 1).correct
    assert not mark_answer("C", {"type": "mcq", "value": "B"}, 1).correct


def test_parse_latex():
    import sympy as sp

    assert sp.simplify(parse("\\frac{\\sqrt{2}}{2}") - sp.sqrt(2) / 2) == 0


def test_all_templates_mark_their_own_answer():
    from app.services import maths_templates

    for code in maths_templates.TEMPLATES:
        for d in (1, 2, 3):
            g = maths_templates.generate(code, 3, d)
            a = g.answer
            resp = ", ".join(a["values"]) if a["type"] == "set" else a["value"]
            r = mark_answer(resp, a, g.marks, g.common_errors)
            assert r.correct, f"{code} L{d}: {resp} not accepted"
