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
    a = p["a"]
    return {"a": dfun(lambda t: t * mp.sin(a * t)), "b": lambda t: t * mp.cos(a * t), "c": quad(lambda t: t * mp.cos(a * t), 0, mp.pi / (2 * a))}


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
