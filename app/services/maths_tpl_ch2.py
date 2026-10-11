"""Chapter 2 — Curve-sketching using the derivative (owner: maths).

Only Year 11 calculus (power, chain, product and quotient rules on algebraic functions) is used:
exponential, logarithmic and trigonometric calculus come later in the learning sequence."""
from __future__ import annotations

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_iv, A_mcq, A_num, A_parts, A_prim, A_set, A_units, Generated, L, P, Rng, S, cp, err, mcq_options, multipart,
    nonzero, pick, pl, region, x,
)

STAT = "stationary points"
CONC = "concavity"
DIFF = "differentiation rules"
CD = "continuity and differentiability"
INTG = "integration rules"
kk_ = sp.Symbol("k")


def _cubic(r: Rng, lo: int = -4, hi: int = 5, gap: int = 2):
    """f with f'(x) = s*m*(x - p)(x - q), integer coefficients; p < q."""
    while True:
        p, q = sorted(r.sample(range(lo, hi + 1), 2))
        if q - p >= gap:
            break
    m = 3 if (p + q) % 2 == 0 else 6
    s = pick(r, [1, 1, -1])
    c = r.randint(-8, 8)
    fp = s * m * (x - p) * (x - q)
    f = sp.expand(sp.integrate(fp, x) + c)
    return f, sp.expand(fp), p, q, s


def _fx(f, v):
    return sp.expand(f).subs(x, v)


# ----------------------------------------------------------------------- 2A ---
def t_2A(r: Rng, d: int) -> Generated:
    if d == 1:
        a = pick(r, [1, 2, 3, -1, -2])
        h = nonzero(r, -5, 5)
        c = r.randint(-9, 9)
        f = a * x**2 - 2 * a * h * x + c
        up = a > 0
        ans = [(h, None, False, False)] if up else [(None, h, False, False)]
        other = [(None, h, False, False)] if up else [(h, None, False, False)]
        flip = [(-h, None, False, False)] if up else [(None, -h, False, False)]
        return Generated(
            f"For which values of \\(x\\) is the function \\(f(x) = {L(f)}\\) increasing?",
            A_iv(ans, ends="ignore"), 2, 1,
            [f"\\(f'(x) = {L(sp.diff(f, x))}\\).",
             f"\\(f\\) is increasing where \\(f'(x) > 0\\): \\({L(sp.diff(f, x))} > 0\\), so \\({region(ans)}\\)."],
            "A function is increasing where its derivative is positive and decreasing where it is negative.",
            "Write the inequality \\(f'(x) > 0\\) before solving it; when you divide by a negative number, reverse the inequality.",
            quicker=f"The parabola is concave {'up' if up else 'down'} with axis \\(x = {h}\\), so it rises to the {'right' if up else 'left'} of its vertex.",
            common_errors=[err(region(other), "interpretation", "inequality direction", "That is where \\(f\\) is decreasing (\\(f'(x) < 0\\)).", step=2),
                           err(region(flip), "careless error", "sign error", "Sign error when solving \\(f'(x) > 0\\).", step=2)],
            skill="Find where a function is increasing from the sign of its derivative.",
            params={"form": "quad", "a": a, "h": h, "c": c},
        )
    if d == 2:
        if r.random() < 0.5:
            f, fp, p, q, s = _cubic(r)
            dec = [(p, q, False, False)] if s > 0 else [(None, p, False, False), (q, None, False, False)]
            inc = [(None, p, False, False), (q, None, False, False)] if s > 0 else [(p, q, False, False)]
            return Generated(
                f"Find the values of \\(x\\) for which the curve \\(y = {L(f)}\\) is decreasing.",
                A_iv(dec, ends="ignore"), 3, 2,
                [f"\\(\\dfrac{{dy}}{{dx}} = {L(fp)} = {L(sp.factor(fp))}\\).",
                 f"\\(\\dfrac{{dy}}{{dx}} = 0\\) at \\(x = {p}\\) and \\(x = {q}\\); the derivative is a {'concave up' if s > 0 else 'concave down'} parabola.",
                 f"So \\(\\dfrac{{dy}}{{dx}} < 0\\) for \\({region(dec)}\\)."],
                "The curve decreases where \\(\\frac{dy}{dx} < 0\\); a quadratic derivative changes sign only at its zeros.",
                "Draw the sign diagram of \\(\\frac{dy}{dx}\\) (a quick sketch of the parabola) and read the region from it.",
                quicker="Sketch \\(y = \\frac{dy}{dx}\\) as a parabola through its zeros and shade where it lies below the axis.",
                common_errors=[err(region(inc), "interpretation", "inequality direction", "That is where the curve is increasing: decreasing needs \\(\\frac{dy}{dx} < 0\\).", step=3),
                               err(region([(-q, -p, False, False)] if s > 0 else [(None, -q, False, False), (-p, None, False, False)]),
                                   "careless error", "sign error", "Sign error: \\((x - a) = 0\\) gives \\(x = a\\), not \\(-a\\).", step=2)],
                skill="Find where a cubic is decreasing.",
                checkpoints=[cp(fp, "the derivative", step=1)],
                params={"form": "dec", "f": str(f), "p": p, "q": q, "s": s},
            )
        b = nonzero(r, -4, 4)
        m = nonzero(r, -3, 3)
        c = r.randint(-6, 6)
        kval = -3 * m * m - 2 * b * m
        f = x**3 + b * x**2 + kk_ * x + c
        ces = [err(3 * m * m + 2 * b * m, "careless error", "sign error", "Sign error when solving for \\(k\\).", step=2)]
        if m != 0 and m**3 + b * m * m + c != 0:
            ces.append(err(sp.Rational(-(m**3 + b * m * m + c), m), "conceptual", STAT,
                           "You set \\(y = 0\\). A stationary point needs \\(\\frac{dy}{dx} = 0\\).", step=1))
        return Generated(
            f"The curve \\(y = {pl(f)}\\) is stationary at \\(x = {m}\\). Find the value of the constant \\(k\\).",
            A_num(kval), 2, 2,
            [f"\\(\\dfrac{{dy}}{{dx}} = {pl(sp.diff(f, x))}\\), and it is zero at \\(x = {m}\\).",
             f"\\({L(sp.diff(f, x).subs(x, m))} = 0\\), so \\(k = {kval}\\)."],
            "'Stationary at a point' means the derivative is zero there.",
            "Differentiate first, then substitute; substituting into \\(y\\) itself is the most common mistake.",
            quicker="Write \\(y'(m) = 0\\) directly as a linear equation in \\(k\\).",
            common_errors=ces, skill="Use the condition for a stationary point to find a constant.",
            params={"form": "stat_k", "b": b, "m": m, "c": c, "k": kval},
        )
    f, fp, p, q, s = _cubic(r)
    inc = [(None, p, False, False), (q, None, False, False)] if s > 0 else [(p, q, False, False)]
    dec = [(p, q, False, False)] if s > 0 else [(None, p, False, False), (q, None, False, False)]
    text = multipart(f"Let \\(f(x) = {L(f)}\\).",
                     [("a", "Find \\(f'(x)\\).", 1), ("b", "Find the values of \\(x\\) at which \\(f\\) is stationary.", 2),
                      ("c", "For which values of \\(x\\) is \\(f\\) increasing?", 2)])
    steps = [f"(a) \\(f'(x) = {L(fp)}\\).",
             f"(b) \\(f'(x) = {L(sp.factor(fp))} = 0\\), so \\(x = {p}\\) or \\(x = {q}\\).",
             f"(c) \\(f'(x)\\) is a {'concave up' if s > 0 else 'concave down'} quadratic with zeros \\({p}\\) and \\({q}\\).",
             f"So \\(f'(x) > 0\\), and \\(f\\) is increasing, for \\({region(inc)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(fp)), P("b", 2, A_set([p, q])), P("c", 2, A_iv(inc, ends="ignore"))), 5, 3, steps,
        "The sign of \\(f'(x)\\) tells you where \\(f\\) increases, decreases or is stationary.",
        "In (c), justify the region with a sign diagram of \\(f'(x)\\) — 'by inspection' earns nothing.",
        quicker="Once \\(f'(x)\\) is factorised, the stationary points and the sign diagram come from the same line.",
        common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error solving \\((x - a)(x - b) = 0\\).", step=2, part="b"),
                       err(region(dec), "interpretation", "inequality direction", "That is where \\(f\\) is decreasing.", step=4, part="c"),
                       err(sp.expand(fp / 3) if fp.coeff(x, 2) % 3 == 0 else 2 * fp, "careless error", DIFF,
                           "Multiply each coefficient by its power when differentiating.", step=1, part="a")],
        skill="Analyse where a cubic increases, decreases and is stationary.",
        checkpoints=[cp(fp, "the derivative", step=1, part="b"), cp(fp, "the derivative", step=1, part="c")],
        params={"form": "parts", "f": str(f), "p": p, "q": q, "s": s},
    )


# ----------------------------------------------------------------------- 2B ---
def t_2B(r: Rng, d: int) -> Generated:
    if d == 1:
        f, fp, p, q, s = _cubic(r)
        return Generated(
            f"Find the \\(x\\)-coordinates of the stationary points of \\(y = {L(f)}\\).",
            A_set([p, q]), 2, 1,
            [f"\\(\\dfrac{{dy}}{{dx}} = {L(fp)} = {L(sp.factor(fp))}\\).", f"Stationary when \\(\\dfrac{{dy}}{{dx}} = 0\\): \\(x = {p}\\) or \\(x = {q}\\)."],
            "Stationary points occur where the derivative is zero (the tangent is horizontal).",
            "Take out the common factor and factorise the derivative fully before solving.",
            quicker="After taking out the common factor, the sum and product of the roots give the factors quickly.",
            common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error: \\((x - a) = 0\\) gives \\(x = a\\).", step=2),
                           err(S(_fx(f, p), _fx(f, q)), "interpretation", STAT, "Those are the \\(y\\)-coordinates; the question asks for the \\(x\\)-coordinates.", step=2)],
            skill="Find the stationary points of a cubic.",
            checkpoints=[cp(fp, "the derivative", step=1)],
            params={"form": "statx", "f": str(f), "p": p, "q": q},
        )
    if d == 2:
        if r.random() < 0.5:
            f, fp, p, q, s = _cubic(r)
            mx, mn = (p, q) if s > 0 else (q, p)
            fpp = sp.diff(fp, x)
            return Generated(
                f"Find the coordinates of the local maximum turning point of \\(y = {L(f)}\\), justifying its nature. "
                "Give the answer as \\(x, y\\).",
                A_set([mx, _fx(f, mx)], ordered=True), 3, 2,
                [f"\\(y' = {L(fp)} = {L(sp.factor(fp))}\\), so the stationary points are at \\(x = {p}\\) and \\(x = {q}\\).",
                 f"\\(y'' = {L(fpp)}\\). At \\(x = {mx}\\): \\(y'' = {fpp.subs(x, mx)} < 0\\), so concave down — a local maximum.",
                 f"At \\(x = {mn}\\): \\(y'' = {fpp.subs(x, mn)} > 0\\), a local minimum.",
                 f"\\(y({mx}) = {_fx(f, mx)}\\): the local maximum is \\(({mx}, {_fx(f, mx)})\\)."],
                "The second-derivative test: at a stationary point, \\(y'' < 0\\) means concave down (maximum), \\(y'' > 0\\) concave up (minimum).",
                "The nature must be justified (second derivative or a table of gradients); an unjustified 'maximum' loses a mark.",
                quicker=f"The cubic's leading coefficient is {'positive' if s > 0 else 'negative'}, so the {'left' if s > 0 else 'right'} stationary point is the maximum — confirm with \\(y''\\).",
                common_errors=[err(S(mn, _fx(f, mn)), "conceptual", STAT, "That is the local minimum: check the sign of \\(y''\\) there.", step=2),
                               err(S(mx, -_fx(f, mx)) if _fx(f, mx) != 0 else S(mx, 1), "arithmetic", "sign error",
                                   "Your \\(x\\)-value is right; recheck the substitution for \\(y\\).", step=4)],
                skill="Find and justify a local maximum.",
                checkpoints=[cp(fp, "the derivative", step=1), cp(fpp, "the second derivative", step=2)],
                params={"form": "max_cubic", "f": str(f), "p": p, "q": q, "s": s},
            )
        a = pick(r, [1, 2, 3])
        c = r.randint(-6, 8)
        f = x**4 - 2 * a * a * x**2 + c
        return Generated(
            f"The curve \\(y = {L(f)}\\) has three stationary points. Find the coordinates of the local maximum turning point. "
            "Give the answer as \\(x, y\\).",
            A_set([0, c], ordered=True), 3, 2,
            [f"\\(y' = {L(sp.diff(f, x))} = {L(sp.factor(sp.diff(f, x)))}\\), so \\(x = 0\\) or \\(x = \\pm {a}\\).",
             f"\\(y'' = {L(sp.diff(f, x, 2))}\\): at \\(x = 0\\), \\(y'' = {-4 * a * a} < 0\\) (maximum); at \\(x = \\pm {a}\\), \\(y'' = {8 * a * a} > 0\\) (minima).",
             f"The local maximum is \\((0, {c})\\)."],
            "A quartic with a positive leading coefficient and three stationary points is W-shaped: two minima and a maximum between them.",
            "Factorise the derivative completely: \\(4x(x^2 - a^2) = 4x(x - a)(x + a)\\).",
            quicker="The function is even (only even powers), so the curve is symmetric about the \\(y\\)-axis and \\(x = 0\\) is a turning point.",
            common_errors=[err(S(a, c - a**4), "conceptual", STAT, "That is a local minimum: check the sign of \\(y''\\).", step=2),
                           err(S(a, c), "arithmetic", STAT, "Substitute the \\(x\\)-value of the maximum into \\(y\\).", step=3)],
            skill="Find and classify the turning points of an even quartic.",
            checkpoints=[cp(sp.diff(f, x), "the derivative", step=1)],
            params={"form": "max_quartic", "a": a, "c": c},
        )
    f, fp, p, q, s = _cubic(r)
    yp, yq = _fx(f, p), _fx(f, q)
    ymax, ymin = max(yp, yq), min(yp, yq)
    xmax = p if yp > yq else q
    text = multipart(f"Let \\(f(x) = {L(f)}\\).",
                     [("a", "Find the \\(x\\)-coordinates of the stationary points of \\(f\\).", 2),
                      ("b", "Find the \\(y\\)-coordinate of the local maximum.", 1),
                      ("c", "For which values of \\(k\\) does the equation \\(f(x) = k\\) have three distinct real solutions?", 2)])
    steps = [f"(a) \\(f'(x) = {L(fp)} = {L(sp.factor(fp))}\\), so \\(x = {p}\\) or \\(x = {q}\\).",
             f"(b) \\(f({p}) = {yp}\\) and \\(f({q}) = {yq}\\); \\(f''({xmax}) = {sp.diff(fp, x).subs(x, xmax)} < 0\\), so the local maximum is \\(({xmax}, {ymax})\\).",
             f"(c) The horizontal line \\(y = k\\) cuts the cubic three times exactly when it lies strictly between the turning values.",
             f"So \\({ymin} < k < {ymax}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_set([p, q])), P("b", 1, A_num(ymax)), P("c", 2, A_iv([(ymin, ymax, False, False)], var="k"))), 5, 3, steps,
        "The number of solutions of \\(f(x) = k\\) is the number of times the horizontal line \\(y = k\\) meets the graph, so it changes at the turning values.",
        "Sketch the cubic with its turning points labelled before answering (c); use strict inequalities, because at \\(k\\) equal to a turning value there are only two solutions.",
        quicker="Once (a) and (b) are done, (c) needs no algebra: read it from the sketch.",
        common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error solving \\(f'(x) = 0\\).", step=1, part="a"),
                       err(ymin, "conceptual", STAT, "That is the local minimum value.", step=2, part="b"),
                       err(region([(ymin, ymax, True, True)], "k"), "notation", "inequality direction",
                           "At a turning value the line touches the curve, giving only two solutions: use strict inequalities.", step=4, part="c")],
        skill="Use turning points to count solutions of f(x) = k.",
        checkpoints=[cp(fp, "the derivative", step=1, part="a")],
        params={"form": "parts", "f": str(f), "p": p, "q": q},
    )


# ----------------------------------------------------------------------- 2C ---
def t_2C(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = r.randint(1, 4), nonzero(r, -5, 5), r.randint(-6, 6)
        e = pick(r, [4, 5])
        f = a * x**e + b * x**3 + c * x
        f2 = sp.diff(f, x, 2)
        if r.random() < 0.5:
            return Generated(
                f"Given \\(f(x) = {L(f)}\\), find \\(f''(x)\\).",
                A_expr(f2), 1, 1,
                [f"\\(f'(x) = {L(sp.diff(f, x))}\\).", f"\\(f''(x) = {L(sp.expand(f2))}\\)."],
                "The second derivative is the derivative of the first derivative.",
                "Write \\(f'(x)\\) as its own line before differentiating again.",
                quicker=f"For \\(x^n\\) the second derivative is \\(n(n-1)x^{{n-2}}\\): e.g. \\(x^{e}\\) gives \\({e * (e - 1)}x^{{{e - 2}}}\\).",
                common_errors=[err(sp.diff(f, x), "incomplete reasoning", DIFF, "That is \\(f'(x)\\): differentiate once more.", step=2),
                               err(sp.diff(f, x, 3), "careless error", DIFF, "That is the third derivative.", step=2)],
                skill="Find a second derivative.",
                params={"form": "f2x", "f": str(f)},
            )
        m = nonzero(r, -2, 3)
        val = f2.subs(x, m)
        return Generated(
            f"Given \\(f(x) = {L(f)}\\), find \\(f''({m})\\).",
            A_num(val), 2, 1,
            [f"\\(f'(x) = {L(sp.diff(f, x))}\\).", f"\\(f''(x) = {L(f2)}\\).", f"\\(f''({m}) = {val}\\)."],
            "The second derivative is the derivative of the first derivative; substitute only at the end.",
            "Differentiate in two clear lines; don't try to do both steps mentally.",
            quicker="Only the \\(x^{n}\\) terms with \\(n \\ge 2\\) survive two differentiations, so the \\(cx\\) term can be ignored.",
            common_errors=[err(sp.diff(f, x).subs(x, m), "incomplete reasoning", DIFF, f"That is \\(f'({m})\\): differentiate twice.", step=2)]
            + ([err(f.subs(x, m), "interpretation", DIFF, f"That is \\(f({m})\\).", step=3)] if f.subs(x, m) != val else []),
            skill="Evaluate a second derivative.",
            checkpoints=[cp(f2, "the second derivative", step=2)],
            params={"form": "f2m", "f": str(f), "m": m},
        )
    if d == 2:
        a = pick(r, [2, 3, 4, 5])
        b = nonzero(r, -5, 5)
        m = pick(r, [3, 4, 5, 6])
        u = a * x + b
        f = u**m
        f1 = m * a * u ** (m - 1)
        f2 = m * (m - 1) * a**2 * u ** (m - 2)
        return Generated(
            f"Find the second derivative of \\(y = {L(f)}\\).",
            A_expr(f2), 2, 2,
            [f"Chain rule: \\(y' = {m}\\times {a}({L(u)})^{{{m - 1}}} = {L(f1)}\\).",
             f"Again: \\(y'' = {m * a}\\times {m - 1}\\times {a}({L(u)})^{{{m - 2}}} = {L(f2)}\\)."],
            "Each differentiation of \\((ax + b)^n\\) brings down the power and multiplies by the inner derivative \\(a\\).",
            "Leave the answer in factored form — expanding wastes time and invites errors.",
            quicker=f"\\(\\dfrac{{d^2}}{{dx^2}}(ax+b)^n = n(n-1)a^2(ax+b)^{{n-2}}\\): here \\({m}\\times{m - 1}\\times{a * a}\\).",
            common_errors=[err(m * (m - 1) * a * u ** (m - 2), "conceptual", "chain rule", "You multiplied by the inner derivative only once; it appears at each differentiation.", step=2),
                           err(m * (m - 1) * u ** (m - 2), "conceptual", "chain rule", "The chain-rule factor \\(a\\) is missing (twice).", step=1)],
            skill="Second derivative using the chain rule.",
            checkpoints=[cp(m * a * (a * x + b) ** (m - 1), "the first derivative", step=1)],
            params={"form": "chain", "a": a, "b": b, "m": m},
        )
    b = pick(r, [1, 2, 3, -1, -2])
    x0 = pick(r, [1, 2, 3, -1, -2])
    a = -b * x0**3
    f = b * x**2 + a / x
    f1, f2 = sp.diff(f, x), sp.diff(f, x, 2)
    text = multipart(f"Let \\(f(x) = {L(f)}\\), for \\(x \\ne 0\\).",
                     [("a", "Find \\(f'(x)\\).", 1), ("b", "Find \\(f''(x)\\).", 1), ("c", "Find the value of \\(x\\) for which \\(f''(x) = 0\\).", 2)])
    steps = [f"Write \\(f(x) = {L(b * x**2)} {'+' if a > 0 else '-'} {abs(a)}x^{{-1}}\\).",
             f"(a) \\(f'(x) = {L(2 * b * x)} {'-' if a > 0 else '+'} {abs(a)}x^{{-2}} = {L(f1)}\\).",
             f"(b) \\(f''(x) = {L(2 * b)} {'+' if a > 0 else '-'} {2 * abs(a)}x^{{-3}} = {L(f2)}\\).",
             f"(c) \\({L(f2)} = 0\\) gives \\(x^3 = {L(sp.Rational(-a, b))}\\), so \\(x = {x0}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(f1)), P("b", 1, A_expr(f2)), P("c", 2, A_num(x0))), 4, 3, steps,
        "Rewrite \\(\\frac{a}{x}\\) as \\(ax^{-1}\\) so the power rule applies; negative powers become more negative each time.",
        "Show the index form line: it is where the sign of each term is decided.",
        quicker="\\(\\frac{d}{dx}x^{-1} = -x^{-2}\\) and \\(\\frac{d}{dx}x^{-2} = 2x^{-3}\\): two sign changes return the original sign.",
        common_errors=[err(2 * b * x + a / x**2, "careless error", "sign error", "\\(\\frac{d}{dx}x^{-1} = -x^{-2}\\): the sign changes.", step=2, part="a"),
                       err(2 * b - 2 * a / x**3, "careless error", "sign error", "Differentiating \\(-x^{-2}\\) gives \\(+2x^{-3}\\).", step=3, part="b"),
                       err(-x0, "careless error", "sign error", "Sign error solving for \\(x^3\\).", step=4, part="c")],
        skill="Differentiate negative powers twice and solve f''(x) = 0.",
        checkpoints=[cp(f2, "the second derivative", step=3, part="c")],
        params={"form": "parts", "a": a, "b": b, "x0": x0},
    )


# ----------------------------------------------------------------------- 2D ---
def t_2D(r: Rng, d: int) -> Generated:
    a = pick(r, [1, 2, -1, -2, 3])
    h = nonzero(r, -3, 3)
    b = -3 * a * h
    c, e = r.randint(-6, 6), r.randint(-5, 5)
    f = a * x**3 + b * x**2 + c * x + e
    f2 = sp.diff(f, x, 2)
    if d == 1:
        up = [(h, None, False, False)] if a > 0 else [(None, h, False, False)]
        down = [(None, h, False, False)] if a > 0 else [(h, None, False, False)]
        return Generated(
            f"For which values of \\(x\\) is the curve \\(y = {L(f)}\\) concave up?",
            A_iv(up, ends="ignore"), 2, 1,
            [f"\\(y' = {L(sp.diff(f, x))}\\) and \\(y'' = {L(f2)}\\).", f"Concave up where \\(y'' > 0\\): \\({L(f2)} > 0\\), so \\({region(up)}\\)."],
            "Concave up means the gradient is increasing, i.e. \\(y'' > 0\\).",
            "Divide by a negative coefficient carefully: the inequality reverses.",
            quicker=f"\\(y''\\) is linear with zero at \\(x = {h}\\), so the concavity changes only there.",
            common_errors=[err(region(down), "interpretation", CONC, "That is where the curve is concave down (\\(y'' < 0\\)).", step=2),
                           err(region([(-h, None, False, False)] if a > 0 else [(None, -h, False, False)]), "careless error", "sign error",
                               "Sign error solving \\(y'' > 0\\).", step=2)],
            skill="Find where a curve is concave up.",
            params={"form": "up", "f": str(f), "a": a, "h": h},
        )
    if d == 2:
        yh = f.subs(x, h)
        return Generated(
            f"Find the coordinates of the point of inflection of \\(y = {L(f)}\\), showing that the concavity changes there. Give the answer as \\(x, y\\).",
            A_set([h, yh], ordered=True), 3, 2,
            [f"\\(y' = {L(sp.diff(f, x))}\\), \\(y'' = {L(f2)}\\).",
             f"\\(y'' = 0\\) when \\(x = {h}\\). \\(y''\\) is linear, so it changes sign at \\(x = {h}\\) (e.g. \\(y''({h - 1}) = {f2.subs(x, h - 1)}\\), \\(y''({h + 1}) = {f2.subs(x, h + 1)}\\)).",
             f"\\(y({h}) = {yh}\\), so the point of inflection is \\(({h}, {yh})\\)."],
            "A point of inflection needs \\(y'' = 0\\) and a change of concavity (a sign change of \\(y''\\)).",
            "\\(y'' = 0\\) alone is not enough: test values either side and say 'concavity changes'.",
            quicker="For any cubic \\(ax^3 + bx^2 + cx + d\\) the inflection is at \\(x = -\\frac{b}{3a}\\) — use it to check.",
            common_errors=[err(S(-h, f.subs(x, -h)), "careless error", "sign error", "Sign error solving \\(y'' = 0\\).", step=2),
                           err(S(h, sp.diff(f, x).subs(x, h)), "interpretation", CONC, "You gave the gradient at the point, not its \\(y\\)-coordinate.", step=3)],
            skill="Find and verify a point of inflection.",
            checkpoints=[cp(f2, "the second derivative", step=1)],
            params={"form": "poi", "f": str(f), "h": h},
        )
    u, v = sorted(r.sample(range(-3, 4), 2))
    pp, c0 = r.randint(-6, 6), r.randint(-5, 5)
    g = x**4 - 2 * (u + v) * x**3 + 6 * u * v * x**2 + pp * x + c0
    g2 = sp.expand(sp.diff(g, x, 2))
    text = multipart(f"Let \\(f(x) = {L(g)}\\).",
                     [("a", "Find \\(f''(x)\\).", 1), ("b", "Find the \\(x\\)-coordinates of the points of inflection, justifying your answer.", 2),
                      ("c", "For which values of \\(x\\) is the curve concave down?", 2)])
    steps = [f"(a) \\(f'(x) = {L(sp.diff(g, x))}\\), so \\(f''(x) = {L(g2)} = {L(sp.factor(g2))}\\).",
             f"(b) \\(f''(x) = 0\\) at \\(x = {u}\\) and \\(x = {v}\\). These are distinct (single) zeros of a quadratic, so \\(f''\\) changes sign at each: both are points of inflection.",
             f"(c) \\(f''(x)\\) is a concave-up quadratic, negative between its zeros: concave down for \\({u} < x < {v}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(g2)), P("b", 2, A_set([u, v])), P("c", 2, A_iv([(u, v, False, False)], ends="ignore"))), 5, 3, steps,
        "Points of inflection are where the concavity changes, which for a polynomial happens at the single (not repeated) zeros of \\(f''\\).",
        "In (b) the justification is the sign change of \\(f''\\) — say so explicitly or test a value either side.",
        quicker="Factorise \\(f''(x)\\) once: it answers (b) and (c) together.",
        common_errors=[err(S(-u, -v), "careless error", "sign error", "Sign error solving \\(f''(x) = 0\\).", step=2, part="b"),
                       err(region([(None, u, False, False), (v, None, False, False)]), "interpretation", CONC, "That is where the curve is concave up.", step=3, part="c"),
                       err(sp.diff(g, x), "incomplete reasoning", DIFF, "That is \\(f'(x)\\): differentiate again.", step=1, part="a")],
        skill="Find points of inflection of a quartic and its regions of concavity.",
        checkpoints=[cp(g2, "the second derivative", step=1, part="b"), cp(g2, "the second derivative", step=1, part="c")],
        params={"form": "parts", "f": str(g), "u": u, "v": v},
    )


# ----------------------------------------------------------------------- 2E ---
def t_2E(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            kind = pick(r, ["odd", "even", "neither"])
            a, b = nonzero(r, -4, 4), nonzero(r, -6, 6)
            if kind == "odd":
                f = a * x**5 + b * x**3 + r.randint(1, 5) * x if r.random() < 0.5 else a * x**3 + b * x
            elif kind == "even":
                f = a * x**4 + b * x**2 + nonzero(r, -9, 9)
            else:
                f = a * x**3 + b * x**2 + nonzero(r, -9, 9)
            letter = {"odd": "A", "even": "B", "neither": "C"}[kind]
            opts = mcq_options("Odd", "Even", "Neither odd nor even")
            fm = sp.expand(f.subs(x, -x))
            wrong = {"A": "Odd needs \\(f(-x) = -f(x)\\) for every \\(x\\): every power must be odd (a constant term is an even power).",
                     "B": "Even needs \\(f(-x) = f(x)\\): every power must be even.",
                     "C": "Substitute \\(-x\\) and compare with \\(f(x)\\) and \\(-f(x)\\) term by term."}
            return Generated(
                f"Is the function \\(f(x) = {L(f)}\\) odd, even, or neither? Choose one option.",
                A_mcq(letter, opts), 1, 1,
                [f"\\(f(-x) = {L(fm)}\\).",
                 {"odd": "This is \\(-f(x)\\), so \\(f\\) is odd: its graph has point symmetry in the origin.",
                  "even": "This is \\(f(x)\\), so \\(f\\) is even: its graph is symmetric in the \\(y\\)-axis.",
                  "neither": "This is neither \\(f(x)\\) nor \\(-f(x)\\), so \\(f\\) is neither odd nor even."}[kind]],
                "Symmetry is the first step of systematic curve sketching: even functions are symmetric in the \\(y\\)-axis, odd functions in the origin.",
                "Show the substitution \\(f(-x)\\) and compare it with \\(f(x)\\); a one-word answer earns little in a written question.",
                quicker="For a polynomial, look at the powers: all odd means odd, all even (including the constant) means even.",
                common_errors=[err(ltr, "conceptual", "transformations", wrong[ltr], step=2) for ltr in "ABC" if ltr != letter],
                skill="Test a function for odd or even symmetry.",
                params={"form": "parity", "f": str(f), "kind": kind},
            )
        a, b, c = nonzero(r, -4, 4), r.randint(-6, 6), nonzero(r, -4, 4)
        while a * c + b == 0:
            b = r.randint(-6, 6)
        f = (a * x + b) / (x - c)
        text = multipart(f"Consider the curve \\(y = {L(f)}\\).",
                         [("a", "Find the equation of the vertical asymptote (enter the value of \\(x\\)).", 1),
                          ("b", "Find the equation of the horizontal asymptote (enter the value of \\(y\\)).", 1)])
        return Generated(
            text, A_parts(P("a", 1, A_num(c)), P("b", 1, A_num(a))), 2, 1,
            [f"(a) The denominator is zero at \\(x = {c}\\) (and the numerator is not), so \\(x = {c}\\) is a vertical asymptote.",
             f"(b) Divide top and bottom by \\(x\\): \\(y = \\dfrac{{{a} {'+' if b >= 0 else '-'} {abs(b)}/x}}{{1 {'-' if c > 0 else '+'} {abs(c)}/x}} \\to {a}\\) as \\(x \\to \\pm\\infty\\), so \\(y = {a}\\)."],
            "Vertical asymptotes come from zeros of the denominator; horizontal asymptotes from the behaviour as \\(x \\to \\pm\\infty\\).",
            "State asymptotes as equations of lines: \\(x = \\ldots\\) and \\(y = \\ldots\\).",
            quicker="For \\(\\frac{ax + b}{x - c}\\), the horizontal asymptote is the ratio of the leading coefficients, \\(y = a\\).",
            common_errors=[err(-c, "careless error", "sign error", "\\(x - c = 0\\) gives \\(x = c\\).", step=1, part="a"),
                           err(sp.Rational(-b, a) if b else 0, "conceptual", "domain/range", "That is where the curve crosses the \\(x\\)-axis, not an asymptote.", step=2, part="b")],
            skill="Find the asymptotes of a rational function.",
            params={"form": "asym", "a": a, "b": b, "c": c},
        )
    if d == 2:
        a = pick(r, [1, 2, 3])
        sgn = pick(r, [1, -1])
        f = sgn * (x**4 - 4 * a * x**3)
        opts = mcq_options("a local maximum", "a local minimum", "a horizontal (stationary) point of inflection")
        turn = "minimum" if sgn > 0 else "maximum"
        text = multipart(f"Consider the curve \\(y = {L(f)}\\).",
                         [("a", "Find the \\(x\\)-coordinates of the stationary points.", 1),
                          ("b", "What is the nature of the stationary point at the origin? Justify your answer.", 2)])
        fp = sp.diff(f, x)
        return Generated(
            text, A_parts(P("a", 1, A_set([0, 3 * a])), P("b", 2, A_mcq("C", opts))), 3, 2,
            [f"(a) \\(y' = {L(fp)} = {L(sp.factor(fp))}\\), which is zero at \\(x = 0\\) and \\(x = {3 * a}\\).",
             f"(b) Table of gradients: \\(y'(-1) = {fp.subs(x, -1)}\\), \\(y'(1) = {fp.subs(x, 1)}\\): the gradient has the same sign on both sides of \\(x = 0\\).",
             f"So the origin is a horizontal point of inflection (\\(x^2\\) is a squared factor of \\(y'\\)); the point at \\(x = {3 * a}\\) is a local {turn}."],
            "A stationary point is a turning point only if \\(y'\\) changes sign there; a repeated (squared) factor of \\(y'\\) gives no sign change.",
            "Use a table of gradients: \\(y'' = 0\\) at the origin, so the second-derivative test is inconclusive there.",
            quicker="The factor \\(x^2\\) in \\(y'\\) never changes sign, so the sign of \\(y'\\) near \\(0\\) is the sign of the other factor on both sides.",
            common_errors=[err("A", "conceptual", STAT, "A maximum needs \\(y'\\) to change from positive to negative; here it does not change sign.", step=2, part="b"),
                           err("B", "conceptual", STAT, "A minimum needs \\(y'\\) to change from negative to positive; here it does not change sign.", step=2, part="b"),
                           err(S(0, -3 * a), "careless error", "sign error", "Sign error solving \\(y' = 0\\).", step=1, part="a")],
            skill="Classify stationary points with a table of gradients.",
            checkpoints=[cp(fp, "the derivative", step=1, part="b")],
            params={"form": "hpoi", "a": a, "s": sgn},
        )
    p = pick(r, [3, 6, 9, -3, -6])
    f = x * (x - p) ** 2
    fe = sp.expand(f)
    fp = sp.expand(sp.diff(f, x))
    s1, s2 = sp.Rational(p, 3), p
    y1, y2 = f.subs(x, s1), f.subs(x, s2)
    xmax, ymax = (s1, y1) if y1 > y2 else (s2, y2)
    ymin = min(y1, y2)
    xi = sp.Rational(2 * p, 3)
    text = multipart(f"Let \\(f(x) = x(x {'-' if p > 0 else '+'} {abs(p)})^2\\).",
                     [("a", "Find the \\(x\\)-intercepts of the graph.", 1),
                      ("b", "Find the coordinates of the local maximum turning point (give \\(x, y\\)).", 2),
                      ("c", "Find the \\(x\\)-coordinate of the point of inflection.", 1),
                      ("d", "For which values of \\(k\\) does \\(f(x) = k\\) have exactly one real solution?", 2)])
    steps = [f"(a) \\(f(x) = 0\\) when \\(x = 0\\) or \\(x = {p}\\) (a double root: the curve touches the axis there).",
             f"(b) \\(f(x) = {L(fe)}\\), so \\(f'(x) = {L(fp)} = {L(sp.factor(fp))}\\), zero at \\(x = {L(s1)}\\) and \\(x = {p}\\).",
             f"\\(f''(x) = {L(sp.diff(fe, x, 2))}\\): \\(f''({L(xmax)}) = {L(sp.diff(fe, x, 2).subs(x, xmax))} < 0\\), so the local maximum is \\(({L(xmax)}, {L(ymax)})\\).",
             f"(c) \\(f''(x) = 0\\) at \\(x = {L(xi)}\\), and \\(f''\\) is linear so it changes sign there.",
             f"(d) The line \\(y = k\\) meets the curve once when it is above the local maximum or below the local minimum (value \\({L(ymin)}\\)): \\(k < {L(ymin)}\\) or \\(k > {L(ymax)}\\)."]
    return Generated(
        text,
        A_parts(P("a", 1, A_set([0, p])), P("b", 2, A_set([xmax, ymax], ordered=True)), P("c", 1, A_num(xi)),
                P("d", 2, A_iv([(None, ymin, False, False), (ymax, None, False, False)], var="k"))),
        6, 3, steps,
        "Systematic sketching: intercepts, stationary points and their nature, inflections, then the global shape — which answers questions about the number of solutions.",
        "Draw the sketch before (d) and mark the turning values on the \\(y\\)-axis.",
        quicker=f"The double root at \\(x = {p}\\) is a turning point on the axis, so one stationary value is \\(0\\) without any calculus.",
        common_errors=[err(S(0, -p), "careless error", "sign error", "Sign error: \\((x - a)^2 = 0\\) gives \\(x = a\\).", step=1, part="a"),
                       err(S(xmax, -ymax), "arithmetic", "sign error", "Recheck the \\(y\\)-coordinate.", step=3, part="b"),
                       err(region([(ymin, ymax, False, False)], "k"), "interpretation", STAT, "Between the turning values the line meets the curve three times.", step=5, part="d")],
        skill="Sketch a cubic systematically and count solutions of f(x) = k.",
        checkpoints=[cp(fp, "the derivative", step=2, part="b")],
        params={"form": "parts", "p": p},
    )


# ----------------------------------------------------------------------- 2F ---
def _global(f, lo, hi, stats):
    vals = {v: f.subs(x, v) for v in [lo, hi] + [s for s in stats if lo <= s <= hi]}
    return vals


def t_2F(r: Rng, d: int) -> Generated:
    if d == 1:
        h, c = r.randint(-3, 3), r.randint(-5, 9)
        a = pick(r, [1, 2])
        lo, hi = h - r.randint(1, 3), h + r.randint(1, 4)
        f = sp.expand(-a * (x - h) ** 2 + c)
        ends = {lo: f.subs(x, lo), hi: f.subs(x, hi)}
        return Generated(
            f"Find the global maximum value of \\(f(x) = {L(f)}\\) for \\({lo} \\le x \\le {hi}\\).",
            A_num(c), 2, 1,
            [f"\\(f'(x) = {L(sp.diff(f, x))} = 0\\) at \\(x = {h}\\), inside the interval; \\(f''(x) = {-2 * a} < 0\\) so it is a maximum.",
             f"\\(f({h}) = {c}\\), and at the endpoints \\(f({lo}) = {ends[lo]}\\), \\(f({hi}) = {ends[hi]}\\).",
             f"The global maximum is \\({c}\\)."],
            "On a closed interval the global maximum is the largest of the stationary values inside the interval and the endpoint values.",
            "List every candidate value (stationary points and endpoints) and choose the largest.",
            quicker="The parabola is concave down, so its vertex is the highest point whenever the vertex lies in the interval.",
            common_errors=[err(max(ends.values()), "interpretation", STAT, "That is the larger endpoint value; the vertex inside the interval is higher.", step=2),
                           err(h, "interpretation", STAT, "That is where the maximum occurs; the question asks for the maximum value.", step=3)],
            skill="Find a global maximum on a closed interval.",
            params={"form": "quad", "a": a, "h": h, "c": c, "lo": lo, "hi": hi},
        )
    for _ in range(200):
        f, fp, p, q, s = _cubic(r, -3, 4)
        lo, hi = p - r.randint(1, 3), q + r.randint(1, 3)
        vals = _global(f, lo, hi, [p, q])
        gmax, gmin = max(vals.values()), min(vals.values())
        lmax, lmin = (f.subs(x, p), f.subs(x, q)) if s > 0 else (f.subs(x, q), f.subs(x, p))
        if gmax != lmax or gmin != lmin:
            break
    if d == 2:
        ask_max = gmax != lmax or r.random() < 0.3
        target = gmax if ask_max else gmin
        local = lmax if ask_max else lmin
        word = "maximum" if ask_max else "minimum"
        ces = [err(local, "interpretation", STAT, f"That is the local {word}; an endpoint gives a {'larger' if ask_max else 'smaller'} value.", step=3)] if local != target else []
        ces.append(err(-target, "careless error", "sign error", "Check the signs when substituting.", step=2))
        return Generated(
            f"Find the global {word} value of \\(f(x) = {L(f)}\\) in the interval \\({lo} \\le x \\le {hi}\\).",
            A_num(target), 3, 2,
            [f"\\(f'(x) = {L(fp)} = {L(sp.factor(fp))}\\), zero at \\(x = {p}\\) and \\(x = {q}\\) (both in the interval).",
             "Values: " + ", ".join(f"\\(f({v}) = {fv}\\)" for v, fv in vals.items()) + ".",
             f"The global {word} is \\({target}\\)."],
            "Global extrema on a closed interval occur at stationary points or at the endpoints, so compare all of them.",
            "Global questions are designed to catch students who check only the stationary points: always evaluate the endpoints.",
            quicker="Sketch the cubic with its turning points; the shape shows which endpoint can beat a turning value.",
            common_errors=ces, skill="Find a global extremum of a cubic on a closed interval.",
            checkpoints=[cp(fp, "the derivative", step=1)],
            params={"form": "cubic", "f": str(f), "lo": lo, "hi": hi, "word": word},
        )
    text = multipart(f"Let \\(f(x) = {L(f)}\\), for \\({lo} \\le x \\le {hi}\\).",
                     [("a", "Find the \\(x\\)-coordinates of the stationary points.", 2), ("b", "Find the global maximum value of \\(f(x)\\).", 1),
                      ("c", "Find the global minimum value of \\(f(x)\\).", 1)])
    ces = [err(S(-p, -q), "careless error", "sign error", "Sign error solving \\(f'(x) = 0\\).", step=1, part="a")]
    if lmax != gmax:
        ces.append(err(lmax, "interpretation", STAT, "That is the local maximum; an endpoint is higher.", step=3, part="b"))
    if lmin != gmin:
        ces.append(err(lmin, "interpretation", STAT, "That is the local minimum; an endpoint is lower.", step=3, part="c"))
    return Generated(
        text, A_parts(P("a", 2, A_set([p, q])), P("b", 1, A_num(gmax)), P("c", 1, A_num(gmin))), 4, 3,
        [f"(a) \\(f'(x) = {L(fp)} = {L(sp.factor(fp))}\\), so \\(x = {p}\\) or \\(x = {q}\\).",
         "(b) Candidates: " + ", ".join(f"\\(f({v}) = {fv}\\)" for v, fv in vals.items()) + ".",
         f"The global maximum is \\({gmax}\\) and (c) the global minimum is \\({gmin}\\)."],
        "On a closed interval compare the stationary values with the endpoint values.",
        "Set out a table of candidate \\(x\\)-values and \\(f(x)\\); it is quick to mark and hard to get wrong.",
        quicker="A sketch of the cubic between the endpoints shows immediately which candidates can be extreme.",
        common_errors=ces, skill="Find global extrema of a cubic on a closed interval.",
        checkpoints=[cp(fp, "the derivative", step=1, part="a")],
        params={"form": "parts", "f": str(f), "lo": lo, "hi": hi},
    )


# ----------------------------------------------------------------------- 2G ---
def t_2G(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = nonzero(r, -4, 4), r.randint(-6, 6), nonzero(r, -3, 3)
        kv = a * c + b - c * c
        lin = a * x + b
        ces = [err(c * c - a * c - b, "careless error", "sign error", "Sign error when solving for \\(k\\).", step=2)]
        if b != kv:
            ces.append(err(b, "interpretation", CD, f"You matched the pieces at \\(x = 0\\); continuity is needed where the rule changes, \\(x = {c}\\).", step=1))
        return Generated(
            f"The function \\(f\\) is defined by \\(f(x) = {L(lin)}\\) for \\(x < {c}\\) and \\(f(x) = x^2 + k\\) for \\(x \\ge {c}\\). "
            f"Find the value of \\(k\\) for which \\(f\\) is continuous at \\(x = {c}\\).",
            A_num(kv), 2, 1,
            [f"For continuity at \\(x = {c}\\) the two pieces must meet: \\({L(lin.subs(x, c))} = ({c})^2 + k\\).",
             f"So \\(k = {lin.subs(x, c)} - {c * c} = {kv}\\)."],
            "A function is continuous at a point when its graph has no break there: the left and right limits equal the function value.",
            "Write the left-hand and right-hand limits separately, then set them equal.",
            quicker=f"Evaluate both rules at \\(x = {c}\\) and equate — one line.",
            common_errors=ces, skill="Make a piecewise function continuous.",
            params={"form": "cont", "a": a, "b": b, "c": c},
        )
    if d == 2:
        if r.random() < 0.5:
            pp, q, c = pick(r, [1, 2, 3, -1]), r.randint(-5, 5), nonzero(r, -3, 3)
            av, bv = 2 * pp * c, q - pp * c * c
            left = pp * x**2 + q
            text = multipart(f"The function \\(f(x) = {L(left)}\\) for \\(x \\le {c}\\) and \\(f(x) = ax + b\\) for \\(x > {c}\\) is differentiable at \\(x = {c}\\).",
                             [("a", "Find \\(a\\).", 1), ("b", "Find \\(b\\).", 2)])
            return Generated(
                text, A_parts(P("a", 1, A_num(av)), P("b", 2, A_num(bv))), 3, 2,
                [f"(a) Differentiable means the gradients match: \\(\\dfrac{{d}}{{dx}}({L(left)}) = {L(2 * pp * x)}\\), which is \\({2 * pp * c}\\) at \\(x = {c}\\), so \\(a = {av}\\).",
                 f"(b) Differentiable implies continuous: \\({L(left.subs(x, c))} = {av}\\times({c}) + b\\), so \\(b = {bv}\\)."],
                "A function is differentiable at a join only if it is continuous there and the left and right gradients are equal.",
                "Use both conditions: equal values (continuity) and equal gradients (smoothness).",
                quicker="The line must be the tangent to the parabola at \\(x = c\\): \\(y = f(c) + f'(c)(x - c)\\).",
                common_errors=[err(pp * c, "careless error", DIFF, "\\(\\frac{d}{dx}x^2 = 2x\\): the factor 2 is missing.", step=1, part="a"),
                               err(q + pp * c * c, "careless error", "sign error", "Sign error when solving for \\(b\\).", step=2, part="b")],
                skill="Use continuity and equal gradients at a join.",
                params={"form": "diff_ab", "p": pp, "q": q, "c": c},
            )
        m = pick(r, [1, 2, 3, 4, 5])
        f = sp.Abs(x**2 - m * m)
        return Generated(
            f"At which values of \\(x\\) is the function \\(y = |x^2 - {m * m}|\\) not differentiable?",
            A_set([-m, m]), 2, 2,
            [f"\\(y = x^2 - {m * m}\\) outside \\(-{m} < x < {m}\\) and \\(y = {m * m} - x^2\\) inside: the part below the axis is reflected.",
             f"At \\(x = \\pm {m}\\) the left and right gradients are \\(\\mp {2 * m}\\) and \\(\\pm {2 * m}\\): sharp corners, so not differentiable there. At \\(x = 0\\) the graph is smooth (a turning point)."],
            "A graph is not differentiable at a sharp corner (or a break); reflecting the negative part of a curve in the \\(x\\)-axis creates corners at its \\(x\\)-intercepts.",
            "Sketch the curve: corners are where the reflected part meets the axis.",
            quicker="For \\(y = |g(x)|\\), check the zeros of \\(g\\) where \\(g\\) changes sign.",
            common_errors=[err(S(-m, 0, m), "interpretation", CD, "At \\(x = 0\\) the curve has a smooth turning point (gradient 0), so it is differentiable there.", step=2),
                           err(S(0), "conceptual", CD, "The turning point at \\(x = 0\\) is smooth; the corners are at the \\(x\\)-intercepts.", step=2)],
            skill="Recognise where a function is not differentiable.",
            params={"form": "abs", "m": m, "f": str(f)},
        )
    b, c = r.randint(-4, 4), nonzero(r, -3, 3)
    smooth = r.random() < 0.5
    grad = 2 * c + b
    m = grad if smooth else grad + nonzero(r, -2, 2)
    kv = c * c + b * c - m * c
    left = x**2 + b * x
    opts = mcq_options("Yes, it is differentiable at that point", "No, it is not differentiable at that point")
    letter = "A" if smooth else "B"
    text = multipart(f"Let \\(f(x) = {L(left)}\\) for \\(x < {c}\\) and \\(f(x) = {L(m * x)} + k\\) for \\(x \\ge {c}\\).",
                     [("a", f"Find the value of \\(k\\) for which \\(f\\) is continuous at \\(x = {c}\\).", 2),
                      ("b", f"Find the gradient of the curve \\(y = {L(left)}\\) at \\(x = {c}\\).", 1),
                      ("c", f"With this value of \\(k\\), is \\(f\\) differentiable at \\(x = {c}\\)? Justify your answer.", 1)])
    steps = [f"(a) Left limit: \\({L(left.subs(x, c))}\\); right value: \\({m * c} + k\\).",
             f"Continuity: \\({left.subs(x, c)} = {m * c} + k\\), so \\(k = {kv}\\).",
             f"(b) \\(\\dfrac{{d}}{{dx}}({L(left)}) = {L(2 * x + b)}\\), which is \\({grad}\\) at \\(x = {c}\\).",
             f"(c) The line has gradient \\({m}\\). " + ("The gradients are equal and \\(f\\) is continuous, so \\(f\\) is differentiable at the join."
                                                         if smooth else f"\\({m} \\ne {grad}\\): the graph has a corner, so \\(f\\) is not differentiable there.")]
    return Generated(
        text, A_parts(P("a", 2, A_num(kv)), P("b", 1, A_num(grad)), P("c", 1, A_mcq(letter, opts))), 4, 3, steps,
        "Differentiable at a join means continuous there with equal left and right gradients.",
        "In (c) quote both gradients — the justification earns the mark, not the word 'yes' or 'no'.",
        quicker="Continuity first (a), then compare the two gradients (b) — (c) follows in one line.",
        common_errors=[err(m * c - c * c - b * c, "careless error", "sign error", "Sign error when solving for \\(k\\).", step=2, part="a"),
                       err(left.subs(x, c), "conceptual", DIFF, "That is the function value; the gradient needs the derivative.", step=3, part="b"),
                       err("B" if smooth else "A", "conceptual", CD,
                           "Compare the two gradients at the join: equal gradients (with continuity) mean differentiable." if smooth
                           else "Continuity alone is not enough: the gradients differ, so there is a corner.", step=4, part="c")],
        skill="Test a piecewise function for continuity and differentiability.",
        params={"form": "parts", "b": b, "c": c, "m": m},
    )


# ----------------------------------------------------------------------- 2H ---
def t_2H(r: Rng, d: int) -> Generated:
    if d == 1:
        a, h = pick(r, [2, 4, 5, 10]), pick(r, [10, 20, 25, 30, 40])
        b = 2 * a * h
        c0 = pick(r, [100, 200, 500, 1000])
        prof = a * h * h - c0
        P_ = b * x - a * x**2 - c0
        return Generated(
            f"A grower's profit, in dollars, from planting \\(x\\) hectares is \\(P = {L(P_)}\\). Find the maximum profit, justifying that it is a maximum.",
            A_units(prof, "$"), 2, 1,
            [f"\\(\\dfrac{{dP}}{{dx}} = {L(sp.diff(P_, x))} = 0\\) when \\(x = {h}\\); \\(\\dfrac{{d^2P}}{{dx^2}} = {-2 * a} < 0\\), so a maximum.",
             f"\\(P({h}) = {b}\\times {h} - {a}\\times {h}^2 - {c0} = {prof}\\): the maximum profit is \\${prof}."],
            "At a maximum the derivative is zero and the second derivative is negative.",
            "Answer the question asked: the maximum profit, in dollars — not the number of hectares.",
            quicker="The profit function is a concave-down parabola, so the maximum is at the vertex \\(x = -\\frac{b}{2a}\\).",
            common_errors=[err(h, "interpretation", "modelling", "That is the number of hectares; the question asks for the profit.", step=2),
                           err(a * h * h, "careless error", "modelling", "The fixed cost must still be subtracted.", step=2)],
            skill="Maximise a quadratic model.",
            params={"form": "profit", "a": a, "h": h, "c": c0},
        )
    if d == 2:
        Lf = pick(r, [40, 60, 80, 100, 120, 160, 200])
        area = sp.Rational(Lf * Lf, 8)
        return Generated(
            f"A farmer has \\({Lf}\\) metres of fencing to enclose a rectangular paddock against a long straight wall, so only three sides need fencing. "
            "Find the maximum area of the paddock.",
            A_units(area, "m^2"), 3, 2,
            [f"Let the two sides perpendicular to the wall be \\(x\\) m; the side parallel to the wall is \\({Lf} - 2x\\) m.",
             f"\\(A = x({Lf} - 2x) = {Lf}x - 2x^2\\), for \\(0 < x < {Lf // 2}\\).",
             f"\\(A' = {Lf} - 4x = 0\\) at \\(x = {L(sp.Rational(Lf, 4))}\\); \\(A'' = -4 < 0\\), so a maximum.",
             f"\\(A = {L(sp.Rational(Lf, 4))}\\times {L(sp.Rational(Lf, 2))} = {L(area)}\\) m²."],
            "Optimisation: write the quantity in one variable using the constraint, then differentiate and justify the maximum.",
            "Define the variable on a diagram, state its domain, and justify the maximum with \\(A''\\) or a table.",
            quicker=f"\\(A = x({Lf} - 2x)\\) is a parabola with zeros \\(0\\) and \\({Lf // 2}\\): its vertex is midway, at \\(x = {L(sp.Rational(Lf, 4))}\\).",
            common_errors=[err(sp.Rational(Lf, 4) ** 2, "interpretation", "modelling", "That fences all four sides (a square); the wall replaces one side.", step=1),
                           err(sp.Rational(Lf, 4), "incomplete reasoning", "modelling", "That is the width that gives the maximum; now find the area.", step=4),
                           err(sp.Rational(Lf, 3) ** 2, "conceptual", "modelling", "Equal sides are not optimal here: write \\(A\\) in terms of one variable and differentiate.", step=2)],
            skill="Set up and solve an optimisation problem with a constraint.",
            checkpoints=[cp(Lf * x - 2 * x**2, "the area function", step=2, marks=1)],
            params={"form": "fence", "L": Lf},
        )
    if r.random() < 0.5:
        s = pick(r, [6, 12, 18, 24, 30, 36])
        V = x * (s - 2 * x) ** 2
        xv = sp.Rational(s, 6)
        vmax = V.subs(x, xv)
        text = multipart(f"A square sheet of cardboard has side length \\({s}\\) cm. Equal squares of side \\(x\\) cm are cut from each corner and the sides are folded up to make an open box.",
                         [("a", "Write an expression for the volume \\(V\\) of the box in terms of \\(x\\).", 1),
                          ("b", "Find the value of \\(x\\) that maximises the volume, justifying that it is a maximum.", 2),
                          ("c", "Find the maximum volume.", 1)])
        Vp = sp.expand(sp.diff(V, x))
        return Generated(
            text, A_parts(P("a", 1, A_expr(V)), P("b", 2, A_num(xv)), P("c", 1, A_units(vmax, "cm^3"))), 4, 3,
            [f"(a) The base is \\(({s} - 2x)\\) by \\(({s} - 2x)\\) and the height is \\(x\\): \\(V = x({s} - 2x)^2\\), \\(0 < x < {s // 2}\\).",
             f"(b) \\(V' = ({s} - 2x)^2 - 4x({s} - 2x) = ({s} - 2x)({s} - 6x) = {L(Vp)}\\).",
             f"\\(V' = 0\\) at \\(x = {s // 2}\\) (no box: reject) or \\(x = {L(xv)}\\). \\(V'' = {L(sp.diff(Vp, x))}\\), which is \\({sp.diff(Vp, x).subs(x, xv)} < 0\\) at \\(x = {L(xv)}\\): a maximum.",
             f"(c) \\(V = {L(xv)}\\times {s - 2 * xv}^2 = {L(vmax)}\\) cm³."],
            "Write the quantity in terms of one variable, find its domain, differentiate, and reject stationary points outside the domain.",
            "State the domain \\(0 < x < \\frac{s}{2}\\) — it is how you justify rejecting the other stationary point.",
            quicker="For a square sheet of side \\(s\\), the optimal cut is always \\(x = \\frac{s}{6}\\) — a useful check.",
            common_errors=[err(x * (s - x) ** 2, "conceptual", "modelling", "A square is cut from both ends of each side, so the base is \\(s - 2x\\).", step=1, part="a"),
                           err(sp.Rational(s, 2), "interpretation", "domain/range", f"\\(x = {s // 2}\\) leaves no base (volume 0): it is outside the domain.", step=3, part="b"),
                           err(xv * (s - xv) ** 2, "arithmetic", "modelling", "Substitute into \\(V = x(s - 2x)^2\\).", step=4, part="c")],
            skill="Optimise the volume of an open box.",
            checkpoints=[cp(Vp, "the derivative V'", step=2, part="b")],
            params={"form": "box", "s": s},
        )
    m = pick(r, [1, 2, 3])
    c = 3 * m * m
    A = 2 * x * (c - x**2)
    amax = A.subs(x, m)
    text = multipart(f"A rectangle has two vertices on the \\(x\\)-axis and the other two on the parabola \\(y = {c} - x^2\\), above the axis and symmetric about the \\(y\\)-axis. "
                     "Let the vertex in the first quadrant be \\((x, y)\\).",
                     [("a", "Write the area \\(A\\) of the rectangle in terms of \\(x\\).", 1),
                      ("b", "Find the value of \\(x\\) that gives the maximum area.", 2), ("c", "Find the maximum area.", 1)])
    return Generated(
        text, A_parts(P("a", 1, A_expr(A)), P("b", 2, A_num(m)), P("c", 1, A_units(amax, "units^2"))), 4, 3,
        [f"(a) The width is \\(2x\\) and the height is \\({c} - x^2\\): \\(A = 2x({c} - x^2) = {L(sp.expand(A))}\\), \\(0 < x < \\sqrt{{{c}}}\\).",
         f"(b) \\(A' = {L(sp.expand(sp.diff(A, x)))} = 0\\) gives \\(x^2 = {m * m}\\), so \\(x = {m}\\) (\\(x > 0\\)).",
         f"\\(A'' = -12x < 0\\) for \\(x > 0\\), so it is a maximum.",
         f"(c) \\(A = 2\\times {m}\\times({c} - {m * m}) = {amax}\\) square units."],
        "Use the curve to express the height in terms of \\(x\\), so the area is a function of one variable.",
        "Write the domain and reject the negative root explicitly.",
        quicker="By symmetry work with the half-rectangle \\(x({c} - x^2)\\) and double at the end.",
        common_errors=[err(x * (c - x**2), "conceptual", "modelling", "The rectangle extends from \\(-x\\) to \\(x\\): its width is \\(2x\\).", step=1, part="a"),
                       err(sp.sqrt(c), "interpretation", "domain/range", "At \\(x = \\sqrt{c}\\) the height is zero; that makes \\(A = 0\\).", step=2, part="b"),
                       err(m * (c - m * m), "careless error", "modelling", "Remember the width is \\(2x\\).", step=4, part="c")],
        skill="Optimise a rectangle inscribed under a parabola.",
        checkpoints=[cp(sp.expand(sp.diff(A, x)), "the derivative A'", step=2, part="b")],
        params={"form": "parabola", "m": m},
    )


# ----------------------------------------------------------------------- 2I ---
def t_2I(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = r.randint(1, 4), nonzero(r, -6, 6), nonzero(r, -9, 9)
        f = 3 * a * x**2 + 2 * b * x + c
        F = a * x**3 + b * x**2 + c * x
        return Generated(
            f"Find the primitive of \\({L(f)}\\).",
            A_prim(F), 1, 1,
            [f"Increase each index by one and divide by the new index: \\(\\displaystyle\\int ({L(f)})\\,dx = {L(F)} + C\\)."],
            "A primitive \\(F\\) satisfies \\(F'(x) = f(x)\\); all primitives differ by a constant.",
            "Always include \\(+C\\) for a primitive, and check by differentiating.",
            quicker="Differentiate your answer mentally: you should get back the original function.",
            common_errors=[err(sp.diff(f, x), "conceptual", INTG, "You differentiated; a primitive reverses differentiation.", step=1),
                           err(x * f, "formula selection", INTG, "Increase the index by one and divide by the new index, term by term.", step=1)],
            skill="Find the primitive of a polynomial.",
            params={"form": "poly", "f": str(f)},
        )
    if d == 2:
        if r.random() < 0.5:
            a, b = pick(r, [3, 6, 9, 3 * 2]), nonzero(r, -6, 6)
            f = a * sp.sqrt(x) + b / x**2
            F = sp.Rational(2 * a, 3) * x ** sp.Rational(3, 2) - b / x
            return Generated(
                f"Find \\(\\displaystyle\\int \\left({L(f)}\\right)dx\\).",
                A_prim(F), 2, 2,
                [f"Write in index form: \\({a}x^{{\\frac{{1}}{{2}}}} {'+' if b > 0 else '-'} {abs(b)}x^{{-2}}\\).",
                 f"\\(\\displaystyle\\int = {a}\\cdot\\frac{{x^{{3/2}}}}{{3/2}} {'+' if b > 0 else '-'} {abs(b)}\\cdot\\frac{{x^{{-1}}}}{{-1}} + C = {L(F)} + C\\)."],
                "Roots and reciprocals become powers of \\(x\\), and the power rule for primitives applies to any index except \\(-1\\).",
                "Write the index form line first; most errors come from the signs of negative indices.",
                quicker="Dividing by \\(\\frac{3}{2}\\) is multiplying by \\(\\frac{2}{3}\\).",
                common_errors=[err(sp.Rational(2 * a, 3) * x ** sp.Rational(3, 2) + b / x, "careless error", "sign error", "Dividing by the new index \\(-1\\) changes the sign.", step=2),
                               err(sp.Rational(3 * a, 2) * x ** sp.Rational(3, 2) - b / x, "arithmetic", INTG, "Divide by \\(\\frac{3}{2}\\), i.e. multiply by \\(\\frac{2}{3}\\).", step=2)],
                skill="Primitives of fractional and negative powers.",
                params={"form": "powers", "a": a, "b": b},
            )
        a, b, c = r.randint(1, 4), nonzero(r, -5, 5), nonzero(r, -6, 6)
        fp = 3 * a * x**2 + 2 * b * x + c
        x0, y0 = r.randint(-2, 2), r.randint(-9, 9)
        C = y0 - (a * x0**3 + b * x0**2 + c * x0)
        F = a * x**3 + b * x**2 + c * x + C
        ces = [err(a * x**3 + b * x**2 + c * x, "incomplete reasoning", "constant of integration", "You left out the constant: use the given point to find \\(C\\).", step=2)] if C != 0 else []
        ces.append(err(F - 2 * C + 0 * x if C else F + 1, "careless error", "sign error", "Check the sign when solving for \\(C\\).", step=2))
        return Generated(
            f"A function satisfies \\(f'(x) = {L(fp)}\\) and \\(f({x0}) = {y0}\\). Find \\(f(x)\\).",
            A_expr(F), 3, 2,
            [f"\\(f(x) = {L(a * x**3 + b * x**2 + c * x)} + C\\).",
             f"\\(f({x0}) = {a * x0**3 + b * x0**2 + c * x0} + C = {y0}\\), so \\(C = {C}\\).",
             f"\\(f(x) = {L(F)}\\)."],
            "A primitive is determined up to a constant; one known point fixes the constant.",
            "Keep \\(+C\\) until you have used the condition — then substitute its value.",
            quicker="Check: differentiate your \\(f(x)\\) and substitute \\(x = " + str(x0) + "\\).",
            common_errors=ces, skill="Find a function from its derivative and a point.",
            checkpoints=[cp(a * x**3 + b * x**2 + c * x, "the primitive before C is found", step=1, marks=1)],
            params={"form": "point", "a": a, "b": b, "c": c, "x0": x0, "y0": y0},
        )
    while True:
        m1, m2 = r.sample(range(-3, 4), 2)
        if (m1 + m2) % 2 == 0 and m1 != m2:
            break
    B = sp.Rational(-3 * (m1 + m2), 2)
    kv = 3 * m1 * m2
    y0 = r.randint(-8, 8)
    base = x**3 + B * x**2 + kv * x
    C = y0 - base.subs(x, m1)
    curve = base + C
    grad = 3 * x**2 + 2 * B * x + kk_
    text = multipart(f"The gradient function of a curve is \\(\\dfrac{{dy}}{{dx}} = {pl(grad)}\\), where \\(k\\) is a constant. The curve has a stationary point at \\(({m1}, {y0})\\).",
                     [("a", "Find the value of \\(k\\).", 1), ("b", "Find the equation of the curve (enter the expression for \\(y\\)).", 2),
                      ("c", "Find the \\(x\\)-coordinate of the other stationary point.", 1)])
    steps = [f"(a) At a stationary point \\(\\dfrac{{dy}}{{dx}} = 0\\): \\({pl(grad.subs(x, m1), kk_)} = 0\\), so \\(k = {kv}\\).",
             f"(b) \\(y = {L(base)} + C\\).",
             f"The curve passes through \\(({m1}, {y0})\\): \\({base.subs(x, m1)} + C = {y0}\\), so \\(C = {C}\\) and \\(y = {L(curve)}\\).",
             f"(c) \\(\\dfrac{{dy}}{{dx}} = {L(3 * x**2 + 2 * B * x + kv)} = 3(x {'-' if m1 > 0 else '+'} {abs(m1)})(x {'-' if m2 > 0 else '+'} {abs(m2)})\\)".replace("(x + 0)", "x").replace("(x - 0)", "x")
             + f", so the other stationary point is at \\(x = {m2}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(kv)), P("b", 2, A_expr(curve)), P("c", 1, A_num(m2))), 4, 3, steps,
        "The gradient function is the derivative; integrating it gives the curve up to a constant, fixed by a point on the curve.",
        "Use the stationary point twice: once for \\(\\frac{dy}{dx} = 0\\) (to find \\(k\\)) and once as a point on the curve (to find \\(C\\)).",
        quicker="For (c), the product of the roots of \\(3x^2 + bx + k\\) is \\(\\frac{k}{3}\\), so the other root is \\(\\frac{k}{3m}\\).",
        common_errors=[err(-kv, "careless error", "sign error", "Sign error solving for \\(k\\).", step=1, part="a"),
                       err(base, "incomplete reasoning", "constant of integration", "Use the point on the curve to find the constant of integration.", step=3, part="b")
                       if C != 0 else err(base + 1, "careless error", "constant of integration", "Recheck the constant.", step=3, part="b"),
                       err(-m2, "careless error", "sign error", "Sign error when factorising the gradient function.", step=4, part="c")],
        skill="Recover a curve from its gradient function and a stationary point.",
        checkpoints=[cp(base, "the primitive before C is found", step=2, part="b")],
        params={"form": "parts", "m1": m1, "m2": m2, "y0": y0},
    )
