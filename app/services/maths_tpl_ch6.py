"""Chapter 6 — The trigonometric functions (owner: maths). All angles are in radians."""
from __future__ import annotations

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_mcq, A_num, A_parts, A_prim, A_set, A_units, Generated, L, P, Rng, S, co, cp, err, mcq_options, multipart, nonzero,
    pick, pn, x,
)

pi = sp.pi
sin, cos, tan = sp.sin, sp.cos, sp.tan
DIFF = "differentiation rules"
INTG = "integration rules"
STAT = "stationary points"
TEV = "trig exact values"
STD = [pi / 6, pi / 4, pi / 3, pi / 2, 2 * pi / 3, 3 * pi / 4, 5 * pi / 6]


def arg(a, b=0) -> str:
    return L(a * x + b)


# ======================================================================= 6A ===
def t_6A(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b = pick(r, [2, 3, 4, 5, sp.Rational(1, 2)]), pick(r, [2, 3, 4, sp.Rational(1, 2), sp.Rational(1, 3)])
        fn_ = pick(r, ["sin", "cos"])
        dv = r.randint(-3, 3)
        f = a * getattr(sp, fn_)(b * x) + dv
        per = 2 * pi / b
        text = multipart(f"Consider \\(y = {L(f)}\\).", [("a", "State the amplitude.", 1), ("b", "State the period.", 1)])
        return Generated(
            text, A_parts(P("a", 1, A_num(a)), P("b", 1, A_num(per))), 2, 1,
            [f"(a) The amplitude is the coefficient of \\(\\{fn_}\\): \\({L(a)}\\)" + (f" (the vertical shift \\({dv}\\) moves the centre line, not the amplitude)." if dv else "."),
             f"(b) The period of \\(\\{fn_} bx\\) is \\(\\dfrac{{2\\pi}}{{b}} = \\dfrac{{2\\pi}}{{{L(b)}}} = {L(per)}\\)."],
            "For \\(y = a\\sin bx + d\\) or \\(y = a\\cos bx + d\\): amplitude \\(|a|\\), period \\(\\frac{2\\pi}{b}\\), centre line \\(y = d\\).",
            "Write the formula \\(\\frac{2\\pi}{b}\\) before substituting.",
            quicker="A larger \\(b\\) squeezes the graph horizontally, so the period gets shorter.",
            common_errors=[err(b * 2 * pi, "formula selection", "transformations", "The period is \\(\\frac{2\\pi}{b}\\), not \\(2\\pi b\\).", step=2, part="b"),
                           err(pi / b, "formula selection", "transformations", "\\(\\frac{\\pi}{b}\\) is the period of \\(\\tan bx\\); sine and cosine repeat every \\(\\frac{2\\pi}{b}\\).", step=2, part="b"),
                           err(a + dv, "interpretation", "transformations", "That is the maximum value; the amplitude is the distance from the centre line.", step=1, part="a")
                           if dv else err(2 * a, "interpretation", "transformations", "The amplitude is half the distance from minimum to maximum.", step=1, part="a")],
            skill="Read amplitude and period from an equation.",
            params={"form": "ap", "a": str(a), "b": str(b)},
        )
    if d == 2:
        T = pick(r, [4, 6, 8, 10, 12, 24])
        lo = r.randint(1, 10)
        hi = lo + 2 * r.randint(2, 8)
        a, dv = sp.Rational(hi - lo, 2), sp.Rational(hi + lo, 2)
        b = 2 * pi / T
        text = multipart(
            f"A quantity is modelled by \\(y = a\\cos(bt) + d\\), with \\(a > 0\\) and \\(b > 0\\). Its maximum value is \\({hi}\\), its minimum value is \\({lo}\\), and the pattern repeats every \\({T}\\) hours.",
            [("a", "Find \\(a\\).", 1), ("b", "Find \\(b\\).", 1), ("c", "Find \\(d\\).", 1)])
        return Generated(
            text, A_parts(P("a", 1, A_num(a)), P("b", 1, A_num(b)), P("c", 1, A_num(dv))), 3, 2,
            [f"(a) The amplitude is half the range: \\(a = \\dfrac{{{hi} - {lo}}}{{2}} = {L(a)}\\).",
             f"(b) The period is \\(\\dfrac{{2\\pi}}{{b}} = {T}\\), so \\(b = {L(b)}\\).",
             f"(c) The centre line is midway: \\(d = \\dfrac{{{hi} + {lo}}}{{2}} = {L(dv)}\\)."],
            "In a sinusoidal model the amplitude is half the range, the centre line is the average of the maximum and minimum, and \\(b = \\frac{2\\pi}{\\text{period}}\\).",
            "Write each relationship in words before substituting.",
            quicker=f"Check: \\(d + a = {hi}\\) and \\(d - a = {lo}\\).",
            common_errors=[err(hi - lo, "formula selection", "modelling", "The amplitude is half of max − min.", step=1, part="a"),
                           err(T, "formula selection", "modelling", "\\(b\\) is \\(\\frac{2\\pi}{\\text{period}}\\), not the period itself.", step=2, part="b"),
                           err(2 * pi * T, "formula selection", "modelling", "Period \\(= \\frac{2\\pi}{b}\\), so \\(b = \\frac{2\\pi}{\\text{period}}\\).", step=2, part="b"),
                           err(hi, "interpretation", "modelling", "\\(d\\) is the centre line, the average of max and min.", step=3, part="c")],
            skill="Fit a sinusoidal model to maximum, minimum and period.",
            params={"form": "fit", "hi": hi, "lo": lo, "T": T},
        )
    ctx = pick(r, ["depth", "wheel"])
    T = pick(r, [12, 24, 6, 8])
    a = r.randint(2, 6) if ctx == "depth" else pick(r, [10, 12, 15, 20])
    dv = a + r.randint(1, 8)
    s = 1 if ctx == "depth" else -1
    thr_kind = pick(r, ["half", "zero", "-half", "r3"])
    cval = {"half": sp.Rational(1, 2), "zero": 0, "-half": sp.Rational(-1, 2), "r3": sp.sqrt(3) / 2}[thr_kind]
    # D(t) >= dv + s*a*cval  <=>  s*cos(2 pi t / T) >= ... ; fraction of the cycle where cos(theta) >= c is (1/pi) acos(c)
    frac = sp.acos(cval) / pi
    dur = sp.nsimplify(T * frac)
    level = dv + a * cval
    m = pick(r, [T // 6, T // 4, T // 3]) if T % 12 == 0 else pick(r, [T // 4, T // 2])
    Dm = dv + s * a * cos(2 * pi * m / T)
    tmax = T if s > 0 else sp.Rational(T, 2)
    if ctx == "depth":
        stem = (f"The depth of water at a harbour entrance \\(t\\) hours after midnight is modelled by "
                f"\\(D = {dv} + {a}\\cos\\left(\\dfrac{{\\pi t}}{{{T // 2}}}\\right)\\) metres.").replace("{\\pi t}{1}", "\\pi t")
        what, unit, lvl = "depth", "m", f"the depth is at least \\({L(level)}\\) metres"
    else:
        stem = (f"The height of a seat on a Ferris wheel \\(t\\) minutes after it passes the lowest point is "
                f"\\(H = {dv} - {a}\\cos\\left(\\dfrac{{\\pi t}}{{{T // 2}}}\\right)\\) metres.")
        what, unit, lvl = "height", "m", f"the seat is at least \\({L(level)}\\) metres high"
    tu = "hours" if ctx == "depth" else "minutes"
    text = multipart(stem, [("a", f"Find the {what} when \\(t = {m}\\).", 1), ("b", f"Find the maximum {what}.", 1),
                            ("c", f"Find the first time \\(t > 0\\) at which the {what} is greatest.", 1),
                            ("d", f"For how many {tu} in each cycle is it true that {lvl}?", 2)])
    theta = f"\\dfrac{{\\pi t}}{{{T // 2}}}"
    steps = [f"(a) \\({'D' if s > 0 else 'H'} = {dv} {'+' if s > 0 else '-'} {a}\\cos\\left({L(2 * pi * m / T)}\\right) = {dv} {'+' if s > 0 else '-'} {a}\\times {pn(cos(2 * pi * m / T))} = {L(Dm)}\\) m.",
             f"(b) \\(\\cos\\) ranges from \\(-1\\) to \\(1\\), so the maximum is \\({dv} + {a} = {dv + a}\\) m.",
             f"(c) The maximum needs \\(\\cos\\left({theta}\\right) = {'1' if s > 0 else '-1'}\\), i.e. \\({theta} = {'2\\pi' if s > 0 else '\\pi'}\\): \\(t = {L(tmax)}\\).",
             f"(d) The condition is \\(\\cos\\left({theta}\\right) {'\\ge' if s > 0 else '\\le'} {L(s * cval)}\\).",
             f"In one cycle \\(0 \\le {theta} \\le 2\\pi\\) this holds on a total angle of \\(2\\cos^{{-1}}({L(cval)}) = {L(2 * sp.acos(cval))}\\), i.e. a fraction \\({L(frac)}\\) of the period: \\({L(frac)}\\times {T} = {L(dur)}\\) {tu}."]
    return Generated(
        text,
        A_parts(P("a", 1, A_units(Dm, unit)), P("b", 1, A_units(dv + a, unit)), P("c", 1, A_num(tmax)), P("d", 2, A_num(dur))), 5, 3, steps,
        "A sinusoidal model \\(y = d \\pm a\\cos(bt)\\) has centre line \\(d\\), amplitude \\(a\\) and period \\(\\frac{2\\pi}{b}\\); questions about 'how long' become trigonometric inequalities over one period.",
        "Sketch one period of the graph with the threshold line drawn — the time intervals can then be read off and checked.",
        quicker="By symmetry, the time above a level is the same fraction of every period, so work with the angle and convert at the end.",
        common_errors=[err(dv + a * cos(2 * pi * m / T) * (-s), "careless error", "sign error", "Check the sign in front of the cosine.", step=1, part="a"),
                       err(a, "interpretation", "modelling", "That is the amplitude; the maximum is centre line + amplitude.", step=2, part="b"),
                       err(sp.Rational(T, 2) if s > 0 else T, "interpretation", "modelling", "Check whether the model starts at a maximum or a minimum.", step=3, part="c"),
                       err(T - dur, "interpretation", "modelling", "That is the time below the level.", step=5, part="d"),
                       err(dur / 2, "incomplete reasoning", "modelling", "The condition holds on two intervals in each cycle (either side of the peak).", step=5, part="d")],
        skill="Use a trigonometric model: values, maximum, timing and duration.",
        params={"form": "model", "d": dv, "a": a, "s": s, "T": T, "m": m, "c": str(cval)},
    )


# ======================================================================= 6B ===
def t_6B(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, -2, 4]), pick(r, [2, 3, 4, 5, -1]), pick(r, [0, 0, 1, -2, 3])
        f = A * pick(r, [sin, cos, tan])(a * x + b)
        fp = sp.diff(f, x)
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), 1, 1,
            [f"\\(\\dfrac{{d}}{{dx}}\\sin u = u'\\cos u\\), \\(\\dfrac{{d}}{{dx}}\\cos u = -u'\\sin u\\), \\(\\dfrac{{d}}{{dx}}\\tan u = u'\\sec^2 u\\).",
             f"\\(\\dfrac{{dy}}{{dx}} = {L(fp)}\\)."],
            "The derivatives of \\(\\sin\\), \\(\\cos\\) and \\(\\tan\\) (in radians), combined with the chain rule for the inside.",
            "Check the sign: only the derivative of \\(\\cos\\) brings a minus sign.",
            quicker="Differentiate the outside, then multiply by the derivative of the inside.",
            common_errors=[err(fp / a, "careless error", "chain rule", f"Multiply by the derivative of the inside, \\({a}\\).", step=2),
                           err(-fp, "careless error", "sign error", "\\(\\frac{d}{dx}\\sin x = \\cos x\\) and \\(\\frac{d}{dx}\\cos x = -\\sin x\\): check the sign.", step=2)],
            skill="Differentiate a trigonometric function of a linear expression.",
            params={"form": "diff", "f": str(f)},
        )
    if d == 2:
        form = pick(r, ["prod", "quot", "chain", "power"])
        a = pick(r, [1, 2, 3])
        if form == "prod":
            f = x**pick(r, [1, 2]) * pick(r, [sin, cos])(a * x)
            hint, tag = "Product rule: \\((uv)' = u'v + uv'\\).", "product rule"
        elif form == "quot":
            f = sin(a * x) / x
            hint, tag = "Quotient rule: \\(\\left(\\dfrac{u}{v}\\right)' = \\dfrac{vu' - uv'}{v^2}\\).", "quotient rule"
        elif form == "chain":
            f = cos(x**2 + a)
            hint, tag = "Chain rule with the inside \\(x^2 + " + str(a) + "\\).", "chain rule"
        else:
            f = pick(r, [sin, cos])(x) ** pick(r, [2, 3])
            hint, tag = "Chain rule: power of a trigonometric function, \\(\\sin^n x = (\\sin x)^n\\).", "chain rule"
        fp = sp.diff(f, x)
        wrong = {"prod": sp.diff(f.args[0], x) * sp.diff(f.args[1], x) if f.is_Mul and len(f.args) == 2 else -fp,
                 "quot": (sin(a * x) - x * a * cos(a * x)) / x**2, "chain": -sin(x**2 + a), "power": -fp}[form]
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), 2, 2, [hint, f"\\(\\dfrac{{dy}}{{dx}} = {L(sp.factor(fp))}\\)."],
            "Trigonometric functions combine with the product, quotient and chain rules exactly as other functions do.",
            "Write \\(u\\), \\(v\\) and their derivatives before combining.",
            quicker="Check one value numerically on the calculator (in radians).",
            common_errors=[err(wrong, "formula selection" if form != "power" else "careless error", tag,
                               {"prod": "That is \\(u'v'\\): the product rule is \\(u'v + uv'\\).",
                                "quot": "The quotient rule is \\(\\frac{vu' - uv'}{v^2}\\): the order in the numerator matters.",
                                "chain": "Multiply by the derivative of the inside, \\(2x\\).",
                                "power": "Check the sign of the derivative of the trigonometric function."}[form], step=2)],
            skill=f"Differentiate trigonometric functions with the {tag}.",
            checkpoints=[cp(fp, "the derivative", step=2)],
            params={"form": "diff", "f": str(f)},
        )
    b = pick(r, [1, 2, 3])
    sq = pick(r, ["sin", "cos"])
    f = getattr(sp, sq)(b * x) ** 2
    fp = sp.simplify(sp.diff(f, x))
    f2 = sp.diff(fp, x)
    x0 = pick(r, [pi / 6, pi / 8, pi / 12, pi / 4]) / b
    v1, v2 = sp.nsimplify(fp.subs(x, x0)), sp.nsimplify(f2.subs(x, x0))
    sgn_ = 1 if sq == "sin" else -1
    text = multipart(f"Let \\(f(x) = \\{sq}^2 {'x' if b == 1 else '(' + str(b) + 'x)'}\\).",
                     [("a", "Find \\(f'(x)\\).", 2), ("b", "Find \\(f''(x)\\).", 1),
                      ("c", f"Find the exact value of \\(f'\\left({L(x0)}\\right)\\).", 1), ("d", f"Find the exact value of \\(f''\\left({L(x0)}\\right)\\).", 1)])
    steps = [f"(a) Chain rule: \\(f'(x) = 2\\{sq}({arg(b)})\\times \\left({'' if sq == 'sin' else '-'}{co(b, '')}\\{'cos' if sq == 'sin' else 'sin'}({arg(b)})\\right)\\).",
             f"\\(= {'' if sgn_ > 0 else '-'}{co(2 * b, '')}\\sin({arg(b)})\\cos({arg(b)}) = {L(fp)}\\) (using \\(2\\sin\\theta\\cos\\theta = \\sin 2\\theta\\)).",
             f"(b) \\(f''(x) = {L(f2)}\\).",
             f"(c) \\(f'\\left({L(x0)}\\right) = {L(v1)}\\).",
             f"(d) \\(f''\\left({L(x0)}\\right) = {L(v2)}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_expr(fp)), P("b", 1, A_expr(f2)), P("c", 1, A_num(v1)), P("d", 1, A_num(v2))), 5, 3, steps,
        "A power of a trigonometric function needs the chain rule twice: once for the power, once for the inside \\(bx\\).",
        "Write \\(\\sin^2 u\\) as \\((\\sin u)^2\\) before differentiating; use exact values, not a calculator, in (c) and (d).",
        quicker="\\(2\\sin u\\cos u = \\sin 2u\\) makes the second derivative a one-step chain rule.",
        common_errors=[err(2 * getattr(sp, sq)(b * x), "careless error", "chain rule", "Multiply by the derivative of the inside function too.", step=1, part="a"),
                       err(-fp, "careless error", "sign error", "Check the sign of the derivative of the trigonometric function.", step=1, part="a"),
                       err(-v1, "careless error", "sign error", "Recheck the sign of your exact value.", step=4, part="c")],
        skill="Differentiate powers of trigonometric functions and evaluate exactly.",
        checkpoints=[cp(fp, "the first derivative", step=2, part="b")],
        params={"form": "parts", "f": str(f), "x0": str(x0)},
    )


# ======================================================================= 6C ===
_TRIG_PTS = {"sin": [pi / 6, pi / 4, pi / 3, 2 * pi / 3, 5 * pi / 6], "cos": [pi / 6, pi / 4, pi / 3, 2 * pi / 3], "tan": [pi / 6, pi / 4, pi / 3]}


def t_6C(r: Rng, d: int) -> Generated:
    if d == 1:
        fname = pick(r, ["sin", "cos", "tan"])
        A = pick(r, [1, 2, 3, 4])
        x0 = pick(r, _TRIG_PTS[fname])
        f = A * getattr(sp, fname)(x)
        g = sp.nsimplify(sp.diff(f, x).subs(x, x0))
        return Generated(
            f"Find the exact gradient of the tangent to \\(y = {L(f)}\\) at the point where \\(x = {L(x0)}\\).",
            A_num(g), 1, 1,
            [f"\\(y' = {L(sp.diff(f, x))}\\), so at \\(x = {L(x0)}\\) the gradient is \\({L(g)}\\)."],
            "The gradient of the tangent is the derivative evaluated at the point, using exact values.",
            "Differentiate first; then use the exact-value triangles, not a calculator.",
            quicker="Sketch the curve: the sign of the gradient must match whether it is rising or falling there.",
            common_errors=[err(sp.nsimplify(f.subs(x, x0)), "conceptual", DIFF, "That is the \\(y\\)-value; the gradient is \\(y'\\).", step=1),
                           err(-g, "careless error", "sign error", "Check the sign: \\(\\frac{d}{dx}\\cos x = -\\sin x\\).", step=1)],
            skill="Find the gradient of a trigonometric curve exactly.",
            params={"form": "grad", "f": str(f), "x0": str(x0)},
        )
    if d == 2:
        fname = pick(r, ["sin", "cos", "tan"])
        x0 = pick(r, _TRIG_PTS[fname][:3])
        A = pick(r, [1, 2])
        f = A * getattr(sp, fname)(x)
        m = sp.nsimplify(sp.diff(f, x).subs(x, x0))
        y0 = sp.nsimplify(f.subs(x, x0))
        tan_ = m * (x - x0) + y0
        return Generated(
            f"Find the equation of the tangent to \\(y = {L(f)}\\) at the point where \\(x = {L(x0)}\\). (Enter the expression for \\(y\\).)",
            A_expr(tan_), 3, 2,
            [f"The point: \\(y = {co(A, '')}\\{fname}\\left({L(x0)}\\right) = {L(y0)}\\).",
             f"The gradient: \\(y' = {L(sp.diff(f, x))}\\), so \\(m = {L(m)}\\).",
             f"\\(y - {pn(y0)} = {co(m, '') if m.is_positive else pn(m)}\\left(x - {L(x0)}\\right)\\), so \\(y = {L(sp.expand(tan_))}\\)."],
            "The tangent line passes through the point of contact with gradient \\(f'(x_0)\\); with trigonometric curves both are exact values.",
            "Leave \\(\\pi\\) in the equation: it is an exact constant.",
            quicker="Check that your line passes through the point by substituting \\(x_0\\).",
            common_errors=[err(m * x + y0, "incomplete reasoning", "algebra", f"Use \\(y - y_1 = m(x - x_1)\\) with \\(x_1 = {L(x0)}\\).", step=3),
                           err(-m * (x - x0) + y0, "careless error", "sign error", "Check the sign of the gradient.", step=2)],
            skill="Find a tangent to a trigonometric curve.",
            checkpoints=[cp(sp.diff(f, x), "the derivative", step=2)],
            params={"form": "tangent", "f": str(f), "x0": str(x0)},
        )
    kind = pick(r, ["x+2cos", "x-2sin", "r3x+2cos", "x+r2cos"])
    if kind == "x+2cos":
        f, sols = x + 2 * cos(x), [pi / 6, 5 * pi / 6]
    elif kind == "x-2sin":
        f, sols = x - 2 * sin(x), [pi / 3, 5 * pi / 3]
    elif kind == "r3x+2cos":
        f, sols = sp.sqrt(3) * x + 2 * cos(x), [pi / 3, 2 * pi / 3]
    else:
        f, sols = x + sp.sqrt(2) * cos(x), [pi / 4, 3 * pi / 4]
    fp = sp.diff(f, x)
    f2 = sp.diff(f, x, 2)
    first = sols[0]
    nat = "A" if sp.nsimplify(f2.subs(x, first)) < 0 else "B"
    mx = [v for v in sols if sp.nsimplify(f2.subs(x, v)) < 0][0]
    ymax = sp.nsimplify(f.subs(x, mx))
    opts = mcq_options("a local maximum", "a local minimum", "a horizontal point of inflection")
    text = multipart(f"Consider the curve \\(y = {L(f)}\\) for \\(0 \\le x \\le 2\\pi\\).",
                     [("a", "Find \\(\\dfrac{dy}{dx}\\).", 1), ("b", "Find the \\(x\\)-coordinates of the stationary points.", 2),
                      ("c", f"Determine the nature of the stationary point at \\(x = {L(first)}\\).", 1),
                      ("d", "Find the exact \\(y\\)-coordinate of the local maximum.", 1)])
    steps = [f"(a) \\(\\dfrac{{dy}}{{dx}} = {L(fp)}\\).",
             f"(b) \\({L(fp)} = 0\\) gives \\(\\{'sin' if 'cos' in kind else 'cos'} x = {L(sp.nsimplify(({'x+2cos': sin(pi / 6), 'x-2sin': cos(pi / 3), 'r3x+2cos': sin(pi / 3), 'x+r2cos': sin(pi / 4)})[kind]))}\\).",
             f"In \\([0, 2\\pi]\\): \\(x = {L(sols[0])}\\) or \\(x = {L(sols[1])}\\).",
             f"(c) \\(\\dfrac{{d^2y}}{{dx^2}} = {L(f2)}\\), which at \\(x = {L(first)}\\) is \\({L(sp.nsimplify(f2.subs(x, first)))}\\) {'< 0: a local maximum' if nat == 'A' else '> 0: a local minimum'}.",
             f"(d) The local maximum is at \\(x = {L(mx)}\\): \\(y = {L(ymax)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(fp)), P("b", 2, A_set(sols)), P("c", 1, A_mcq(nat, opts)), P("d", 1, A_num(ymax))), 5, 3, steps,
        "Stationary points of trigonometric curves come from solving a trigonometric equation over the given domain; the second derivative classifies them.",
        "List every solution in the domain — use the quadrant (ASTC) diagram — and keep answers exact.",
        quicker="Sketch \\(y'\\) as a shifted sine or cosine wave: its zeros and sign changes give the stationary points and their nature together.",
        common_errors=[err(S(sols[0]), "incomplete reasoning", TEV, "There is a second solution in \\([0, 2\\pi]\\): use the symmetry of the graph.", step=3, part="b"),
                       err("B" if nat == "A" else "A", "conceptual", STAT, "Check the sign of the second derivative at that point.", step=4, part="c"),
                       err(S(-sols[0], sols[0]), "interpretation", "domain/range", "Only solutions in \\(0 \\le x \\le 2\\pi\\) count.", step=3, part="b")],
        skill="Find and classify stationary points of a trigonometric curve.",
        checkpoints=[cp(fp, "the derivative", step=1, part="b")],
        params={"form": "parts", "f": str(f)},
    )


# ======================================================================= 6D ===
def t_6D(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, 4, 6]), pick(r, [2, 3, 4, 5, -1]), pick(r, [0, 0, 1, -2])
        kind = pick(r, ["sin", "cos", "sec2"])
        if kind == "sec2":
            integrand = A / cos(a * x + b) ** 2
            F = sp.Rational(A, a) * tan(a * x + b)
            show = f"\\dfrac{{{A}}}{{\\cos^2({arg(a, b)})}}" if A != 1 else f"\\sec^2({arg(a, b)})"
            if A != 1:
                show = f"{A}\\sec^2({arg(a, b)})"
        else:
            integrand = A * getattr(sp, kind)(a * x + b)
            F = sp.integrate(integrand, x)
            show = L(integrand)
        return Generated(
            f"Find \\(\\displaystyle\\int {show}\\,dx\\).",
            A_prim(F), 1, 1,
            [f"\\(\\int\\cos(ax + b)\\,dx = \\tfrac1a\\sin(ax + b)\\), \\(\\int\\sin(ax + b)\\,dx = -\\tfrac1a\\cos(ax + b)\\), \\(\\int\\sec^2(ax + b)\\,dx = \\tfrac1a\\tan(ax + b)\\).",
             f"So the primitive is \\({L(F)} + C\\)."],
            "Integrating reverses differentiation: divide by the coefficient of \\(x\\), and note the sign for \\(\\sin\\).",
            "Check by differentiating your answer.",
            quicker="\\(\\int\\sin = -\\cos\\) because \\(\\frac{d}{dx}\\cos = -\\sin\\).",
            common_errors=[err(F * a * a, "conceptual", "chain rule", "Integrating divides by the coefficient of \\(x\\); it does not multiply.", step=2),
                           err(-F, "careless error", "sign error", "Check the sign: \\(\\int\\sin x\\,dx = -\\cos x\\).", step=2)],
            skill="Integrate a basic trigonometric function.",
            params={"form": "prim", "f": str(integrand)},
        )
    if d == 2:
        A, a = pick(r, [1, 2, 3, 4, 6]), pick(r, [1, 2, 3])
        th = pick(r, [pi / 6, pi / 4, pi / 3, pi / 2])
        kind = pick(r, ["sin", "cos"])
        integrand = A * getattr(sp, kind)(a * x)
        hi = th / a
        val = sp.nsimplify(sp.integrate(integrand, (x, 0, hi)))
        Fx = sp.integrate(integrand, x)
        return Generated(
            f"Evaluate \\(\\displaystyle\\int_0^{{{L(hi)}}} {L(integrand)}\\,dx\\), giving an exact answer.",
            A_num(val), 2, 2,
            [f"\\(\\displaystyle\\int_0^{{{L(hi)}}} {L(integrand)}\\,dx = \\Big[{L(Fx)}\\Big]_0^{{{L(hi)}}}\\).",
             f"\\(= {L(sp.nsimplify(Fx.subs(x, hi)))} - {pn(sp.nsimplify(Fx.subs(x, 0)))} = {L(val)}\\)."],
            "Evaluate the primitive at both limits using exact values; \\(\\cos 0 = 1\\) is the usual trap at the lower limit.",
            "Keep the radian exact values — no calculator.",
            quicker="Area check: the integrand is positive on the interval, so the answer must be positive.",
            common_errors=[err(sp.nsimplify(Fx.subs(x, hi)), "incomplete reasoning", "limits of integration", "Subtract the value at the lower limit (\\(\\cos 0 = 1\\)).", step=2)
                           if Fx.subs(x, 0) != 0 else err(val * a * a, "conceptual", "chain rule", "Divide by the coefficient of \\(x\\).", step=1),
                           err(-val, "careless error", "sign error", "Check the sign of the primitive.", step=1)],
            skill="Evaluate a definite trigonometric integral exactly.",
            params={"form": "def", "f": str(integrand), "lo": "0", "hi": str(hi)},
        )
    a = pick(r, [1, 2, 3])
    D = sp.diff(x * sin(a * x), x)
    F = x * sin(a * x) / a + cos(a * x) / a**2
    hi = pi / (2 * a)
    val = sp.nsimplify(F.subs(x, hi) - F.subs(x, 0))
    ax = "x" if a == 1 else f"{a}x"
    text = multipart(
        "",
        [("a", f"Differentiate \\(x\\sin {ax}\\).", 1), ("b", f"Hence find \\(\\displaystyle\\int x\\cos {ax}\\,dx\\).", 2),
         ("c", f"Hence evaluate \\(\\displaystyle\\int_0^{{{L(hi)}}} x\\cos {ax}\\,dx\\), giving an exact answer.", 2)])
    steps = [f"(a) Product rule: \\(\\dfrac{{d}}{{dx}}(x\\sin {ax}) = \\sin {ax} + {co(a, '')}x\\cos {ax}\\).",
             f"(b) So \\(x\\sin {ax} = \\displaystyle\\int \\sin {ax}\\,dx + {co(a, '')}\\int x\\cos {ax}\\,dx = -{L(cos(a * x) / a)} + {co(a, '')}\\int x\\cos {ax}\\,dx\\).",
             f"Rearranging: \\(\\displaystyle\\int x\\cos {ax}\\,dx = {L(F)} + C\\).",
             f"(c) \\(\\Big[{L(F)}\\Big]_0^{{{L(hi)}}} = {L(sp.nsimplify(F.subs(x, hi)))} - {pn(sp.nsimplify(F.subs(x, 0)))} = {L(val)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(D)), P("b", 2, A_prim(F)), P("c", 2, A_num(val))), 5, 3, steps,
        "A product-rule derivative, read backwards, gives an integral that has no direct rule in this course.",
        "In (b) integrate the whole line from (a), then rearrange for the integral you want.",
        quicker="Check (b) by differentiating: the \\(\\sin\\) terms must cancel.",
        common_errors=[err(a * x * cos(a * x), "formula selection", "product rule", "Use the product rule: both \\(x\\) and \\(\\sin\\) vary.", step=1, part="a"),
                       err(x * sin(a * x) / a - cos(a * x) / a**2, "careless error", "sign error", "\\(\\int\\sin ax\\,dx = -\\frac1a\\cos ax\\): watch the double negative.", step=3, part="b"),
                       err(sp.nsimplify(F.subs(x, hi)), "incomplete reasoning", "limits of integration", "At \\(x = 0\\), \\(\\cos 0 = 1\\): subtract that value.", step=4, part="c")],
        skill="Integrate x cos(ax) using a given derivative.",
        checkpoints=[cp(D, "the derivative from (a)", step=1, part="b")],
        params={"form": "parts", "a": a},
    )


# ======================================================================= 6E ===
def t_6E(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a = pick(r, [1, 2, 3, 4, 5]), pick(r, [1, 2, 3, 4])
        area = sp.Rational(2 * A, a)
        ax = "x" if a == 1 else f"{a}x"
        hi = pi / a
        return Generated(
            f"Find the area of the region between the curve \\(y = {co(A, '')}\\sin {ax}\\) and the \\(x\\)-axis from \\(x = 0\\) to \\(x = {L(hi)}\\).",
            A_units(area, "units^2"), 2, 1,
            [f"The curve is above the axis on \\([0, {L(hi)}]\\) (one arch).",
             f"\\(A = \\displaystyle\\int_0^{{{L(hi)}}} {co(A, '')}\\sin {ax}\\,dx = \\Big[{L(-A * cos(a * x) / a)}\\Big]_0^{{{L(hi)}}} = {L(sp.Rational(A, a))} + {L(sp.Rational(A, a))} = {L(area)}\\) square units."],
            "One arch of \\(\\sin ax\\) runs from \\(0\\) to \\(\\frac{\\pi}{a}\\) and lies above the axis.",
            "Substitute both limits carefully: \\(\\cos\\pi = -1\\) and \\(\\cos 0 = 1\\).",
            quicker="One arch of \\(y = \\sin x\\) has area exactly 2; stretching scales it.",
            common_errors=[err(0, "conceptual", "area below the axis", "The cosine values at the limits are \\(-1\\) and \\(1\\); their difference is not zero.", step=2),
                           err(2 * A * a, "conceptual", "chain rule", "Divide by the coefficient of \\(x\\).", step=2)],
            skill="Find the area under one arch of a sine curve.",
            params={"form": "area", "f": str(A * sin(a * x)), "lo": "0", "hi": str(hi)},
        )
    if d == 2:
        A = pick(r, [1, 2, 3, 4])
        if r.random() < 0.5:
            area = 2 * sp.sqrt(2) * A
            return Generated(
                f"Find the exact area enclosed between the curves \\(y = {co(A, '')}\\sin x\\) and \\(y = {co(A, '')}\\cos x\\) from \\(x = \\dfrac{{\\pi}}{{4}}\\) to \\(x = \\dfrac{{5\\pi}}{{4}}\\).",
                A_units(area, "units^2"), 3, 2,
                ["The curves meet where \\(\\tan x = 1\\): at \\(x = \\frac{\\pi}{4}\\) and \\(x = \\frac{5\\pi}{4}\\); between them \\(\\sin x \\ge \\cos x\\).",
                 f"\\(A = \\displaystyle\\int_{{\\pi/4}}^{{5\\pi/4}} {co(A, '')}(\\sin x - \\cos x)\\,dx = {co(A, '')}\\big[-\\cos x - \\sin x\\big]_{{\\pi/4}}^{{5\\pi/4}}\\).",
                 f"\\(= {co(A, '')}\\big((\\tfrac{{\\sqrt2}}{{2}} + \\tfrac{{\\sqrt2}}{{2}}) - (-\\tfrac{{\\sqrt2}}{{2}} - \\tfrac{{\\sqrt2}}{{2}})\\big) = {L(area)}\\) square units."],
                "Area between curves: integrate (upper − lower) between consecutive intersections.",
                "Say which curve is on top, e.g. test \\(x = \\frac{\\pi}{2}\\).",
                quicker="Exact values at \\(\\frac{5\\pi}{4}\\) are the negatives of those at \\(\\frac{\\pi}{4}\\).",
                common_errors=[err(-area, "careless error", "sign error", "Integrate upper minus lower.", step=2),
                               err(0, "conceptual", "area below the axis", "Integrate the difference of the curves, not each curve's signed area.", step=2)],
                skill="Find the area between sine and cosine curves.",
                params={"form": "between", "A": A},
            )
        a = pick(r, [1, 2, 3])
        ax = "x" if a == 1 else f"{a}x"
        area = sp.Rational(2 * A, a)
        hi = pi / a
        return Generated(
            f"Find the total area between the curve \\(y = {co(A, '')}\\cos {ax}\\) and the \\(x\\)-axis from \\(x = 0\\) to \\(x = {L(hi)}\\).",
            A_units(area, "units^2"), 3, 2,
            [f"The curve crosses the axis at \\(x = {L(hi / 2)}\\): above it before, below it after.",
             f"\\(\\displaystyle\\int_0^{{{L(hi / 2)}}} = {L(sp.Rational(A, a))}\\) and \\(\\displaystyle\\int_{{{L(hi / 2)}}}^{{{L(hi)}}} = -{L(sp.Rational(A, a))}\\).",
             f"Total area \\(= {L(sp.Rational(A, a))} + {L(sp.Rational(A, a))} = {L(area)}\\) square units."],
            "Where a curve dips below the axis its integral is negative: split at the intercept and add the areas.",
            "Sketch first and mark where the curve crosses the axis.",
            quicker="The two halves are congruent by symmetry, so double the first.",
            common_errors=[err(0, "conceptual", "area below the axis", "The signed areas cancel; area must be counted positively on each side.", step=1),
                           err(sp.Rational(A, a), "incomplete reasoning", "area below the axis", "Add the area of the part below the axis.", step=3)],
            skill="Find the total area for a curve crossing the axis.",
            params={"form": "total", "f": str(A * cos(a * x)), "lo": "0", "hi": str(hi)},
        )
    kv = pick(r, [1, 2, 3, 4])
    lvl = pick(r, ["half", "r2", "r3"])
    v, al = {"half": (sp.Rational(1, 2), pi / 6), "r2": (sp.sqrt(2) / 2, pi / 4), "r3": (sp.sqrt(3) / 2, pi / 3)}[lvl]
    area = sp.nsimplify(kv * (2 * cos(al) - v * (pi - 2 * al)))
    text = multipart(f"The curve \\(y = {co(kv, '')}\\sin x\\) and the line \\(y = {L(kv * v)}\\) are drawn for \\(0 \\le x \\le \\pi\\).",
                     [("a", "Find the \\(x\\)-coordinates of the points of intersection.", 2),
                      ("b", "Find the exact area of the region above the line and below the curve.", 3)])
    steps = [f"(a) \\({co(kv, '')}\\sin x = {L(kv * v)}\\) gives \\(\\sin x = {L(v)}\\), so \\(x = {L(al)}\\) or \\(x = {L(pi - al)}\\).",
             f"(b) \\(A = \\displaystyle\\int_{{{L(al)}}}^{{{L(pi - al)}}} \\left({co(kv, '')}\\sin x - {L(kv * v)}\\right)dx = \\Big[-{co(kv, '')}\\cos x - {co(kv * v, 'x')}\\Big]_{{{L(al)}}}^{{{L(pi - al)}}}\\).",
             f"\\(= {co(kv, '')}\\big(\\cos{L(al)} - \\cos{L(pi - al)}\\big) - {co(kv * v, '')}\\left({L(pi - al)} - {L(al)}\\right) = {L(area)}\\) square units."]
    return Generated(
        text, A_parts(P("a", 2, A_set([al, pi - al])), P("b", 3, A_units(area, "units^2"))), 5, 3, steps,
        "Find the intersections from an exact-value equation, then integrate (curve − line) between them.",
        "Use the symmetry of \\(\\sin x\\) about \\(x = \\frac{\\pi}{2}\\) for the second intersection.",
        quicker="The region is symmetric about \\(x = \\frac{\\pi}{2}\\): integrate from the first intersection to \\(\\frac{\\pi}{2}\\) and double.",
        common_errors=[err(S(al), "incomplete reasoning", TEV, "There are two solutions in \\([0, \\pi]\\).", step=1, part="a"),
                       err(sp.nsimplify(kv * 2 * cos(al)), "incomplete reasoning", "area below the axis", "Subtract the area under the line (a rectangle).", step=3, part="b"),
                       err(-area, "careless error", "sign error", "Integrate curve minus line.", step=2, part="b")],
        skill="Find an area between a sine curve and a horizontal line.",
        checkpoints=[cp(kv * sin(x) - kv * v, "the difference curve − line", step=2, part="b")],
        params={"form": "parts", "k": kv, "v": str(v)},
    )
