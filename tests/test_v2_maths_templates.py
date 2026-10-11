"""v2 maths templates: every learning-plan subtopic has a real template, difficulty tiers are real,
the content self-test passes, and every answer is recomputed INDEPENDENTLY from the generating
parameters (numerically, with mpmath, not by re-running the template's own SymPy algebra)
(audit maths-06, 09, 10, 13, 16, 17, 20; selection-02, selection-08; adaptive-10)."""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import mpmath as mp
import pytest
import sympy as sp

from app.marking.maths import mark_answer
from app.services import maths_templates as mt
from app.services.maths_tpl_base import model_response

X = sp.Symbol("x")
SEEDS = range(12)
ENRICHMENT = {"3D", "6F"}


def plan_codes() -> list[str]:
    plan = json.loads((Path(__file__).resolve().parent.parent / "data/seed/curriculum.json").read_text())["plan"]
    return [p["code"] for p in plan if p["code"][0].isdigit() or p["code"].startswith("Y11-")]


# ------------------------------------------------------------------ helpers ---
def fn(expr: str, var: str = "x"):
    """A numeric (mpmath) function from a trusted stored expression string."""
    e = sp.sympify(expr, locals={"e": sp.E, "ln": sp.log})
    return sp.lambdify(sp.Symbol(var), e, "mpmath")


def poly_coeffs(expr: str) -> list:
    return [mp.mpf(sp.Rational(c)) for c in sp.Poly(sp.sympify(expr), X).all_coeffs()]


def deriv_coeffs(cs: list) -> list:
    deg = len(cs) - 1
    return [c * (deg - i) for i, c in enumerate(cs[:-1])]


def real_roots(cs: list) -> list[float]:
    while cs and abs(cs[0]) < 1e-30:
        cs = cs[1:]
    if len(cs) < 2:
        return []
    rts = mp.polyroots(cs, maxsteps=200, extraprec=200)
    out = sorted(float(mp.re(z)) for z in rts if abs(mp.im(z)) < 1e-9)
    dedup: list[float] = []
    for v in out:
        if not dedup or abs(v - dedup[-1]) > 1e-7:
            dedup.append(v)
    return dedup


def sign_region(f, roots: list[float], positive: bool) -> list[tuple]:
    """Where f > 0 (or < 0), as merged (lo, hi) intervals with None for infinity, given f's zeros."""
    cuts = [None] + list(roots) + [None]
    out: list[list] = []
    for lo, hi in zip(cuts, cuts[1:]):
        mid = (lo - 1 if hi is None else hi - 1) if lo is None else (lo + 1 if hi is None else (lo + hi) / 2)
        val = f(mid)
        if (val > 0) == positive and abs(val) > 1e-12:
            if out and out[-1][1] == lo:
                out[-1][1] = hi
            else:
                out.append([lo, hi])
    return [tuple(v) for v in out]


def close(a, b, rel=1e-7) -> bool:
    return abs(float(a) - float(b)) <= rel * max(1.0, abs(float(b)))


def stored_num(v: str) -> float:
    return float(sp.sympify(v, locals={"e": sp.E, "ln": sp.log}).evalf(30))


def assert_spec(spec: dict, exp, where: str = ""):
    kind = spec["type"]
    if kind == "parts":
        assert isinstance(exp, dict), where
        for p in spec["parts"]:
            if p["label"] in exp:
                assert_spec(p["answer"], exp[p["label"]], f"{where}({p['label']})")
        return
    if kind == "num":
        assert close(stored_num(spec["value"]), exp, 1e-6), f"{where}: stored {spec['value']} vs recomputed {exp}"
        return
    if kind == "mcq":
        assert spec["value"] == exp, f"{where}: {spec['value']} vs {exp}"
        return
    if kind == "set":
        got = [stored_num(v) for v in spec["values"]]
        want = [float(v) for v in exp]
        if not spec.get("ordered"):
            got, want = sorted(got), sorted(want)
        assert len(got) == len(want) and all(close(a, b, 1e-6) for a, b in zip(got, want)), f"{where}: {got} vs {want}"
        return
    if kind == "interval":
        got = [(None if str(lo) == "-oo" else stored_num(lo), None if str(hi) == "oo" else stored_num(hi)) for lo, hi, *_ in spec["intervals"]]
        want = [tuple(e[:2]) for e in exp]
        assert len(got) == len(want), f"{where}: {got} vs {want}"
        for (a, b), (c, d) in zip(sorted(got, key=lambda t: -1e18 if t[0] is None else t[0]), sorted(want, key=lambda t: -1e18 if t[0] is None else t[0])):
            assert (a is None) == (c is None) and (b is None) == (d is None), f"{where}: {got} vs {want}"
            assert (a is None or close(a, c, 1e-6)) and (b is None or close(b, d, 1e-6)), f"{where}: {got} vs {want}"
        return
    var = spec.get("var") or (spec.get("vars") or ["x"])[0]
    stored = fn(spec["value"], var)
    pts = [mp.mpf(v) for v in ("0.37", "1.3", "2.71", "0.83", "3.3", "1.9")]
    if kind == "expr":
        checked = 0
        for t in pts:
            try:
                a, b = stored(t), exp(t)
            except (ZeroDivisionError, ValueError):
                continue
            assert close(a, b, 1e-6), f"{where}: expr {spec['value']} at {t}: {a} vs {b}"
            checked += 1
        assert checked >= 3, where
        return
    if kind == "antiderivative":
        for t in pts:
            assert close(mp.diff(stored, t), exp(t), 1e-6), f"{where}: d/dx of {spec['value']} at {t} vs integrand {exp(t)}"
        return
    raise AssertionError(f"unknown kind {kind}")


VERIFY: dict = {}


def verifies(*codes):
    def deco(f):
        for c in codes:
            VERIFY[c] = f
        return f
    return deco


def stationary(fs: str) -> list[float]:
    return real_roots(deriv_coeffs(poly_coeffs(fs)))


def second_roots(fs: str) -> list[float]:
    return real_roots(deriv_coeffs(deriv_coeffs(poly_coeffs(fs))))


def poly_fn(cs):
    return lambda t: mp.polyval(cs, t)


# ------------------------------------------------------------------- chapter 1 ---
@verifies("1A")
def v_1A(g):
    p = g.params
    if p["form"] == "explicit":
        return p["a"] * p["m"] ** 2 + p["b"] * p["m"] + p["c"]
    if p["form"] == "recursive":
        t = p["p"]
        for _ in range(p["m"] - 1):
            t = p["q"] * t + p["s"]
        return t
    if p["form"] == "which":
        n = 1
        while p["a"] * n + p["c"] != p["v"]:
            n += 1
        return n
    T = lambda n: n * n - p["p"] * n  # noqa: E731
    which = next(n for n in range(1, 500) if T(n) == p["v"])
    return {"a": T(p["m"]), "b": which, "c": sum(1 for n in range(1, 500) if T(n) < 0)}


@verifies("1B")
def v_1B(g):
    p = g.params
    if p["form"] == "nth":
        return p["a"] + (p["m"] - 1) * p["d"]
    if p["form"] == "two_terms":
        d = Fraction(p["Tq"] - p["Tp"], p["q"] - p["p"])
        a = p["Tp"] - (p["p"] - 1) * d
        return a + (p["m"] - 1) * d
    xv = p["x"]
    t1, t2, t3 = xv + p["p"], 2 * xv + p["q"], 4 * xv + p["s"]
    assert t2 - t1 == t3 - t2
    d = t2 - t1
    n = next(n for n in range(1, 10000) if t1 + (n - 1) * d > p["B"])
    return {"a": xv, "b": lambda t: t1 + (t - 1) * d, "c": n}


# ------------------------------------------------------------------- chapter 2 ---
@verifies("2A")
def v_2A(g):
    p = g.params
    if p["form"] == "quad":
        cs = [mp.mpf(p["a"]), mp.mpf(-2 * p["a"] * p["h"]), mp.mpf(p["c"])]
        d = deriv_coeffs(cs)
        return sign_region(poly_fn(d), real_roots(d), True)
    if p["form"] == "stat_k":
        # y' = 3x^2 + 2bx + k = 0 at x = m
        return -(3 * p["m"] ** 2 + 2 * p["b"] * p["m"])
    cs = poly_coeffs(p["f"])
    d = deriv_coeffs(cs)
    st = real_roots(d)
    if p["form"] == "dec":
        return sign_region(poly_fn(d), st, False)
    return {"a": poly_fn(d), "b": st, "c": sign_region(poly_fn(d), st, True)}


@verifies("2B")
def v_2B(g):
    p = g.params
    if p["form"] == "statx":
        return stationary(p["f"])
    if p["form"] == "max_cubic":
        cs = poly_coeffs(p["f"])
        st = stationary(p["f"])
        d2 = deriv_coeffs(deriv_coeffs(cs))
        mx = next(s for s in st if mp.polyval(d2, s) < 0)
        return [mx, mp.polyval(cs, mx)]
    if p["form"] == "max_quartic":
        f = lambda t: t**4 - 2 * p["a"] ** 2 * t**2 + p["c"]  # noqa: E731
        st = [-p["a"], 0, p["a"]]
        mx = next(s for s in st if mp.diff(f, s, 2) < 0)
        return [mx, f(mx)]
    cs = poly_coeffs(p["f"])
    st = stationary(p["f"])
    vals = [mp.polyval(cs, s) for s in st]
    return {"a": st, "b": max(vals), "c": [(min(vals), max(vals))]}


@verifies("2C")
def v_2C(g):
    p = g.params
    if p["form"] in ("f2x", "f2m"):
        d2 = deriv_coeffs(deriv_coeffs(poly_coeffs(p["f"])))
        return poly_fn(d2) if p["form"] == "f2x" else mp.polyval(d2, p["m"])
    if p["form"] == "chain":
        a, b, m = p["a"], p["b"], p["m"]
        return lambda t: mp.diff(lambda s: (a * s + b) ** m, t, 2)
    a, b = p["a"], p["b"]
    f = lambda t: b * t**2 + a / t  # noqa: E731
    root = mp.findroot(lambda t: mp.diff(f, t, 2), p["x0"] + 0.3)
    return {"a": lambda t: mp.diff(f, t), "b": lambda t: mp.diff(f, t, 2), "c": root}


@verifies("2D")
def v_2D(g):
    p = g.params
    cs = poly_coeffs(p["f"])
    d2 = deriv_coeffs(deriv_coeffs(cs))
    r2 = real_roots(d2)
    if p["form"] == "up":
        return sign_region(poly_fn(d2), r2, True)
    if p["form"] == "poi":
        assert len(r2) == 1
        return [r2[0], mp.polyval(cs, r2[0])]
    # inflection = sign change of f'' (check numerically either side)
    pois = [v for v in r2 if mp.polyval(d2, v - 1e-3) * mp.polyval(d2, v + 1e-3) < 0]
    return {"a": poly_fn(d2), "b": pois, "c": sign_region(poly_fn(d2), r2, False)}


@verifies("2E")
def v_2E(g):
    p = g.params
    if p["form"] == "parity":
        f = fn(p["f"])
        pts = [0.3, 1.1, 2.7]
        if all(close(f(-t), -f(t), 1e-9) for t in pts):
            return "A"
        if all(close(f(-t), f(t), 1e-9) for t in pts):
            return "B"
        return "C"
    if p["form"] == "asym":
        a, b, c = p["a"], p["b"], p["c"]
        f = lambda t: (a * t + b) / (t - c)  # noqa: E731
        assert abs(f(c + 1e-9)) > 1e5
        return {"a": c, "b": f(mp.mpf(10) ** 12)}
    if p["form"] == "hpoi":
        a, s = p["a"], p["s"]
        cs = [mp.mpf(s), -4 * a * s, 0, 0, 0]
        d = deriv_coeffs(cs)
        st = real_roots(d)
        left, right = mp.polyval(d, -0.01), mp.polyval(d, 0.01)
        nature = "C" if left * right > 0 else ("A" if left > 0 else "B")
        return {"a": st, "b": nature}
    pp = p["p"]
    f = lambda t: t * (t - pp) ** 2  # noqa: E731
    cs = [mp.mpf(1), -2 * pp, pp * pp, 0]
    st = stationary_from(cs)
    d2 = deriv_coeffs(deriv_coeffs(cs))
    mx = next(s for s in st if mp.polyval(d2, s) < 0)
    vals = [f(s) for s in st]
    return {"a": real_roots(cs), "b": [mx, f(mx)], "c": real_roots(d2)[0], "d": [(None, min(vals)), (max(vals), None)]}


def stationary_from(cs):
    return real_roots(deriv_coeffs(cs))


@verifies("2F")
def v_2F(g):
    p = g.params
    if p["form"] == "quad":
        f = lambda t: -p["a"] * (t - p["h"]) ** 2 + p["c"]  # noqa: E731
        grid = [p["lo"] + i * (p["hi"] - p["lo"]) / 20000 for i in range(20001)]
        return max(f(t) for t in grid)
    cs = poly_coeffs(p["f"])
    cands = [p["lo"], p["hi"]] + [s for s in stationary(p["f"]) if p["lo"] <= s <= p["hi"]]
    vals = [mp.polyval(cs, c) for c in cands]
    if p["form"] == "cubic":
        return max(vals) if p["word"] == "maximum" else min(vals)
    return {"a": stationary(p["f"]), "b": max(vals), "c": min(vals)}


@verifies("2G")
def v_2G(g):
    p = g.params
    if p["form"] == "cont":
        return p["a"] * p["c"] + p["b"] - p["c"] ** 2
    if p["form"] == "diff_ab":
        left = lambda t: p["p"] * t**2 + p["q"]  # noqa: E731
        a = mp.diff(left, p["c"])
        return {"a": a, "b": left(p["c"]) - a * p["c"]}
    if p["form"] == "abs":
        m = p["m"]
        f = lambda t: abs(t * t - m * m)  # noqa: E731
        corners = []
        for t in [i / 4 for i in range(-40, 41)]:
            h = 1e-6
            if abs((f(t + h) - f(t)) / h - (f(t) - f(t - h)) / h) > 1e-2:
                corners.append(t)
        return corners
    b, c, m = p["b"], p["c"], p["m"]
    left = lambda t: t * t + b * t  # noqa: E731
    k = left(c) - m * c
    grad = mp.diff(left, c)
    return {"a": k, "b": grad, "c": "A" if close(grad, m) else "B"}


@verifies("2H")
def v_2H(g):
    p = g.params
    if p["form"] == "profit":
        P = lambda t: 2 * p["a"] * p["h"] * t - p["a"] * t * t - p["c"]  # noqa: E731
        return mp.findroot(lambda t: mp.diff(P, t), 1) and P(mp.findroot(lambda t: mp.diff(P, t), 1))
    if p["form"] == "fence":
        Lf = p["L"]
        return max(t * (Lf - 2 * t) for t in [i * Lf / 2 / 40000 for i in range(40001)])
    if p["form"] == "box":
        s = p["s"]
        V = lambda t: t * (s - 2 * t) ** 2  # noqa: E731
        xs = mp.findroot(lambda t: mp.diff(V, t), s / 5)
        return {"a": V, "b": xs, "c": V(xs)}
    m = p["m"]
    c = 3 * m * m
    A = lambda t: 2 * t * (c - t * t)  # noqa: E731
    xs = mp.findroot(lambda t: mp.diff(A, t), m + 0.2)
    return {"a": A, "b": xs, "c": A(xs)}


@verifies("2I")
def v_2I(g):
    p = g.params
    if p["form"] == "poly":
        return fn(p["f"])
    if p["form"] == "powers":
        return lambda t: p["a"] * mp.sqrt(t) + p["b"] / t**2
    if p["form"] == "point":
        a, b, c, x0, y0 = p["a"], p["b"], p["c"], p["x0"], p["y0"]
        fp = lambda t: 3 * a * t * t + 2 * b * t + c  # noqa: E731
        return lambda t: y0 + mp.quad(fp, [x0, t])
    m1, m2, y0 = p["m1"], p["m2"], p["y0"]
    B = -mp.mpf(3) * (m1 + m2) / 2
    k = -(3 * m1 * m1 + 2 * B * m1)
    grad = lambda t: 3 * t * t + 2 * B * t + k  # noqa: E731
    others = [r for r in real_roots([mp.mpf(3), 2 * B, k]) if not close(r, m1)]
    return {"a": k, "b": lambda t: y0 + mp.quad(grad, [m1, t]), "c": others[0]}


# --------------------------------------------------------------------- tests ---
def test_every_plan_subtopic_has_its_own_v2_template():
    missing = [c for c in plan_codes() if c not in ENRICHMENT and c not in mt.V2_CODES]
    assert not missing, f"no v2 template for {missing}"


def test_templates_are_distinct_functions():
    fns = {}
    for code in mt.V2_CODES:
        f = mt.TEMPLATES[code]
        assert f not in fns.values(), f"{code} is an alias of {[c for c, g in fns.items() if g is f]}"
        fns[code] = f


def test_content_self_test_passes():
    problems = mt.self_test(sorted(mt.V2_CODES), seeds=8)
    assert problems == {}, json.dumps(problems, indent=1)[:4000]


@pytest.mark.parametrize("code", sorted(VERIFY))
def test_answers_recomputed_independently(code):
    if code not in mt.V2_CODES:
        pytest.skip("template not yet rewritten")
    for d in (1, 2, 3):
        for s in SEEDS:
            g = mt.generate(code, s, d)
            exp = VERIFY[code](g)
            assert_spec(g.answer, exp, f"{code} L{d} seed {s} {g.params}")
            assert mark_answer(model_response(g.answer), g.answer, g.marks, g.common_errors, options=g.options).correct


def test_every_v2_template_has_an_independent_verifier():
    assert not [c for c in mt.V2_CODES if c not in VERIFY]


def test_difficulty_tiers_are_real():
    for code in sorted(mt.V2_CODES):
        marks = {d: [mt.generate(code, s, d).marks for s in range(6)] for d in (1, 2, 3)}
        assert max(marks[1]) <= 2 and min(marks[3]) >= 4, (code, marks)
        assert sum(marks[3]) / 6 > sum(marks[1]) / 6, (code, marks)
        multi = sum(1 for s in range(6) if mt.generate(code, s, 3).answer.get("type") == "parts")
        assert multi >= 3, f"{code}: challenge tier should usually be a multi-part HSC-style question"


def test_challenge_items_fill_time():
    # selection-02: the challenge tier gives 8-10 minute items so the Maths slot can reach ~35 minutes
    mins = [mt.minutes_for(mt.generate(c, s, 3).marks) for c in mt.V2_CODES for s in range(3)]
    assert sum(mins) / len(mins) >= 7.5


def test_instances_vary():
    for code in sorted(mt.V2_CODES):
        for d in (1, 2, 3):
            texts = {mt.generate(code, s, d).text for s in range(25)}
            assert len(texts) >= 4, f"{code} L{d}: only {len(texts)} distinct questions in 25 seeds"


def test_two_axis_common_errors():
    from app.marking.maths import CATEGORIES, TOPIC_TAGS

    tags = set()
    for code in mt.V2_CODES:
        for d in (1, 2, 3):
            for ce in mt.generate(code, 1, d).common_errors:
                assert ce["category"] in CATEGORIES and ce["topic_tag"] in TOPIC_TAGS, (code, ce)
                tags.add(ce["topic_tag"])
    for t in ("sign error", "chain rule", "algebra", "domain/range", "calculator error", "probability interpretation"):
        assert t in tags or not mt.V2_CODES >= {"6B", "9B", "10D"}, f"no template tags '{t}'"


def test_questions_are_labelled_and_serialisable():
    for code in mt.V2_CODES:
        g = mt.generate(code, 2, 3)
        json.dumps(g.answer)
        json.dumps(g.solution())
        assert math.isfinite(mt.minutes_for(g.marks))
