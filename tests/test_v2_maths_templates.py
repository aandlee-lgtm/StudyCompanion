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
# Year 11 review items still use the v1 templates (not yet rewritten with difficulty tiers); see the report.
DEFERRED: set[str] = {"Y11-FUNC", "Y11-TRANS", "Y11-TRIG", "Y11-CALC", "Y11-EXPLOG", "Y11-PROB"}


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
    pts = [mp.mpf(v) for v in ("0.37", "1.3", "2.71", "0.83", "3.3", "1.9", "5.6", "8.2", "-0.7", "-2.6", "-4.3", "-5.2", "-6.9", "-8.8", "11.5", "14.2")]
    if kind == "expr":
        checked = 0
        for t in pts:
            try:
                a, b = stored(t), exp(t)
                if isinstance(a, mp.mpc) or isinstance(b, mp.mpc):
                    continue  # outside the real domain at this sample point
            except (ZeroDivisionError, ValueError):
                continue
            assert close(a, b, 1e-6), f"{where}: expr {spec['value']} at {t}: {a} vs {b}"
            checked += 1
        assert checked >= 3, where
        return
    if kind == "antiderivative":
        checked = 0
        for t in pts:
            try:
                want = exp(t)
                if isinstance(want, mp.mpc) or isinstance(stored(t), mp.mpc):
                    continue
            except (ZeroDivisionError, ValueError):
                continue
            checked += 1
            assert close(mp.diff(stored, t), want, 1e-6), f"{where}: d/dx of {spec['value']} at {t} vs integrand {exp(t)}"
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


def first_over(term, bound):
    """The first term number n whose value (term(n)) exceeds bound, by counting."""
    n = 1
    while term(n) <= bound:
        n += 1
    return n


def num(v):
    return mp.mpf(sp.Rational(v).p) / sp.Rational(v).q if not isinstance(v, (int, float)) else mp.mpf(v)


@verifies("1C")
def v_1C(g):
    p = g.params
    if p["form"] == "nth":
        t = p["a"]
        for _ in range(p["m"] - 1):
            t *= p["r"]
        return t
    if p["form"] == "two_terms":
        q = num(p["T5"]) / num(p["T2"])
        rr = mp.sign(q) * mp.cbrt(abs(q))
        return num(p["T5"]) * rr * rr
    a, rr, bound = p["a"], p["r"], p["bound"]
    nn = first_over(lambda n: a * rr ** (n - 1), bound)
    return {"a": lambda n: a * mp.power(rr, n - 1), "b": nn, "c": a * rr ** (nn - 1)}


@verifies("1D")
def v_1D(g):
    p = g.params
    if p["form"] == "gm":
        return mp.sqrt(p["p"] * p["m"])
    if p["form"] == "ap":
        kk, c = p["k"], p["c"]
        return froot(lambda v: ((v + kk) - v) - (((c + 1) * v - kk) - (v + kk)), -1000, 1000)
    a, b = p["a"], p["b"]
    xv = froot(lambda v: (v + a) ** 2 - v * (v + b), mp.mpf("1e-9"), 10000)
    if p["form"] == "gp":
        return xv
    rr = (xv + a) / xv
    return {"a": xv, "b": rr, "c": first_over(lambda n: xv * rr ** (n - 1), p["bound"])}


@verifies("1E")
def v_1E(g):
    p = g.params
    if p["form"] == "sigma":
        return sum(p["a"] * kk + p["b"] for kk in range(1, p["N"] + 1))
    if p["form"] == "pow2":
        return sum(2**kk for kk in range(p["lo"], p["lo"] + p["cnt"]))
    S = lambda n: p["p"] * n * n + p["q"] * n  # noqa: E731
    if p["form"] == "SnTn":
        return S(p["m"]) - S(p["m"] - 1)
    v = S(p["w"]) - S(p["w"] - 1)
    return {"a": S(1), "b": lambda n: S(n) - S(n - 1), "c": next(n for n in range(1, 1000) if S(n) - S(n - 1) == v)}


@verifies("1F")
def v_1F(g):
    p = g.params
    if p["form"] == "Sn":
        return sum(p["a"] + i * p["d"] for i in range(p["N"]))
    if p["form"] == "findn":
        tot, n = 0, 0
        while tot < p["S"]:
            tot += p["a"] + n * p["d"]
            n += 1
        assert tot == p["S"]
        return n
    mult = [v for v in range(p["A"], p["B"] + 1) if v % p["k"] == 0]
    return {"a": len(mult), "b": sum(mult), "c": sum(v for v in range(p["A"], p["B"] + 1) if v % p["k"])}


@verifies("1G")
def v_1G(g):
    p = g.params
    a, rr = p["a"], Fraction(str(p["r"]))
    if p["form"] == "Sn":
        return float(sum(a * rr**i for i in range(p["N"])))
    if p["form"] == "findn":
        tot, n = 0, 0
        while tot < p["S"]:
            tot += a * rr**n
            n += 1
        assert tot == p["S"]
        return n
    part = lambda n: sum(a * rr**i for i in range(n))  # noqa: E731
    rf = mp.mpf(rr.numerator) / rr.denominator
    assert all(abs(a * (rf**j - 1) / (rf - 1) - float(part(j))) < 1e-6 for j in range(1, 12))  # closed form = partial sums
    return {"a": lambda n: a * (mp.power(rf, n) - 1) / (rf - 1), "b": first_over(lambda n: part(n), p["bound"])}


@verifies("1H")
def v_1H(g):
    p = g.params
    if p["form"] == "Sinf":
        rr = num(p["r"])
        return sum(p["a"] * rr**i for i in range(400))
    if p["form"] == "findr":
        return froot(lambda rr: p["a"] / (1 - rr) - num(p["S"]), mp.mpf("-0.999999"), mp.mpf("0.999999"))
    m = p["m"]
    if p["form"] == "interval":
        c = p["c"]
        cs = [mp.mpf(m * m), mp.mpf(-2 * m * c), mp.mpf(c * c - 1)]
        return sign_region(poly_fn(cs), real_roots(cs), False)
    a = p["a"]
    cs = [mp.mpf(m * m), mp.mpf(0), mp.mpf(-1)]
    x1 = mp.mpf(1) / (2 * m)
    return {"a": sign_region(poly_fn(cs), real_roots(cs), False), "b": sum(a * (m * x1) ** i for i in range(400)),
            "c": froot(lambda v: a / (1 - m * v) - num(p["S2"]), -mp.mpf(1) / m + mp.mpf("1e-12"), mp.mpf(1) / m - mp.mpf("1e-12"))}


@verifies("1I")
def v_1I(g):
    p = g.params
    if p["form"] == "two":
        return mp.mpf("0." + f"{p['dig']:02d}" * 20)
    if p["form"] == "mixed":
        return mp.mpf("0." + str(p["pre"]) + str(p["rep"]) * 40)
    b = p["blk"]
    return {"a": mp.mpf(b) / 1000, "b": mp.mpf(1) / 1000, "c": mp.mpf("0." + str(b) * 15)}


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


# ------------------------------------------------------------------- chapter 3 ---
def quad(f, *pts):
    return mp.quad(f, list(pts))


@verifies("3A")
def v_3A(g):
    p = g.params
    if p["form"] == "geom":
        f = fn(p["f"])
        cuts = sorted({p["lo"], p["hi"]} | {v for v in range(p["lo"], p["hi"] + 1)})
        return quad(f, *cuts)
    r_, k_, m_ = p["rad"], p["k"], p["m"]
    semi = lambda t: mp.sqrt(max(r_ * r_ - t * t, 0))  # noqa: E731
    return {"a": quad(semi, -r_, r_), "b": quad(lambda t: semi(t) + m_ * t + k_, -r_, r_), "c": quad(lambda t: semi(t) - k_, 0, r_)}


@verifies("3B")
def v_3B(g):
    p = g.params
    if p["form"] == "def":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    a, b, V = p["a"], p["b"], p["V"]
    F = lambda kv: quad(lambda t: 2 * t + b, a, kv)  # noqa: E731
    roots = real_roots([mp.mpf(1), mp.mpf(b), mp.mpf(-(a * a + a * b) - V)])
    return {"a": F, "b": [r_ for r_ in roots if r_ > a][0], "c": lambda kv: 2 * kv + b}


@verifies("3C")
def v_3C(g):
    p = g.params
    form = p["form"]
    if form == "add":
        return p["P"] + p["Q"]
    if form == "rev":
        return -p["P"]
    if form == "lin":
        return p["m"] * p["P"] + p["k"] * (p["b"] - p["a"])
    if form == "sym":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    ab = p["P"] - p["Q"]
    return {"a": ab, "b": -2 * ab, "c": p["P"] + p["m"] * (p["c"] - p["a"]), "d": quad(lambda t: t**3 + p["s"], -p["h"], p["h"])}


@verifies("3E")
def v_3E(g):
    p = g.params
    if p["form"] == "prim":
        return fn(p["f"])
    a, b, x0, y0, x1 = p["a"], p["b"], mp.mpf(sp.Rational(p["x0"])), p["y0"], mp.mpf(sp.Rational(p["x1"]))
    lo = mp.mpf(-b) / a
    root = lambda t: mp.sqrt(a * t + b)  # noqa: E731
    curve = lambda t: y0 + quad(root, x0, t) if t >= lo else mp.mpc(0, 1)  # noqa: E731
    return {"a": root, "b": curve, "c": curve(x1)}


@verifies("3F")
def v_3F(g):
    p = g.params
    if p["form"] == "area":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    if p["form"] == "split":
        a, b = p["a"], p["b"]
        return quad(lambda t: abs(t * (t - a)), 0, a, b)
    curve, line = fn(p["curve"]), fn(p["line"])
    cs = poly_coeffs(f"({p['curve']}) - ({p['line']})")
    pts = real_roots(cs)
    return {"a": pts, "b": quad(lambda t: abs(curve(t) - line(t)), pts[0], pts[1])}


@verifies("3G")
def v_3G(g):
    p = g.params
    if p["form"] == "table":
        h, ys = mp.mpf(sp.Rational(p["h"])), p["ys"]
        return h / 2 * (ys[0] + 2 * ys[1] + ys[2])
    if p["form"] == "fn":
        f, h, a = fn(p["f"]), mp.mpf(sp.Rational(p["h"])), p["lo"]
        ys = [f(a + i * h) for i in range(p["n"] + 1)]
        return h / 2 * (ys[0] + 2 * sum(ys[1:-1]) + ys[-1])
    c, s_, b = p["c"], p["s"], p["b"]
    f = lambda t: c + s_ * t * t  # noqa: E731
    h = mp.mpf(b) / 4
    ys = [f(i * h) for i in range(5)]
    T = h / 2 * (ys[0] + 2 * sum(ys[1:-1]) + ys[-1])
    exact = quad(f, 0, b)
    return {"a": T, "b": exact, "c": "A" if T > exact else "B"}


@verifies("3H")
def v_3H(g):
    p = g.params
    if p["form"] == "prim":
        return fn(p["f"])
    b, m, c = p["b"], p["m"], p["c"]
    return {"a": lambda t: mp.diff(lambda u: (u * u + b) ** m, t), "b": lambda t: t * (t * t + b) ** (m - 1),
            "c": quad(lambda t: t * (t * t + b) ** (m - 1), 0, c)}


# ---------------------------------------------------------------- chapters 4-5 ---
def dfun(f, n=1):
    return lambda t: mp.diff(f, t, n)


def froot(f, a, b):
    """A root of f in [a, b] by bisection (independent of any algebra)."""
    fa = f(a)
    for _ in range(70):
        m = (a + b) / 2
        fm = f(m)
        if (fm > 0) == (fa > 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2


@verifies("4A")
def v_4A(g):
    p = g.params
    if p["form"] == "simp":
        return lambda t: mp.exp(p["a"] * t) * mp.exp(p["b"] * t) / mp.exp(p["c"] * t)
    if p["form"] == "solve":
        return froot(lambda t: mp.exp(p["a"] * t) - p["k"], -10, 10)
    if p["form"] == "quad":
        us = [u for u in real_roots([mp.mpf(1), mp.mpf(p["b1"]), mp.mpf(p["c1"])]) if u > 0]
        xs = [froot(lambda t, u=u: mp.exp(t) - u, -20, 20) for u in us]
        return xs[0] if g.answer["type"] == "num" else xs
    A, s_, c = p["A"], p["s"], p["c"]
    f = lambda t: A * mp.exp(s_ * t) + c  # noqa: E731
    far = f(-60 if s_ > 0 else 60)
    return {"a": f(0), "b": far, "c": [(c, None)] if A > 0 else [(None, c)], "d": froot(f, -30, 30)}


@verifies("4B")
def v_4B(g):
    p = g.params
    if p["form"] == "diff":
        return dfun(fn(p["f"]))
    B, C = -(p["p"] + p["q"]), p["p"] * p["q"]
    ks = real_roots([mp.mpf(1), mp.mpf(B), mp.mpf(C)])
    for kv in ks:  # each k really solves y'' + B y' + C y = 0 for y = e^{kx}
        y = lambda t, kv=kv: mp.exp(kv * t)  # noqa: E731
        assert abs(mp.diff(y, 0.7, 2) + B * mp.diff(y, 0.7) + C * y(0.7)) < 1e-6
    return {"c": ks}


@verifies("4C")
def v_4C(g):
    p = g.params
    if p["form"] == "tangent":
        f = lambda t: p["A"] * mp.exp(p["a"] * t)  # noqa: E731
        return lambda t: f(0) + mp.diff(f, 0) * t
    if p["form"] == "stat":
        f = lambda t: (t + p["c"]) * mp.exp(p["a"] * t)  # noqa: E731
        xs = froot(dfun(f), -p["c"] - 1 / mp.mpf(p["a"]) - 0.9, -p["c"] - 1 / mp.mpf(p["a"]) + 0.8)
        return [xs, f(xs)]
    s_, c = p["s"], p["c"]
    f = lambda t: s_ * (t - c) * mp.exp(t)  # noqa: E731
    xs = froot(dfun(f), c - 3, c + 0.5)
    x0 = froot(f, c - 0.5, c + 0.7)
    return {"a": dfun(f), "b": [xs, f(xs)], "c": "B" if mp.diff(f, xs, 2) > 0 else "A", "d": lambda t: mp.diff(f, x0) * (t - x0)}


@verifies("4D")
def v_4D(g):
    p = g.params
    if p["form"] == "prim":
        return fn(p["f"])
    if p["form"] == "def":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    a = p["a"]
    return {"a": dfun(lambda t: t * mp.exp(a * t)), "b": lambda t: t * mp.exp(a * t), "c": quad(lambda t: t * mp.exp(a * t), 0, 1)}


@verifies("4E")
def v_4E(g):
    p = g.params
    if p["form"] == "area":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    m = p["m"]
    if p["form"] == "line":
        xm = froot(lambda t: mp.exp(t) - m, 0, 5)
        return quad(lambda t: m - mp.exp(t), 0, xm)
    xp = froot(lambda t: mp.exp(2 * t) - m * mp.exp(t), 0.01, 5)
    return {"a": xp, "b": quad(lambda t: abs(m * mp.exp(t) - mp.exp(2 * t)), 0, xp)}


@verifies("4F")
def v_4F(g):
    p = g.params
    if p["form"] == "diff":
        return dfun(fn(p["f"]))
    if p["form"] == "prim":
        return fn(p["f"])
    if p["form"] == "def":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    a = p["a"]
    f = lambda t: mp.mpf(a) ** t  # noqa: E731
    slope = mp.diff(f, 0)
    return {"a": froot(lambda kv: mp.exp(kv) - a, 0, 5), "b": dfun(f), "c": lambda t: f(0) + slope * t, "d": -f(0) / slope}


@verifies("5A")
def v_5A(g):
    p = g.params
    if p["form"] == "laws":
        return mp.log(p["a"]) + mp.log(p["b"]) - mp.log(p["c"])
    if p["form"] == "solve":
        return froot(lambda t: p["A"] * mp.log(t + p["a"]) - p["b"], -p["a"] + 1e-12, 1000)
    if p["form"] == "eq":
        return froot(lambda t: mp.log(t) + mp.log(t + p["a"]) - mp.log(p["c"]), 1e-9, 100)
    h, kv = p["h"], p["k"]
    f = lambda t: mp.log(t - h) + kv  # noqa: E731
    return {"a": [(h, None)], "b": h, "c": froot(f, h + 1e-15, h + 100), "d": froot(lambda t: f(t) - (kv + 2), h + 1e-12, h + 100)}


@verifies("5B")
def v_5B(g):
    p = g.params
    if p["form"] == "diff":
        return dfun(fn(p["f"]))
    a, b = p["a"], p["b"]
    f = lambda t: a * mp.log(t) - b * t  # noqa: E731
    xs = froot(dfun(f), 0.01, 50)
    return {"a": dfun(f), "b": [xs, f(xs)], "c": "A" if mp.diff(f, xs, 2) < 0 else "B", "d": lambda t: f(1) + mp.diff(f, 1) * (t - 1)}


@verifies("5C")
def v_5C(g):
    p = g.params
    if p["form"] == "grad":
        return mp.diff(lambda t: p["A"] * mp.log(p["a"] * t), p["c"])
    if p["form"] == "tangent":
        a = p["a"]
        return lambda t: mp.log(a) + mp.diff(mp.log, a) * (t - a)
    c, q = p["c"], p["p"]
    f = lambda t: mp.log(t) + c  # noqa: E731
    m = mp.diff(f, q)
    return {"a": m, "b": lambda t: f(q) + m * (t - q), "c": lambda t: f(q) - (t - q) / m}


@verifies("5D")
def v_5D(g):
    p = g.params
    if p["form"] == "prim":
        return fn(p["f"])
    if p["form"] == "def":
        return quad(fn(p["f"]), p["lo"], p["hi"])
    a, m = p["a"], p["m"]
    return {"a": dfun(lambda t: mp.log(t * t + a)), "b": lambda t: t / (t * t + a), "c": quad(lambda t: t / (t * t + a), 0, m)}


@verifies("5E")
def v_5E(g):
    p = g.params
    if p["form"] == "area":
        return quad(fn(p["f"]), p["lo"], stored_num(p["hi"]))
    q1, q2 = p["p"], p["q"]
    s_, kv = q1 + q2, q1 * q2
    xs = real_roots([mp.mpf(-1), mp.mpf(s_), mp.mpf(-kv)])  # (s - x) - k/x = 0, times x
    return {"a": xs, "b": quad(lambda t: (s_ - t) - kv / t, xs[0], xs[1])}


@verifies("5F")
def v_5F(g):
    p = g.params
    if p["form"] == "diff":
        return dfun(fn(p["f"]))
    a, c = p["a"], p["c"]
    f = lambda t: mp.log(t, a)  # noqa: E731
    return {"a": f, "b": mp.diff(f, c), "c": lambda t: f(a) + mp.diff(f, a) * (t - a)}


# ------------------------------------------------------------------- chapter 6 ---
def roots_on(f, lo, hi, n=800):
    """All sign-change roots of f on [lo, hi], by a grid then bisection."""
    grid = [lo + (hi - lo) * mp.mpf(i) / n for i in range(n + 1)]
    return [froot(f, a, b) for a, b in zip(grid, grid[1:]) if f(a) * f(b) < 0]


@verifies("6A")
def v_6A(g):
    p = g.params
    if p["form"] == "ap":
        a, b = stored_num(p["a"]), stored_num(p["b"])
        f = lambda t: a * mp.sin(b * t)  # noqa: E731
        peaks = [t for t in roots_on(dfun(f), 0.0123, 40, 400) if mp.diff(f, t, 2) < 0]
        return {"a": f(peaks[0]), "b": peaks[1] - peaks[0]}
    if p["form"] == "fit":
        hi, lo, T = p["hi"], p["lo"], p["T"]
        return {"a": (hi - lo) / mp.mpf(2), "b": 2 * mp.pi / T, "c": (hi + lo) / mp.mpf(2)}
    dv, a, s_, T, m, c = p["d"], p["a"], p["s"], p["T"], p["m"], stored_num(p["c"])
    D = lambda t: dv + s_ * a * mp.cos(2 * mp.pi * t / T)  # noqa: E731
    level = dv + a * c
    cuts = [mp.mpf(0)] + roots_on(lambda t: D(t) - level, mp.mpf(T) / 1e6, T * (1 - 1e-6), 97) + [mp.mpf(T)]
    dur = sum(b - a_ for a_, b in zip(cuts, cuts[1:]) if D((a_ + b) / 2) >= level)
    peaks = [t for t in roots_on(dfun(D), T * 0.01, T * 1.01, 97) if mp.diff(D, t, 2) < 0]
    return {"a": D(m), "b": D(peaks[0]), "c": peaks[0], "d": dur}


def _close_grid(v, w):
    return abs(v - w) < 2e-3


@verifies("6B")
def v_6B(g):
    p = g.params
    if p["form"] == "diff":
        return dfun(fn(p["f"]))
    f = fn(p["f"])
    x0 = stored_num(p["x0"])
    return {"a": dfun(f), "b": dfun(f, 2), "c": mp.diff(f, x0), "d": mp.diff(f, x0, 2)}


@verifies("6C")
def v_6C(g):
    p = g.params
    f = fn(p["f"])
    if p["form"] == "grad":
        return mp.diff(f, stored_num(p["x0"]))
    if p["form"] == "tangent":
        x0 = stored_num(p["x0"])
        return lambda t: f(x0) + mp.diff(f, x0) * (t - x0)
    fp = dfun(f)
    sts = roots_on(fp, 0, 2 * mp.pi, 601)
    mx = [s_ for s_ in sts if mp.diff(f, s_, 2) < 0][0]
    return {"a": fp, "b": sts, "c": "A" if mp.diff(f, sts[0], 2) < 0 else "B", "d": f(mx)}


@verifies("6D")
def v_6D(g):
    p = g.params
    if p["form"] == "prim":
        return fn(p["f"])
    if p["form"] == "def":
        return quad(fn(p["f"]), stored_num(p["lo"]), stored_num(p["hi"]))
    a, hi = p["a"], stored_num(p["hi"])
    g_ = (lambda t: t * mp.sin(a * t)) if p["kind"] == "sin" else (lambda t: t * mp.cos(a * t))
    h_ = (lambda t: t * mp.cos(a * t)) if p["kind"] == "sin" else (lambda t: t * mp.sin(a * t))
    return {"a": dfun(g_), "b": h_, "c": quad(h_, 0, hi)}


@verifies("6E")
def v_6E(g):
    p = g.params
    if p["form"] in ("area", "total"):
        f = fn(p["f"])
        hi = stored_num(p["hi"])
        return quad(lambda t: abs(f(t)), *[hi * i / 8 for i in range(9)])
    if p["form"] == "between":
        A = p["A"]
        return quad(lambda t: abs(A * mp.sin(t) - A * mp.cos(t)), mp.pi / 4, 3 * mp.pi / 4, 5 * mp.pi / 4)
    kv, v = p["k"], stored_num(p["v"])
    h = lambda t: kv * mp.sin(t) - kv * v  # noqa: E731
    xs = roots_on(h, 0, mp.pi, 601)
    return {"a": xs, "b": quad(h, xs[0], xs[1])}


# ------------------------------------------------------------------- chapter 7 ---
def tfn(expr: str):
    return fn(expr, "t")


def roots_of(f, lo, hi, n=600):
    return [r_ for r_ in roots_on(f, lo, hi, n)]


def distance(v, T, n=600):
    """Total distance travelled on [0, T] = integral of |v|, split at every sign change of v."""
    cuts = [mp.mpf(0)] + roots_of(v, mp.mpf("1e-9"), T, n) + [mp.mpf(T)]
    return sum(abs(quad(v, a, b)) for a, b in zip(cuts, cuts[1:]))


@verifies("7A")
def v_7A(g):
    p = g.params
    xf = tfn(p["x"])
    v = dfun(xf)
    if p["form"] == "v":
        return v(p["m"])
    if p["form"] == "a":
        return mp.diff(xf, p["m"], 2)
    rest = roots_of(v, mp.mpf("1e-9"), 30)
    if p["form"] == "rest":
        return {"a": rest, "b": mp.diff(xf, rest[0], 2)}
    return {"a": v(0), "b": rest, "c": distance(v, p["T"]), "d": mp.diff(xf, p["m"], 2)}


@verifies("7B")
def v_7B(g):
    p = g.params
    if p["form"] == "x":
        vf = tfn(p["v"])
        return lambda s_: p["x0"] + quad(vf, 0, s_)
    if p["form"] == "acc":
        af = tfn(p["a"])
        vf = lambda s_: p["v0"] + quad(af, 0, s_)  # noqa: E731
        return p["x0"] + quad(vf, 0, p["T"])
    if p["form"] == "expv":
        return quad(lambda s_: p["A"] * mp.exp(-p["k"] * s_), 0, p["T"])
    kf, a, b, T = p["k"], p["p"], p["q"], p["T"]
    vf = lambda s_: kf * (s_ - a) * (s_ - b)  # noqa: E731
    return {"a": lambda s_: quad(vf, 0, s_), "b": roots_of(vf, mp.mpf("1e-9"), 30), "c": distance(vf, T)}


@verifies("7C")
def v_7C(g):
    p = g.params
    if p["form"] == "rate":
        return mp.diff(tfn(p["V"]), p["m"])
    if p["form"] == "drain":
        A, T, m = p["A"], p["T"], p["m"]
        V = lambda s_: A * (T - s_) ** 2  # noqa: E731
        out = lambda s_: -mp.diff(V, s_)  # noqa: E731
        return {"a": out(m), "b": V(0), "c": froot(lambda s_: out(s_) - out(0) / 2, 0, T)}
    P_ = tfn(p["P"])
    dP = dfun(P_)
    end = [r_ for r_ in roots_of(dP, mp.mpf("1e-6"), 40)][0]
    assert dP(end / 2) > 0
    fast = froot(dfun(P_, 2), mp.mpf("1e-9"), end)
    assert mp.diff(P_, fast, 3) < 0
    return {"a": dP(p["m"]), "b": [(0.0, float(end))], "c": fast}


@verifies("7D")
def v_7D(g):
    p = g.params
    if p["form"] == "fill":
        return quad(tfn(p["R"]), 0, p["T"])
    if p["form"] == "stop":
        c, kv, V0 = p["c"], p["k"], p["V0"]
        R = lambda s_: c - kv * s_  # noqa: E731
        ts = froot(R, 0, 1000)
        return {"a": ts, "b": V0 + quad(R, 0, ts)}
    a, T, V0, m = p["a"], p["T"], p["V0"], p["m"]
    R = lambda s_: a * s_ * (T - s_)  # noqa: E731
    return {"a": froot(dfun(R), 0, T), "b": lambda s_: V0 + quad(R, 0, s_), "c": V0 + quad(R, 0, m), "d": quad(R, 0, T)}


@verifies("7E")
def v_7E(g):
    p = g.params
    if p["form"] == "eval":
        return p["N0"] * mp.exp(stored_num(p["k"]) * p["T"])
    if p["form"] == "half":
        return froot(lambda kv: mp.exp(-kv * p["h"]) - mp.mpf(1) / 2, mp.mpf("1e-9"), 10)
    if p["form"] == "k":
        return froot(lambda kv: p["N0"] * mp.exp(kv * p["t1"]) - p["N0"] * stored_num(p["f"]), mp.mpf("1e-9"), 10)
    if p["form"] == "growth":
        N0, f, t1, T, M = p["N0"], stored_num(p["f"]), p["t1"], p["T"], p["M"]
        kv = froot(lambda k_: N0 * mp.exp(k_ * t1) - N0 * f, mp.mpf("1e-9"), 10)
        Pf = lambda s_: N0 * mp.exp(kv * s_)  # noqa: E731
        tM = froot(lambda s_: Pf(s_) - M, 0, 1000)
        return {"a": kv, "b": Pf(T), "c": tM, "d": mp.diff(Pf, tM)}
    A, B, t1, T1, target = p["A"], p["B"], p["t1"], p["T1"], p["target"]
    Bv = (A + B) - A
    kv = froot(lambda k_: A + Bv * mp.exp(-k_ * t1) - T1, mp.mpf("1e-9"), 10)
    return {"a": Bv, "b": kv, "c": froot(lambda s_: A + Bv * mp.exp(-kv * s_) - target, 0, 10000)}


# ------------------------------------------------------------------- chapter 8 ---
# Finance answers are re-derived by simulating the account period by period in exact rational
# arithmetic, and unknown payments / rates by bisection — never by the closed-form GP formulas.
Fr = Fraction


def rate(R, m=1):
    return Fr(str(R)) / (100 * m)


def first_where(cond, limit=5000):
    for n_ in range(1, limit):
        if cond(n_):
            return n_
    raise AssertionError("no n found")


def account(start, r_, pay, periods, due=False):
    """Balance after ``periods``: each period interest at r_ then ``pay`` added (negative = withdrawal);
    with due=True the deposit is made before the interest."""
    b = Fr(start)
    for _ in range(periods):
        b = (b + pay) * (1 + r_) if due else b * (1 + r_) + pay
    return b


def mq(v):
    """A Fraction (or int) as an mpmath number."""
    v = Fr(v)
    return mp.mpf(v.numerator) / v.denominator


def bisect_mp(f, lo, hi, it=200):
    lo, hi = mq(lo), mq(hi)
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def cents_of(v, dp=2):
    from decimal import ROUND_HALF_UP, Decimal

    return Fr(str(Decimal(str(mp.nstr(mp.mpf(v), 40))).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)))


def paid_out(n_, P0, r_, W):
    """Number of full withdrawals W a fund P0 can make (interest first, then the withdrawal)."""
    cnt, b = 0, Fr(P0)
    while b * (1 + r_) >= W:
        b = b * (1 + r_) - W
        cnt += 1
        assert cnt < n_
    return cnt


@verifies("8A")
def v_8A(g):
    p = g.params
    if p["form"] == "seats":
        return sum(p["a"] + i * p["d"] for i in range(p["n"]))
    if p["form"] == "salary":
        return account(p["S0"], rate(p["p"]), 0, p["yr"] - 1)
    jobA = lambda y: p["a"] + (y - 1) * p["inc"]  # noqa: E731
    jobB = lambda y: account(p["b"], rate(p["p"]), 0, y - 1)  # noqa: E731
    totB = sum(jobB(y) for y in range(1, p["N"] + 1))
    if p["form"] == "compare":
        return {"a": sum(jobA(y) for y in range(1, p["N"] + 1)), "b": totB}
    return {"a": jobA(p["n1"]), "b": totB, "c": first_where(lambda y: jobB(y) > jobA(y))}


@verifies("8B")
def v_8B(g):
    p = g.params
    if p["form"] == "multiply":
        return first_where(lambda n_: account(1, rate(p["p"]), 0, n_) >= p["mult"])
    if p["form"] == "dep":
        val = lambda n_: account(p["V0"], -rate(p["p"]), 0, n_)  # noqa: E731
        return {"a": val(p["n1"]), "b": first_where(lambda n_: val(n_) < p["B"])}
    h, f, bound = Fr(p["h"]), Fr(p["f"]), Fr(p["bound"])
    rebound = lambda k_: h * f**k_  # noqa: E731
    travelled = mq(h) + 2 * mp.fsum(mq(rebound(k_)) for k_ in range(1, 400))
    return {"a": rebound(p["k"]), "b": first_where(lambda k_: rebound(k_) < bound), "c": travelled}


@verifies("8C")
def v_8C(g):
    p = g.params
    if p["form"] == "simple":
        return sum(p["P"] * rate(p["R"]) for _ in range(p["n"]))
    if p["form"] == "compound":
        return account(p["P"], rate(p["R"], p["m"]), 0, p["m"] * p["n"])
    if p["form"] == "rate":
        A = mp.mpf(p["A"])
        return 100 * bisect_mp(lambda r_: p["P"] * (1 + r_) ** p["n"] - A, 0, 1)
    return {"a": account(p["P"], rate(p["R"]), 0, p["n"]), "b": account(p["P"], rate(p["R"], 12), 0, 12 * p["n"]),
            "c": first_where(lambda n_: account(p["P"], rate(p["R"]), 0, n_) > p["mult"] * p["P"])}


@verifies("8D")
def v_8D(g):
    p = g.params
    if p["form"] == "fv":
        return account(0, rate(p["R"], p["m"]), p["M"], p["N"], due=p["due"])
    r_ = rate(p["R"], 12)
    if p["form"] == "target":
        unit = account(0, r_, 1, p["N"])  # the balance is linear in the deposit
        return bisect_mp(lambda M: M * mq(unit) - p["T"], 0, p["T"])
    return {"a": account(0, r_, p["M"], 3), "b": account(0, r_, p["M"], p["N"]),
            "c": first_where(lambda n_: account(0, r_, p["M"], n_) > p["T"])}


def _level_payment(P0, r_, N):
    """The payment that takes a balance P0 to zero in N periods, by bisection on the simulated balance."""
    end = lambda W: mq(account(P0, r_, 0, N)) - W * mq(account(0, r_, 1, N))  # noqa: E731
    return bisect_mp(end, 0, P0)


@verifies("8E")
def v_8E(g):
    p = g.params
    r_ = rate(p["R"], 12)
    if p["form"] == "A1":
        return account(p["P"], r_, -p["M"], 1)
    M = _level_payment(p["P"], r_, p["N"])
    if p["form"] == "M":
        return M
    Mr = cents_of(M)
    owing = account(p["P"], r_, -Mr, p["K"])
    assert abs(mq(owing) - (mq(account(p["P"], r_, 0, p["K"])) - M * mq(account(0, r_, 1, p["K"])))) <= mq(g.answer["parts"][3]["answer"]["tol"])
    return {"a": M, "b": account(p["P"], r_, -Mr, 1), "c": p["N"] * Mr - p["P"], "d": cents_of(mq(owing))}


@verifies("8F")
def v_8F(g):
    p = g.params
    if p["form"] == "B2":
        return account(p["P"], rate(p["R"], 12), -p["W"], 2)
    if p["form"] == "pv":
        r_ = rate(p["R"])
        # the fund X that is exactly exhausted by n end-of-year payments W
        return bisect_mp(lambda X: X * mq(account(1, r_, 0, p["n"])) - p["W"] * mq(account(0, r_, 1, p["n"])), 0, p["W"] * p["n"])
    if p["form"] == "W":
        return _level_payment(p["P"], rate(p["R"], 12), p["N"])
    if p["form"] == "count":
        return paid_out(5000, p["P"], rate(p["R"], 12), p["W"])
    r_ = rate(p["R"])
    F = account(0, r_, p["C"], p["N1"])
    return {"a": F, "b": _level_payment(F, r_, p["N2"]), "c": paid_out(500, F, r_, p["W2"])}


# ---------------------------------------------------------------- chapters 9-10 ---
# Discrete answers by enumerating outcomes (or by the definition Var = E[(X - mu)^2]); continuous ones by
# numerical integration and bisection; normal ones from our own 4-decimal-place table of Phi.
import itertools  # noqa: E402


def phi_tab(z) -> Fraction:
    """P(Z <= z) to 4 dp as a table gives it (negative z by symmetry, as students do)."""
    from decimal import ROUND_HALF_UP, Decimal

    z = Fr(str(z))
    if z < 0:
        return 1 - phi_tab(-z)
    with mp.workdps(40):
        v = mp.ncdf(mq(z))
        return Fr(str(Decimal(mp.nstr(v, 30)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)))


EMPIRICAL = {1: Fr(68, 100), 2: Fr(95, 100), 3: Fr(997, 1000)}


def dist_var(vals, probs):
    mu = sum(v * p for v, p in zip(vals, probs))
    return sum((v - mu) ** 2 * p for v, p in zip(vals, probs))


def pdf_k(f, lo, hi):
    return 1 / mp.quad(f, [lo, hi])


def two_marbles(R, B):
    """Distribution of the number of red marbles in two draws without replacement, by enumeration."""
    balls = ["r"] * R + ["b"] * B
    pairs = list(itertools.permutations(range(len(balls)), 2))
    count = {0: 0, 1: 0, 2: 0}
    for i, j in pairs:
        count[(balls[i] == "r") + (balls[j] == "r")] += 1
    return {kk: Fr(c, len(pairs)) for kk, c in count.items()}


@verifies("9A")
def v_9A(g):
    p = g.params
    if p["form"] == "k":
        k_ = sp.Symbol("k")
        return sp.solve(sum(c * k_ for c in p["cs"]) - 1, k_)[0]
    if p["form"] == "event":
        probs = [Fr(w, 20) for w in p["ws"]]
        cut = p["xs"][p["j"]] if p["kind"] == "ge" else p["xs"][p["j"] + 1]
        keep = (lambda v: v >= cut) if p["kind"] == "ge" else (lambda v: v < cut)
        return sum(pr for v, pr in zip(p["xs"], probs) if keep(v))
    if p["form"] == "kq":
        k_ = sp.Symbol("k")
        cells = [c * k_ for c in p["cs"]]
        cells.insert(p["pos"], p["q"] * k_**2)
        roots = [rt for rt in sp.solve(sum(cells) - 1, k_) if all(0 <= c.subs(k_, rt) <= 1 for c in cells)]
        assert len(roots) == 1
        probs = [c.subs(k_, roots[0]) for c in cells]
        return {"a": roots[0], "b": sum(probs[p["j"]:])}
    if p["form"] == "bag":
        dist = two_marbles(p["R"], p["B"])
        return {"a": dist[0], "b": dist[1], "c": dist[1] + dist[2], "d": dist[2] / (dist[1] + dist[2])}
    nd = p["nd"]
    rolls = list(itertools.product(range(1, nd + 1), repeat=2))
    pmf = {v: Fr(sum(1 for a, b in rolls if max(a, b) == v), len(rolls)) for v in range(1, nd + 1)}
    slope = pmf[2] - pmf[1]
    assert all(pmf[v] == pmf[1] + (v - 1) * slope for v in pmf)  # P(X = k) is linear in k
    ge = sum(pr for v, pr in pmf.items() if v >= p["m"])
    return {"a": pmf[p["a"]], "b": lambda kv: mq(pmf[1]) + (kv - 1) * mq(slope), "c": ge, "d": pmf[nd] / ge}


@verifies("9B")
def v_9B(g):
    p = g.params
    if p["form"] == "table":
        return sum(v * Fr(w, 20) for v, w in zip(p["xs"], p["ws"]))
    if p["form"] == "lin":
        mu = Fr(p["mu"])
        return sum((p["a"] * v + p["b"]) * Fr(1, 2) for v in (mu - 3, mu + 3))
    if p["form"] == "game":
        prize = lambda face: p["W1"] if face == 6 else (p["W2"] if face in (4, 5) else 0)  # noqa: E731
        ep = sum(Fr(prize(f_), 6) for f_ in range(1, 7))
        return {"a": ep, "b": ep - p["c"], "c": p["n"] * (ep - p["c"])}
    if p["form"] == "ab":
        a_, b_ = sp.symbols("a b")
        probs = [sp.Rational(w, 10) for w in p["ws"]]
        mean = sum(v * pr for v, pr in zip(p["xs"], probs))
        probs[p["i"]], probs[p["j"]] = a_, b_
        sol = sp.solve([sum(probs) - 1, sum(v * pr for v, pr in zip(p["xs"], probs)) - mean], [a_, b_])
        return [sol[a_], sol[b_]]
    dist = two_marbles(p["R"], p["B"])
    ep = p["A1"] * dist[2] + p["A2"] * dist[1]
    return {"a": dist[2], "b": dist[1], "c": ep, "d": ep, "e": p["n"] * (p["c"] - ep)}


@verifies("9C")
def v_9C(g):
    p = g.params
    if p["form"] == "fromE":
        return Fr(p["s2"]) - Fr(p["mu"]) ** 2
    if p["form"] == "lin":
        s = mp.sqrt(p["var"])
        return dist_var([p["a"] * v + p["b"] for v in (-s, s)], [mp.mpf(1) / 2] * 2)
    if p["form"] == "table":
        v = dist_var(p["xs"], [Fr(w, 20) for w in p["ws"]])
        return mp.sqrt(mq(v)) if p["sd"] else v
    k_ = Fr(1, sum(p["cs"]))
    probs = [c * k_ for c in p["cs"]]
    ys = [p["a"] * v + p["b"] for v in p["xs"]]
    return {"a": k_, "b": sum(v * pr for v, pr in zip(p["xs"], probs)), "c": dist_var(p["xs"], probs), "d": mp.sqrt(mq(dist_var(ys, probs)))}


@verifies("10A")
def v_10A(g):
    p = g.params
    fs = p["fs"]
    n_ = sum(fs)
    if p["form"] == "cf":
        return sum(fs[: p["j"] + 1])
    if p["form"] == "rel":
        return Fr(sum(fs[: p["j"] + 1]), n_)
    b = p["bounds"]
    mean = sum(f * Fr(lo + hi, 2) for f, lo, hi in zip(fs, b, b[1:])) / n_
    if p["form"] == "mean":
        return {"a": mean, "b": Fr(sum(f for f, lo in zip(fs, b) if lo >= b[p["j"]]), n_)}
    pts = [(b[0], 0)] + [(b[i + 1], sum(fs[: i + 1])) for i in range(5)]

    def ogive(xv):
        for (x0, c0), (x1, c1) in zip(pts, pts[1:]):
            if x0 <= xv <= x1:
                return c0 + (c1 - c0) * (xv - x0) / (x1 - x0)
        raise AssertionError
    return {"a": mean, "b": dict(pts)[b[p["j"] + 1]], "c": bisect_mp(lambda xv: ogive(xv) - mp.mpf(n_) / 2, b[0], b[5])}


@verifies("10B")
def v_10B(g):
    p = g.params
    f_ = p["form"]
    if f_ in ("k", "P", "cdf", "pow"):
        n_, a_ = p["n"], p["a"]
        k_ = pdf_k(lambda s_: s_**n_, 0, a_)
        F = lambda s_: k_ * mp.quad(lambda u: u**n_, [0, s_])  # noqa: E731
        if f_ == "k":
            return k_
        if f_ == "P":
            return F(p["b"])
        if f_ == "cdf":
            return {"a": F, "b": F(p["b2"]) - F(p["b1"])}
        return {"a": k_, "b": F, "c": F(p["b2"]) - F(p["b1"]), "d": bisect_mp(lambda s_: F(s_) - mp.mpf(1) / 2, 0, a_)}
    if f_ == "quad":
        a_ = p["a"]
        k_ = pdf_k(lambda s_: s_ * (a_ - s_), 0, a_)
        return {"a": k_, "b": k_ * mp.quad(lambda s_: s_ * (a_ - s_), [0, p["b"]])}
    lam = mq(Fr(p["lam"]))
    if g.difficulty == 1:
        return mp.quad(lambda s_: lam * mp.exp(-lam * s_), [p["b"], mp.inf])
    k_ = pdf_k(lambda s_: mp.exp(-lam * s_), 0, mp.inf)
    F = lambda s_: k_ * mp.quad(lambda u: mp.exp(-lam * u), [0, s_])  # noqa: E731
    return {"a": k_, "b": F, "c": 1 - F(p["b"]), "d": bisect_mp(lambda s_: F(s_) - mp.mpf(1) / 2, 0, 100)}


def _moments(f, lo, hi):
    m1 = mp.quad(lambda s_: s_ * f(s_), [lo, hi])
    return m1, mp.quad(lambda s_: (s_ - m1) ** 2 * f(s_), [lo, hi])


@verifies("10C")
def v_10C(g):
    p = g.params
    f_ = p["form"]
    if f_ == "uni":
        a_, b_ = p["a"], p["b"]
        m1, var = _moments(lambda s_: mp.mpf(1) / (b_ - a_), a_, b_)
        return m1 if g.difficulty == 1 else {"a": m1, "b": var}
    if f_ == "lin":
        return _moments(lambda s_: 2 * s_ / mp.mpf(p["a"]) ** 2, 0, p["a"])[0]
    a_ = p["a"]
    shape = (lambda s_: s_ ** p["n"]) if f_ == "pow" else (lambda s_: s_ * (a_ - s_))
    k_ = pdf_k(shape, 0, a_)
    m1, var = _moments(lambda s_: k_ * shape(s_), 0, a_)
    if g.difficulty == 2:
        return {"a": m1, "b": var}
    upto = m1 if f_ == "pow" else mq(Fr(p["b"]))
    return {"a": k_, "b": m1, "c": var, "d": k_ * mp.quad(shape, [0, upto])}


def emp(k1, k2):
    return (EMPIRICAL[k1] + EMPIRICAL[k2]) / 2


@verifies("10D")
def v_10D(g):
    p = g.params
    f_ = p["form"]
    if f_ == "emp":
        return 100 * emp(p["k1"], p["k2"])
    if f_ == "upper":
        return 1 - phi_tab(p["z"])
    if f_ == "neg":
        return phi_tab("-" + p["z"])
    if f_ == "symm":
        return phi_tab(p["z"]) - phi_tab("-" + p["z"])
    if f_ == "between":
        return phi_tab(p["z2"]) - phi_tab(p["z1"])
    if f_ == "straddle":
        return phi_tab(p["z2"]) - phi_tab("-" + p["z1"])
    za, zb, zc = p["za"], p["zb"], p["zc"]
    return {"a": 1 - phi_tab(zb), "b": phi_tab(zb) - phi_tab("-" + za), "c": phi_tab("-" + zc) + 1 - phi_tab(zc),
            "d": (1 - phi_tab(zb)) / Fr(1, 2)}


def zs(xv, mu, sigma):
    return Fr(xv - mu, sigma)


@verifies("10E")
def v_10E(g):
    p = g.params
    f_ = p["form"]
    if f_ == "emp":
        return 100 * emp(p["k1"], p["k2"])
    if f_ == "z":
        return zs(p["x"], p["mu"], p["sigma"])
    if f_ == "x":
        return p["mu"] + Fr(p["zz"]) * p["sigma"]
    mu, s = p["mu"], p["sigma"]
    if f_ == "between":
        return phi_tab(zs(p["x2"], mu, s)) - phi_tab(zs(p["x1"], mu, s))
    za = zs(p["xa"], mu, s)
    tail = 1 - phi_tab(za)
    return {"a": za, "b": tail, "c": phi_tab(za) - phi_tab(zs(p["xb"], mu, s)), "d": p["N"] * tail}


@verifies("10F")
def v_10F(g):
    p = g.params
    f_ = p["form"]
    if f_ == "count":
        return p["N"] * emp(p["k1"], p["k2"])
    if f_ == "cut":
        return p["mu"] + Fr(p["zq"]) * p["sigma"]
    if f_ == "qc":
        mu, s = p["mu"], p["sigma"]
        rej = phi_tab(zs(p["lo"], mu, s)) + 1 - phi_tab(zs(p["hi"], mu, s))
        return {"a": rej, "b": p["N"] * rej}
    if f_ == "mean":
        return bisect_mp(lambda m: (p["a"] - m) / p["sigma"] - mq(Fr(p["zq"])), -1000, 5000)
    mu, s = p["mu"], p["sigma"]
    zq = Fr(p["zq"])
    return {"a": 1 - phi_tab(zs(p["xa"], mu, s)), "b": 100 * EMPIRICAL[p["k"]], "c": mu + zq * s,
            "d": bisect_mp(lambda m: (p["xa"] - m) / s - mq(zq), -1000, 5000)}


def test_quoted_normal_quantiles_are_right():
    from app.services.maths_tpl_ch9_10 import ZQ

    for top, zq in ZQ:
        assert abs(mp.ncdf(mp.mpf(zq)) - (1 - mp.mpf(top) / 100)) < 0.001, (top, zq)


# --------------------------------------------------------------------- tests ---
def test_every_plan_subtopic_has_its_own_v2_template():
    missing = [c for c in plan_codes() if c not in ENRICHMENT | DEFERRED and c not in mt.V2_CODES]
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
