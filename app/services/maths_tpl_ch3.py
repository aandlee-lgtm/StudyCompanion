"""Chapter 3 — Integration (owner: maths).

Only algebraic integrands (polynomials, powers and roots) are used: exponential, logarithmic and
trigonometric integrals come in chapters 4–6 of the learning sequence."""
from __future__ import annotations

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_mcq, A_num, A_parts, A_prim, A_round, A_set, A_units, Generated, L, P, Rng, S, co, cp, err, pn, rnd, mcq_options, multipart, nonzero,
    pick, pl, x,
)

INTG = "integration rules"
LIM = "limits of integration"
AREA = "area below the axis"
kk = sp.Symbol("k")


def I(lo, hi, f) -> str:  # noqa: E743
    """LaTeX for a definite integral."""
    return f"\\displaystyle\\int_{{{L(sp.sympify(lo))}}}^{{{L(sp.sympify(hi))}}} \\left({_show(f)}\\right)dx"


def _show(f) -> str:
    f = sp.sympify(f)
    return pl(f) if f.is_Add and f.is_polynomial(x) else L(f)


def Iu(f) -> str:
    return f"\\displaystyle\\int \\left({_show(f)}\\right)dx"


def _defint(f, lo, hi):
    return sp.nsimplify(sp.integrate(f, (x, lo, hi)))


# ----------------------------------------------------------------------- 3A ---
def t_3A(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            m, c, b = r.randint(1, 4), r.randint(1, 6), r.randint(2, 6)
            f = m * x + c
            top = m * b + c
            val = sp.Rational(b * (c + top), 2)
            return Generated(
                f"By sketching the graph and using the area of a trapezium (do not find a primitive), evaluate \\({I(0, b, f)}\\).",
                A_num(val), 2, 1,
                [f"The line \\(y = {L(f)}\\) is above the \\(x\\)-axis on \\([0, {b}]\\), so the integral is the area of the trapezium under it.",
                 f"Its parallel sides are \\(y(0) = {c}\\) and \\(y({b}) = {top}\\), and its width is \\({b}\\): area \\(= \\tfrac{{1}}{{2}}\\times {b}\\times({c} + {top}) = {L(val)}\\)."],
                "When a function is positive, its definite integral is the area between its graph and the \\(x\\)-axis.",
                "Show the sketch with the heights marked: the method mark is for recognising the shape.",
                quicker="Width × average height: the average of the end heights of a straight line.",
                common_errors=[err(b * top, "conceptual", LIM, "That is a rectangle of height \\(y({b})\\): the region is a trapezium.", step=2),
                               err(b * c, "incomplete reasoning", LIM, "You found only the rectangle under \\(y = {c}\\); add the triangle on top.".replace("{c}", str(c)), step=2)],
                skill="Evaluate a definite integral as the area of a trapezium.",
                params={"form": "geom", "f": str(f), "lo": 0, "hi": b},
            )
        rad = r.randint(2, 7)
        half = r.random() < 0.5
        lo = -rad if half else 0
        val = sp.pi * rad**2 / (2 if half else 4)
        shape = "semicircle" if half else "quarter-circle"
        return Generated(
            f"By identifying the region as part of a circle, evaluate \\({I(lo, rad, sp.sqrt(rad**2 - x**2))}\\).",
            A_num(val), 2, 1,
            [f"\\(y = \\sqrt{{{rad**2} - x^2}}\\) is the upper half of the circle \\(x^2 + y^2 = {rad**2}\\), radius \\({rad}\\).",
             f"From \\(x = {lo}\\) to \\(x = {rad}\\) the region is a {shape}: area \\(= \\tfrac{{1}}{{{2 if half else 4}}}\\pi\\times {rad}^2 = {L(val)}\\)."],
            "A definite integral of a positive function is an area, so known shapes can be used instead of a primitive.",
            "Name the shape and its radius before calculating.",
            quicker="Square both sides: \\(y^2 = r^2 - x^2\\) is a circle, and the square root keeps the top half.",
            common_errors=[err(sp.pi * rad**2, "interpretation", LIM, f"That is the whole circle; the limits cut out a {shape}.", step=2),
                           err(sp.pi * rad**2 / (4 if half else 2), "interpretation", LIM, "Check which part of the circle the limits cover.", step=2),
                           err(sp.pi * rad, "formula selection", LIM, "Area of a circle is \\(\\pi r^2\\).", step=2)],
            skill="Evaluate a definite integral from the area of part of a circle.",
            params={"form": "geom", "f": str(sp.sqrt(rad**2 - x**2)), "lo": lo, "hi": rad},
        )
    if d == 2:
        a, c = r.randint(-4, 1), r.randint(1, 3)
        b = c + r.randint(1, 5)
        a = min(a, c - 1)
        absval = r.random() < 0.4
        f = sp.Abs(x - c) if absval else x - c
        above, below = sp.Rational((b - c) ** 2, 2), sp.Rational((c - a) ** 2, 2)
        val = above + below if absval else above - below
        other = above - below if absval else above + below
        fl = f"\\left|x - {c}\\right|" if absval else f"\\left({L(x - c)}\\right)"
        return Generated(
            f"Use areas (do not find a primitive) to evaluate \\(\\displaystyle\\int_{{{a}}}^{{{b}}} {fl}\\,dx\\).",
            A_num(val), 3, 2,
            [f"The graph meets the \\(x\\)-axis at \\(x = {c}\\), splitting the region into two triangles.",
             f"Left triangle (\\(x = {a}\\) to \\({c}\\)): area \\(\\tfrac12\\times {c - a}\\times {c - a} = {L(below)}\\); right triangle: \\(\\tfrac12\\times {b - c}\\times {b - c} = {L(above)}\\).",
             (f"Both triangles are above the axis, so the integral is \\({L(below)} + {L(above)} = {L(val)}\\)." if absval else
              f"The left triangle is below the axis and counts negatively: \\({L(above)} - {L(below)} = {L(val)}\\).")],
            "A definite integral is a signed area: regions below the \\(x\\)-axis count as negative.",
            "Sketch the graph and label each region with its area and its sign before combining.",
            quicker="Each triangle has equal base and height (gradient 1), so its area is half the square of its base.",
            common_errors=[err(other, "conceptual", AREA, ("The absolute value makes the whole graph lie above the axis, so both areas count positively."
                                                           if absval else "Below the axis the integral is negative: subtract that triangle, don't add it."), step=3),
                           err(-val, "careless error", "sign error", "Check which region is above the axis.", step=3)],
            skill="Evaluate a definite integral as a signed area.",
            params={"form": "geom", "f": str(f), "lo": a, "hi": b},
        )
    rad = r.randint(2, 6)
    kv, m = r.randint(1, 5), nonzero(r, -4, 4)
    semi = sp.pi * rad**2 / 2
    f_b = sp.sqrt(rad**2 - x**2) + m * x + kv
    val_b = semi + 2 * rad * kv
    f_c = sp.sqrt(rad**2 - x**2) - kv
    val_c = sp.pi * rad**2 / 4 - rad * kv
    text = multipart(
        "In this question, evaluate each integral by interpreting it as an area — do not find primitives.",
        [("a", f"Evaluate \\({I(-rad, rad, sp.sqrt(rad**2 - x**2))}\\).", 2),
         ("b", f"Hence evaluate \\(\\displaystyle\\int_{{-{rad}}}^{{{rad}}} \\left(\\sqrt{{{rad**2} - x^2}} {'+' if m > 0 else '-'} {abs(m) if abs(m) != 1 else ''}x + {kv}\\right)dx\\).", 2),
         ("c", f"Evaluate \\(\\displaystyle\\int_{{0}}^{{{rad}}} \\left(\\sqrt{{{rad**2} - x^2}} - {kv}\\right)dx\\).", 1)])
    steps = [f"(a) \\(y = \\sqrt{{{rad**2} - x^2}}\\) is a semicircle of radius \\({rad}\\): the integral is \\(\\tfrac12\\pi\\times {rad}^2 = {L(semi)}\\).",
             f"(b) Split the integral into three. \\(y = {L(m * x)}\\) is odd, so its integral over \\([-{rad}, {rad}]\\) is \\(0\\) (equal areas above and below the axis).",
             f"The constant \\({kv}\\) gives a rectangle \\({2 * rad}\\times {kv} = {2 * rad * kv}\\). Total: semicircle \\(+\\) rectangle \\(= {L(semi)} + {2 * rad * kv} = {L(val_b)}\\).",
             f"(c) Quarter circle minus a rectangle: \\(\\tfrac14\\pi\\times {rad}^2 - {rad}\\times {kv} = {L(val_c)}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_num(semi)), P("b", 2, A_num(val_b)), P("c", 1, A_num(val_c))), 5, 3, steps,
        "Definite integrals add over sums of functions, odd functions integrate to zero over symmetric intervals, and positive functions give areas.",
        "Write each piece separately ('= semicircle + 0 + rectangle'); the marker can then award each piece.",
        quicker="An odd function such as \\(mx\\) contributes nothing on \\([-a, a]\\): cancel it before you start.",
        common_errors=[err(sp.pi * rad**2, "interpretation", LIM, "The square root gives only the upper half of the circle.", step=1, part="a"),
                       err(semi + 2 * rad * kv + 2 * m * rad**2, "conceptual", AREA, "The odd term's areas above and below the axis cancel.", step=2, part="b"),
                       err(semi + rad * kv, "careless error", LIM, f"The rectangle is \\({2 * rad}\\) wide, from \\(-{rad}\\) to \\({rad}\\).", step=3, part="b"),
                       err(sp.pi * rad**2 / 4 + rad * kv, "careless error", "sign error", "The constant is subtracted.", step=4, part="c")],
        skill="Use geometry, symmetry and linearity to evaluate definite integrals.",
        params={"form": "parts", "rad": rad, "k": kv, "m": m},
    )


# ----------------------------------------------------------------------- 3B ---
def t_3B(r: Rng, d: int) -> Generated:
    if d == 1:
        p, q, s = r.randint(1, 3) * 3, nonzero(r, -4, 4) * 2, r.randint(-5, 5)
        f = p * x**2 + q * x + s
        a = r.randint(-2, 1)
        b = a + r.randint(1, 3)
        F = sp.integrate(f, x)
        val = F.subs(x, b) - F.subs(x, a)
        return Generated(
            f"Evaluate \\({I(a, b, f)}\\).",
            A_num(val), 2, 1,
            [f"A primitive is \\(F(x) = {pl(F)}\\).",
             f"\\(F({b}) - F({a}) = {L(F.subs(x, b))} - ({L(F.subs(x, a))}) = {L(val)}\\)."],
            "The fundamental theorem: \\(\\int_a^b f(x)\\,dx = F(b) - F(a)\\) for any primitive \\(F\\) of \\(f\\).",
            "Write the square-bracket line \\(\\big[F(x)\\big]_a^b\\) and substitute both limits in brackets.",
            quicker="Integrate term by term and evaluate each term at both limits, keeping negatives in brackets.",
            common_errors=[err(-val, "careless error", "sign error", "That is \\(F(a) - F(b)\\): subtract the lower limit's value from the upper.", step=2),
                           err(F.subs(x, b), "incomplete reasoning", LIM, f"You used only the upper limit; subtract \\(F({a})\\).", step=2)
                           if F.subs(x, a) != 0 else err(f.subs(x, b) - f.subs(x, a), "conceptual", INTG, "Substitute into the primitive, not into the integrand.", step=1)],
            skill="Evaluate a definite integral with the fundamental theorem.",
            checkpoints=[cp(F, "the primitive", step=1)],
            params={"form": "def", "f": str(f), "lo": a, "hi": b},
        )
    if d == 2:
        if r.random() < 0.5:
            a, b = pick(r, [3, 6, 9]), nonzero(r, -4, 4)
            m = pick(r, [2, 3])
            f = a * sp.sqrt(x) + b / x**2
            F = sp.Rational(2 * a, 3) * x ** sp.Rational(3, 2) - b / x
            val = F.subs(x, m * m) - F.subs(x, 1)
            return Generated(
                f"Evaluate \\(\\displaystyle\\int_{{1}}^{{{m * m}}} \\left({L(f)}\\right)dx\\).",
                A_num(val), 3, 2,
                [f"Index form: \\({a}x^{{1/2}} {'+' if b > 0 else '-'} {co(abs(b), 'x')}^{{-2}}\\).",
                 f"A primitive is \\(F(x) = {L(F)}\\).",
                 f"\\(F({m * m}) - F(1) = {L(F.subs(x, m * m))} - ({L(F.subs(x, 1))}) = {L(val)}\\)."],
                "Write roots and reciprocals as powers, find a primitive, then apply \\(F(b) - F(a)\\).",
                "Evaluate \\(x^{3/2}\\) as \\((\\sqrt{x})^3\\): it keeps the arithmetic exact.",
                quicker=f"\\({m * m}^{{3/2}} = {m}^3 = {m**3}\\).",
                common_errors=[err(sp.Rational(2 * a, 3) * (m**3 - 1) + b * (sp.Rational(1, m * m) - 1), "careless error", "sign error",
                                   "The primitive of \\(x^{-2}\\) is \\(-x^{-1}\\).", step=2),
                               err(sp.Rational(3 * a, 2) * (m**3 - 1) - b * (sp.Rational(1, m * m) - 1), "arithmetic", INTG, "Divide by the new index \\(\\frac32\\).", step=2)],
                skill="Definite integrals of fractional and negative powers.",
                checkpoints=[cp(F, "the primitive", step=2)],
                params={"form": "def", "f": str(f), "lo": 1, "hi": m * m},
            )
        p, q = nonzero(r, -3, 4), nonzero(r, -3, 4)
        a = r.randint(-1, 1)
        b = a + r.randint(2, 3)
        f = (x - p) * (x + q)
        fe = sp.expand(f)
        F = sp.integrate(fe, x)
        val = F.subs(x, b) - F.subs(x, a)
        wrong = sp.integrate(x - p, (x, a, b)) * sp.integrate(x + q, (x, a, b))
        return Generated(
            f"Evaluate \\(\\displaystyle\\int_{{{a}}}^{{{b}}} {L(x - p)}\\,({L(x + q)})\\,dx\\).".replace("\\,(", "(").replace(f"{L(x - p)}(", f"({L(x - p)})("),
            A_num(val), 3, 2,
            [f"Expand first: \\(({L(x - p)})({L(x + q)}) = {pl(fe)}\\).",
             f"A primitive is \\(F(x) = {pl(F)}\\).",
             f"\\(F({b}) - F({a}) = {L(F.subs(x, b))} - ({L(F.subs(x, a))}) = {L(val)}\\)."],
            "There is no product rule for integration: expand the product into a sum of powers first.",
            "Show the expanded integrand; then the method is visible even if a fraction slips.",
            quicker="Check the sign of your answer against a sketch of the parabola between the limits.",
            common_errors=[err(wrong, "conceptual", INTG, "The integral of a product is not the product of the integrals: expand first.", step=1),
                           err(-val, "careless error", "sign error", "Subtract the lower limit's value from the upper limit's.", step=3)],
            skill="Expand, then evaluate a definite integral.",
            checkpoints=[cp(F, "the primitive", step=2)],
            params={"form": "def", "f": str(fe), "lo": a, "hi": b},
        )
    while True:
        a, bb = r.randint(0, 2), nonzero(r, -6, 6)
        k0 = a + r.randint(2, 5)
        other = -bb - k0
        if other < a and k0 != other:
            break
    f = 2 * x + bb
    Fk = sp.expand(kk**2 + bb * kk - (a * a + bb * a))
    V = Fk.subs(kk, k0)
    text = multipart(
        f"Let \\(k > {a}\\) be a constant.",
        [("a", f"Find \\({I(a, kk, f).replace('dx', 'dx')}\\) in terms of \\(k\\).", 2),
         ("b", f"Find the value of \\(k\\) for which \\({I(a, kk, f)} = {V}\\).", 2),
         ("c", f"Write down \\(\\dfrac{{d}}{{dk}}{I(a, kk, f)}\\).", 1)])
    steps = [f"(a) \\(\\big[x^2 {'+' if bb > 0 else '-'} {abs(bb) if abs(bb) != 1 else ''}x\\big]_{{{a}}}^{{k}} = (k^2 {'+' if bb > 0 else '-'} {abs(bb) if abs(bb) != 1 else ''}k) - ({a * a + bb * a}) = {pl(Fk, kk)}\\).",
             f"(b) \\({pl(Fk, kk)} = {V}\\), so \\({pl(Fk - V, kk)} = 0\\), i.e. \\((k - {k0})(k {'+' if -other > 0 else '-'} {abs(other)}) = 0\\).".replace("(k + 0)", "k").replace("(k - 0)", "k"),
             f"\\(k = {k0}\\) or \\(k = {other}\\); since \\(k > {a}\\), \\(k = {k0}\\).",
             f"(c) By the fundamental theorem, \\(\\dfrac{{d}}{{dk}}\\displaystyle\\int_{{{a}}}^{{k}} f(x)\\,dx = f(k) = {L(2 * kk + bb)}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_expr(Fk, ("k",))), P("b", 2, A_num(k0)), P("c", 1, A_expr(2 * kk + bb, ("k",)))), 5, 3, steps,
        "With a variable limit, \\(\\int_a^k f(x)\\,dx\\) is a function of \\(k\\) whose derivative is \\(f(k)\\) — the fundamental theorem of calculus.",
        "In (b) reject the root that breaks the stated condition and say why.",
        quicker="For (c) no integration is needed: replace \\(x\\) by \\(k\\) in the integrand.",
        common_errors=[err(other, "interpretation", "domain/range", f"That root does not satisfy \\(k > {a}\\).", step=3, part="b"),
                       err(kk**2 + bb * kk, "incomplete reasoning", LIM, f"Subtract the value of the primitive at the lower limit \\(x = {a}\\).", step=1, part="a")
                       if a * a + bb * a != 0 else err(2 * kk**2 + bb * kk, "arithmetic", INTG, "The primitive of \\(2x\\) is \\(x^2\\).", step=1, part="a"),
                       err(Fk, "conceptual", INTG, "Differentiating undoes the integral: the answer is the integrand evaluated at \\(k\\).", step=4, part="c")],
        skill="Use the fundamental theorem with a variable upper limit.",
        checkpoints=[cp(Fk, "the integral in terms of k", step=1, part="b", vars_=("k",))],
        params={"form": "parts", "a": a, "b": bb, "k": k0, "V": int(V)},
    )


# ----------------------------------------------------------------------- 3C ---
def t_3C(r: Rng, d: int) -> Generated:
    a = r.randint(-2, 2)
    b = a + r.randint(1, 4)
    c = b + r.randint(1, 4)
    Pv, Qv = nonzero(r, -9, 12), nonzero(r, -9, 12)
    if d == 1:
        form = pick(r, ["add", "rev", "lin"])
        given = f"Given that \\(\\displaystyle\\int_{{{a}}}^{{{b}}} f(x)\\,dx = {Pv}\\)"
        if form == "add":
            val = Pv + Qv
            return Generated(
                f"{given} and \\(\\displaystyle\\int_{{{b}}}^{{{c}}} f(x)\\,dx = {Qv}\\), find \\(\\displaystyle\\int_{{{a}}}^{{{c}}} f(x)\\,dx\\).",
                A_num(val), 1, 1,
                [f"Adjacent intervals add: \\(\\int_{{{a}}}^{{{c}}} = \\int_{{{a}}}^{{{b}}} + \\int_{{{b}}}^{{{c}}} = {Pv} {'+' if Qv > 0 else '-'} {abs(Qv)} = {val}\\)."],
                "Integrals over adjacent intervals add: \\(\\int_a^b f + \\int_b^c f = \\int_a^c f\\).",
                "Quote the property you are using in words.",
                quicker="Think of signed areas laid side by side.",
                common_errors=[err(Pv - Qv, "conceptual", LIM, "The intervals are adjacent, so the integrals add.", step=1)],
                skill="Use the additivity of definite integrals.",
                params={"form": "add", "P": Pv, "Q": Qv},
            )
        if form == "rev":
            return Generated(
                f"{given}, find \\(\\displaystyle\\int_{{{b}}}^{{{a}}} f(x)\\,dx\\).",
                A_num(-Pv), 1, 1,
                ["Reversing the limits changes the sign: \\(\\int_b^a f = -\\int_a^b f = " + str(-Pv) + "\\)."],
                "\\(\\int_b^a f(x)\\,dx = -\\int_a^b f(x)\\,dx\\), because \\(F(a) - F(b) = -(F(b) - F(a))\\).",
                "State the reversal property explicitly.",
                quicker="Swap the limits, swap the sign.",
                common_errors=[err(Pv, "conceptual", LIM, "Swapping the limits changes the sign of the integral.", step=1)],
                skill="Reverse the limits of a definite integral.",
                params={"form": "rev", "P": Pv},
            )
        m, kv = nonzero(r, -3, 4), nonzero(r, -5, 5)
        val = m * Pv + kv * (b - a)
        return Generated(
            f"{given}, find \\(\\displaystyle\\int_{{{a}}}^{{{b}}} \\left({L(m * sp.Symbol('f(x)'))} {'+' if kv > 0 else '-'} {abs(kv)}\\right)dx\\).",
            A_num(val), 2, 1,
            [f"Split the integral: \\({m}\\displaystyle\\int_{{{a}}}^{{{b}}} f(x)\\,dx {'+' if kv > 0 else '-'} \\int_{{{a}}}^{{{b}}} {abs(kv)}\\,dx\\).",
             f"\\(= {m}\\times({Pv}) {'+' if kv > 0 else '-'} {abs(kv)}\\times({b} - ({a})) = {val}\\)."],
            "Integrals are linear: constants factor out and integrals of sums are sums of integrals.",
            "Remember that the integral of a constant \\(c\\) over \\([a, b]\\) is \\(c(b - a)\\), not \\(c\\).",
            quicker=f"The constant contributes a rectangle of width \\({b - a}\\).",
            common_errors=[err(m * Pv + kv, "conceptual", INTG, f"The integral of the constant \\({kv}\\) over an interval of width \\({b - a}\\) is \\({kv * (b - a)}\\).", step=2),
                           err(Pv + kv * (b - a), "careless error", INTG, f"Multiply the integral of \\(f\\) by \\({m}\\).", step=2)],
            skill="Use linearity of definite integrals.",
            params={"form": "lin", "P": Pv, "m": m, "k": kv, "a": a, "b": b},
        )
    if d == 2:
        h = r.randint(1, 3)
        p, q, s = nonzero(r, -4, 4), nonzero(r, -6, 6), nonzero(r, -6, 6)
        if r.random() < 0.5:
            f = p * x**3 + q * x + s
            val = 2 * h * s
            note = f"\\({L(p * x**3 + q * x)}\\) is odd, so it contributes \\(0\\); the constant gives \\(2\\times {h}\\times {pn(s)} = {val}\\)."
            even_part = s
        else:
            f = p * x**5 + q * x**3 + 3 * s * x**2
            val = 2 * s * h**3
            note = f"\\({L(p * x**5 + q * x**3)}\\) is odd, so it contributes \\(0\\); \\(2\\displaystyle\\int_0^{{{h}}} {co(3 * s, 'x')}^2\\,dx = 2\\times {pn(s * h**3)} = {val}\\)."
            even_part = 3 * s * x**2
        return Generated(
            f"Use the properties of odd and even functions to evaluate \\({I(-h, h, f)}\\).",
            A_num(val), 2, 2,
            ["Split the integrand into its odd and even parts.", note],
            "Over a symmetric interval \\([-a, a]\\), an odd function integrates to \\(0\\) and an even function to \\(2\\int_0^a\\).",
            "Name each part as odd or even (\\(f(-x) = -f(x)\\) or \\(f(x)\\)) — that is the reasoning being assessed.",
            quicker="Odd powers vanish on \\([-a, a]\\); keep only the even powers and double from \\(0\\).",
            common_errors=[err(0, "conceptual", INTG, "Only the odd part integrates to zero; the even part does not.", step=2),
                           err(val // 2, "incomplete reasoning", INTG, "The even part gives twice its integral from \\(0\\).", step=2)],
            skill="Integrate odd and even functions over symmetric intervals.",
            params={"form": "sym", "f": str(f), "lo": -h, "hi": h, "even": str(even_part)},
        )
    m, h, s = nonzero(r, -6, 6), r.randint(1, 4), nonzero(r, -5, 5)
    text = multipart(
        f"The function \\(f\\) satisfies \\(\\displaystyle\\int_{{{a}}}^{{{c}}} f(x)\\,dx = {Pv}\\) and \\(\\displaystyle\\int_{{{b}}}^{{{c}}} f(x)\\,dx = {Qv}\\).",
        [("a", f"Find \\(\\displaystyle\\int_{{{a}}}^{{{b}}} f(x)\\,dx\\).", 1),
         ("b", f"Find \\(\\displaystyle\\int_{{{b}}}^{{{a}}} 2f(x)\\,dx\\).", 1),
         ("c", f"Find \\(\\displaystyle\\int_{{{a}}}^{{{c}}} \\left(f(x) {'+' if m > 0 else '-'} {abs(m)}\\right)dx\\).", 2),
         ("d", f"Evaluate \\(\\displaystyle\\int_{{-{h}}}^{{{h}}} \\left(x^3 {'+' if s > 0 else '-'} {abs(s)}\\right)dx\\).", 1)])
    ab = Pv - Qv
    steps = [f"(a) \\(\\int_{{{a}}}^{{{b}}} = \\int_{{{a}}}^{{{c}}} - \\int_{{{b}}}^{{{c}}} = {Pv} - ({Qv}) = {ab}\\).",
             f"(b) Reverse the limits and take out the factor 2: \\(-2\\times({ab}) = {-2 * ab}\\).",
             f"(c) \\(\\int_{{{a}}}^{{{c}}} f\\,dx + \\int_{{{a}}}^{{{c}}} {pn(m)}\\,dx = {Pv} {'+' if m > 0 else '-'} {abs(m)}\\times {c - a} = {Pv + m * (c - a)}\\).",
             f"(d) \\(x^3\\) is odd, so it integrates to \\(0\\) on \\([-{h}, {h}]\\); the constant gives \\({s}\\times {2 * h} = {2 * h * s}\\)."]
    return Generated(
        text,
        A_parts(P("a", 1, A_num(ab)), P("b", 1, A_num(-2 * ab)), P("c", 2, A_num(Pv + m * (c - a))), P("d", 1, A_num(2 * h * s))), 5, 3, steps,
        "Definite integrals are additive over intervals, change sign when the limits swap, are linear, and odd functions vanish over symmetric intervals.",
        "Quote the property used in each part; these questions are about reasoning, not calculation.",
        quicker="Draw a number line with \\(a\\), \\(b\\), \\(c\\) and the known integrals as arcs.",
        common_errors=[err(Pv + Qv, "conceptual", LIM, "\\(\\int_a^c = \\int_a^b + \\int_b^c\\), so subtract.", step=1, part="a"),
                       err(2 * ab, "careless error", "sign error", "Reversing the limits changes the sign.", step=2, part="b"),
                       err(Pv + m, "conceptual", INTG, f"The constant integrates to \\({m}\\times({c} - ({a}))\\).", step=3, part="c"),
                       err(0, "incomplete reasoning", INTG, "Only the odd part vanishes; the constant still contributes.", step=4, part="d")],
        skill="Combine the properties of definite integrals.",
        params={"form": "parts", "P": Pv, "Q": Qv, "a": a, "b": b, "c": c, "m": m, "h": h, "s": s},
    )


# ----------------------------------------------------------------------- 3E ---
def t_3E(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b = pick(r, [2, 3, 4, 5]), nonzero(r, -7, 7)
        u = a * x + b
        if r.random() < 0.6:
            nn = r.randint(3, 7)
            F = u ** (nn + 1) / (a * (nn + 1))
            integrand = u**nn
            steps = [f"\\(\\displaystyle\\int (ax + b)^n\\,dx = \\frac{{(ax + b)^{{n+1}}}}{{a(n+1)}} + C\\) with \\(a = {a}\\), \\(n = {nn}\\).",
                     f"\\(= \\dfrac{{({L(u)})^{{{nn + 1}}}}}{{{a * (nn + 1)}}} + C\\)."]
            ces = [err(u ** (nn + 1) / (nn + 1), "formula selection", "chain rule", f"Divide by \\(a = {a}\\) as well as by the new index.", step=1),
                   err(u ** (nn + 1) / (a * nn), "arithmetic", INTG, "Divide by the new index \\(n + 1\\).", step=1),
                   err(a * u ** (nn + 1) / (nn + 1), "conceptual", "chain rule", "You multiplied by \\(a\\) (as in differentiating); integrating divides by \\(a\\).", step=1)]
        else:
            nn = pick(r, [2, 3])
            F = u ** (1 - nn) / (a * (1 - nn))
            integrand = 1 / u**nn
            steps = [f"Write \\(\\dfrac{{1}}{{({L(u)})^{{{nn}}}}} = ({L(u)})^{{-{nn}}}\\).",
                     f"\\(\\displaystyle\\int ({L(u)})^{{-{nn}}}\\,dx = \\frac{{({L(u)})^{{{1 - nn}}}}}{{{a}\\times({1 - nn})}} + C = {L(F)} + C\\)."]
            ces = [err(u ** (1 - nn) / (1 - nn), "formula selection", "chain rule", f"Divide by \\(a = {a}\\) as well.", step=2),
                   err(-F, "careless error", "sign error", "The new index is negative, so the coefficient is negative.", step=2)]
        return Generated(
            f"Find \\({Iu(integrand)}\\).",
            A_prim(F), 2, 1, steps,
            "Reversing the chain rule: \\(\\int (ax + b)^n\\,dx = \\frac{(ax + b)^{n+1}}{a(n+1)} + C\\) for \\(n \\neq -1\\).",
            "Check by differentiating your answer: the chain rule should bring back the factor \\(a\\) you divided by.",
            quicker="Differentiate your answer mentally — it must return the integrand exactly.",
            common_errors=ces, skill="Integrate a power of a linear function.",
            params={"form": "prim", "f": str(integrand)},
        )
    if d == 2:
        if r.random() < 0.5:
            p, q, s = nonzero(r, -4, 4) * 2, nonzero(r, -5, 5), nonzero(r, -6, 6)
            num = p * x**3 + q * x**2 + s
            integrand = num / x**2
            F = sp.Rational(p, 2) * x**2 + q * x - s / x
            return Generated(
                f"Find \\(\\displaystyle\\int \\frac{{{pl(num)}}}{{x^2}}\\,dx\\).",
                A_prim(F), 2, 2,
                [f"Divide each term by \\(x^2\\): \\({L(p * x)} {'+' if q > 0 else '-'} {abs(q)} {'+' if s > 0 else '-'} {co(abs(s), 'x')}^{{-2}}\\).",
                 f"\\(\\displaystyle\\int = {L(F)} + C\\)."],
                "A quotient with a single-term denominator is split into separate powers before integrating.",
                "Write the divided-out line; integrating numerator and denominator separately is never valid.",
                quicker="Check: differentiate your answer and put it back over \\(x^2\\).",
                common_errors=[err(sp.Rational(p, 2) * x**2 + q * x + s / x, "careless error", "sign error", "The primitive of \\(x^{-2}\\) is \\(-x^{-1}\\).", step=2),
                               err(sp.integrate(num, x) / (x**3 / 3), "conceptual", INTG, "You cannot integrate the numerator and denominator separately.", step=1)],
                skill="Integrate a quotient by splitting it into powers.",
                params={"form": "prim", "f": str(integrand)},
            )
        a = pick(r, [2, 3, 4, 5])
        b = nonzero(r, -6, 6)
        u = a * x + b
        F = 2 * u ** sp.Rational(3, 2) / (3 * a)
        return Generated(
            f"Find \\(\\displaystyle\\int \\sqrt{{{L(u)}}}\\,dx\\).",
            A_prim(F), 2, 2,
            [f"Write \\(\\sqrt{{{L(u)}}} = ({L(u)})^{{1/2}}\\).",
             f"\\(\\displaystyle\\int ({L(u)})^{{1/2}}\\,dx = \\frac{{({L(u)})^{{3/2}}}}{{{a}\\times\\frac32}} + C = {L(sp.Rational(2, 3 * a))}({L(u)})^{{3/2}} + C\\)."],
            "A root of a linear function is a power: \\(\\int (ax + b)^n dx = \\frac{(ax + b)^{n+1}}{a(n+1)} + C\\) with \\(n = \\frac12\\).",
            "Keep the fraction \\(\\frac{1}{3/2} = \\frac23\\) visible.",
            quicker="Differentiate \\((ax + b)^{3/2}\\) and adjust the constant until it matches.",
            common_errors=[err(2 * u ** sp.Rational(3, 2) / 3, "formula selection", "chain rule", f"Divide by \\(a = {a}\\) too.", step=2),
                           err(3 * u ** sp.Rational(3, 2) / (2 * a), "arithmetic", INTG, "Dividing by \\(\\frac32\\) is multiplying by \\(\\frac23\\).", step=2)],
            skill="Integrate a root of a linear function.",
            params={"form": "prim", "f": str(sp.sqrt(u))},
        )
    while True:
        a = pick(r, [2, 4, 6])
        s0, s1 = pick(r, [1, 2]), pick(r, [3, 4])
        b = r.randint(-5, 5)
        if not (s0 * s0 - b) % a and not (s1 * s1 - b) % a:
            break
    x0, x1 = sp.Rational(s0 * s0 - b, a), sp.Rational(s1 * s1 - b, a)
    y0 = r.randint(-4, 6)
    u = a * x + b
    Fp = 2 * u ** sp.Rational(3, 2) / (3 * a)
    C = y0 - sp.Rational(2 * s0**3, 3 * a)
    y1 = sp.Rational(2 * s1**3, 3 * a) + C
    text = multipart(
        f"The gradient of a curve is given by \\(\\dfrac{{dy}}{{dx}} = \\sqrt{{{L(u)}}}\\), and the curve passes through the point \\(({L(x0)}, {y0})\\).",
        [("a", f"Find \\(\\displaystyle\\int \\sqrt{{{L(u)}}}\\,dx\\).", 2), ("b", "Find the equation of the curve (enter the expression for \\(y\\)).", 2),
         ("c", f"Find the value of \\(y\\) when \\(x = {L(x1)}\\).", 1)])
    steps = [f"(a) \\(\\displaystyle\\int ({L(u)})^{{1/2}}\\,dx = \\frac{{({L(u)})^{{3/2}}}}{{{a}\\times\\frac32}} + C = {L(sp.Rational(2, 3 * a))}({L(u)})^{{3/2}} + C\\).",
             f"(b) At \\(x = {L(x0)}\\), \\({L(u)} = {s0 * s0}\\) and \\(({s0 * s0})^{{3/2}} = {s0**3}\\): \\({y0} = {L(sp.Rational(2 * s0**3, 3 * a))} + C\\), so \\(C = {L(C)}\\).",
             f"So \\(y = {L(sp.Rational(2, 3 * a))}({L(u)})^{{3/2}} {'+' if C >= 0 else '-'} {L(abs(C))}\\).",
             f"(c) At \\(x = {L(x1)}\\), \\({L(u)} = {s1 * s1}\\): \\(y = {L(sp.Rational(2, 3 * a))}\\times {s1**3} {'+' if C >= 0 else '-'} {L(abs(C))} = {L(y1)}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_prim(Fp)), P("b", 2, A_expr(Fp + C)), P("c", 1, A_num(y1))), 5, 3, steps,
        "Integrating the gradient function gives the curve up to a constant, which a known point then fixes.",
        "Keep the constant as \\(C\\) until you substitute the point; write the final equation in full.",
        quicker="The points were chosen so that \\(ax + b\\) is a perfect square: evaluate the root first.",
        common_errors=[err(2 * u ** sp.Rational(3, 2) / 3, "formula selection", "chain rule", f"Divide by \\(a = {a}\\) as well.", step=1, part="a"),
                       err(Fp, "incomplete reasoning", "constant of integration", "Use the given point to find the constant.", step=2, part="b")
                       if C != 0 else err(Fp + 1, "careless error", "constant of integration", "Recheck the constant.", step=2, part="b"),
                       err(sp.Rational(2 * s1**3, 3 * a), "incomplete reasoning", "constant of integration", "Include the constant found in (b).", step=4, part="c")],
        skill="Find a curve from a gradient involving a root of a linear function.",
        checkpoints=[cp(Fp, "the primitive", step=1, part="b")],
        params={"form": "parts", "a": a, "b": b, "x0": x0, "y0": y0, "x1": x1},
    )


# ----------------------------------------------------------------------- 3F ---
def t_3F(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            p, q = r.randint(1, 3), r.randint(1, 6)
            a = r.randint(0, 2)
            b = a + r.randint(1, 3)
            f = p * x**2 + q
        else:
            m = pick(r, [2, 3])
            a, b = 0, m * m
            f = sp.sqrt(x) * pick(r, [1, 3, 6])
        F = sp.integrate(f, x)
        area = F.subs(x, b) - F.subs(x, a)
        return Generated(
            f"Find the area of the region bounded by the curve \\(y = {L(f)}\\), the \\(x\\)-axis and the lines \\(x = {a}\\) and \\(x = {b}\\).",
            A_units(area, "units^2"), 2, 1,
            [f"The curve is above the \\(x\\)-axis on \\([{a}, {b}]\\), so \\(A = {I(a, b, f)}\\).",
             f"\\(= \\big[{L(F)}\\big]_{{{a}}}^{{{b}}} = {L(area)}\\) square units."],
            "When a curve is above the \\(x\\)-axis, the area under it is its definite integral.",
            "Write the integral with its limits before evaluating, and give units of area.",
            quicker="Sanity check: the area lies between (width × smallest height) and (width × largest height).",
            common_errors=[err(-area, "careless error", "sign error", "Subtract the lower limit's value from the upper.", step=2),
                           err(F.subs(x, b), "incomplete reasoning", LIM, "Subtract the primitive's value at the lower limit.", step=2)
                           if F.subs(x, a) != 0 else err(f.subs(x, b) * (b - a), "conceptual", INTG, "That is a rectangle; integrate the curve.", step=1)],
            skill="Find the area under a curve.",
            checkpoints=[cp(F, "the primitive", step=2)],
            params={"form": "area", "f": str(f), "lo": a, "hi": b},
        )
    if d == 2:
        a = r.randint(1, 4)
        b = a + r.randint(1, 3)
        f = x * (x - a)
        below = sp.Rational(a**3, 6)
        Fe = x**3 / 3 - a * x**2 / 2
        above = Fe.subs(x, b) - Fe.subs(x, a)
        area = below + above
        signed = above - below
        return Generated(
            f"Find the total area enclosed between the curve \\(y = {L(sp.expand(f))}\\), the \\(x\\)-axis and the line \\(x = {b}\\), for \\(0 \\le x \\le {b}\\).",
            A_units(area, "units^2"), 3, 2,
            [f"\\(y = x(x - {a})\\) is below the axis for \\(0 < x < {a}\\) and above it for \\(x > {a}\\), so split at \\(x = {a}\\).",
             f"\\(\\displaystyle\\int_0^{{{a}}} = \\big[{L(Fe)}\\big]_0^{{{a}}} = {L(-below)}\\), an area of \\({L(below)}\\).",
             f"\\(\\displaystyle\\int_{{{a}}}^{{{b}}} = {L(above)}\\).",
             f"Total area \\(= {L(below)} + {L(above)} = {L(area)}\\) square units."],
            "Area is always positive: integrate separately on each side of an \\(x\\)-intercept and add the absolute values.",
            "Sketch first and mark the \\(x\\)-intercepts — they are the places to split the integral.",
            quicker="For a parabola, the area between it and the axis between its roots is \\(\\frac{|a|(q - p)^3}{6}\\).",
            common_errors=[err(signed, "conceptual", AREA, "The part below the axis has a negative integral: split at the intercept and add areas.", step=1),
                           err(above, "incomplete reasoning", AREA, f"You left out the region between \\(0\\) and \\({a}\\).", step=4)],
            skill="Find an area when the curve crosses the axis.",
            checkpoints=[cp(Fe, "the primitive", step=2)],
            params={"form": "split", "a": a, "b": b},
        )
    while True:
        p, q = sorted(r.sample(range(-3, 5), 2))
        if q - p >= 2:
            break
    c = r.randint(-4, 4)
    up = r.random() < 0.5
    if up:
        curve = x**2 + c
        line = (p + q) * x - p * q + c
        top, bot = line, curve
    else:
        curve = c - x**2
        line = c - (p + q) * x + p * q
        top, bot = curve, line
    area = sp.Rational((q - p) ** 3, 6)
    diff = sp.expand(top - bot)
    text = multipart(
        f"The curve \\(y = {L(curve)}\\) and the line \\(y = {L(line)}\\) intersect at two points.",
        [("a", "Find the \\(x\\)-coordinates of the points of intersection.", 2),
         ("b", "Find the area of the region enclosed between the curve and the line.", 3)])
    D = sp.integrate(diff, x)
    steps = [f"(a) \\({L(curve)} = {L(line)}\\) gives \\({L(sp.expand(curve - line))} = 0\\), i.e. "
             f"\\({'' if up else '-'}(x {'-' if p > 0 else '+'} {abs(p)})(x {'-' if q > 0 else '+'} {abs(q)}) = 0\\)".replace("(x + 0)", "x").replace("(x - 0)", "x") + f", so \\(x = {p}\\) or \\(x = {q}\\).",
             f"(b) Between the intersections the {'line' if up else 'curve'} is above the {'curve' if up else 'line'}: \\(A = \\displaystyle\\int_{{{p}}}^{{{q}}} \\big(({L(top)}) - ({L(bot)})\\big)\\,dx = \\int_{{{p}}}^{{{q}}} \\left({L(diff)}\\right)dx\\).",
             f"\\(= \\big[{L(D)}\\big]_{{{p}}}^{{{q}}} = {L(D.subs(x, q))} - ({L(D.subs(x, p))}) = {L(area)}\\) square units."]
    return Generated(
        text, A_parts(P("a", 2, A_set([p, q])), P("b", 3, A_units(area, "units^2"))), 5, 3, steps,
        "The area between two curves is \\(\\int_a^b (\\text{upper} - \\text{lower})\\,dx\\) between their intersections.",
        "Say which graph is on top (test a point between the intersections) before you integrate.",
        quicker="For a parabola \\(y = \\pm x^2 + \\ldots\\) and a line, the enclosed area is \\(\\frac{(q - p)^3}{6}\\).",
        common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error solving the quadratic.", step=1, part="a"),
                       err(-area, "careless error", "sign error", "Subtract the lower graph from the upper one.", step=2, part="b"),
                       err(abs(sp.integrate(curve, (x, p, q))), "conceptual", AREA, "Integrate the difference of the two graphs, not the curve alone.", step=2, part="b")],
        skill="Find the area enclosed between a parabola and a line.",
        checkpoints=[cp(diff, "the difference upper − lower", step=2, part="b")],
        params={"form": "parts", "curve": str(curve), "line": str(line), "p": p, "q": q},
    )


# ----------------------------------------------------------------------- 3G ---
def _trap(vals, h):
    return h / 2 * (vals[0] + 2 * sum(vals[1:-1]) + vals[-1])


def t_3G(r: Rng, d: int) -> Generated:
    if d == 1:
        h = pick(r, [sp.Integer(1), sp.Integer(2), sp.Rational(1, 2)])
        a = r.randint(0, 3)
        xs = [a + i * h for i in range(3)]
        ys = [r.randint(1, 15) for _ in range(3)]
        val = _trap(ys, h)
        rows = " & ".join(L(v) for v in xs)
        vals = " & ".join(str(v) for v in ys)
        return Generated(
            f"A function takes the values in the table below. Use the trapezoidal rule with these three function values to estimate "
            f"\\(\\displaystyle\\int_{{{L(xs[0])}}}^{{{L(xs[-1])}}} f(x)\\,dx\\).\n\n"
            f"\\[\\begin{{array}}{{c|ccc}} x & {rows} \\\\ \\hline f(x) & {vals} \\end{{array}}\\]",
            A_num(val), 2, 1,
            [f"Two subintervals of width \\(h = {L(h)}\\).",
             f"\\(\\displaystyle\\int \\approx \\frac{{h}}{{2}}\\big(f_0 + 2f_1 + f_2\\big) = \\frac{{{L(h)}}}{{2}}\\big({ys[0]} + 2\\times {ys[1]} + {ys[2]}\\big) = {L(val)}\\)."],
            "The trapezoidal rule replaces the curve by straight segments: \\(\\int_a^b f \\approx \\frac{h}{2}\\big(f_0 + 2(f_1 + \\cdots + f_{n-1}) + f_n\\big)\\).",
            "Write the formula with \\(h\\) and the function values substituted before calculating.",
            quicker="Ends once, middles twice, times half the strip width.",
            common_errors=[err(h / 2 * sum(ys), "formula selection", "series formula", "The interior value is counted twice.", step=2),
                           err(h * (ys[0] + 2 * ys[1] + ys[2]), "formula selection", "series formula", "Multiply by \\(\\frac{h}{2}\\), not \\(h\\).", step=2)],
            skill="Apply the trapezoidal rule to a table of values.",
            params={"form": "table", "ys": ys, "h": str(h)},
        )
    if d == 2:
        kind = pick(r, ["sqrt", "recip", "root1"])
        a = r.randint(1, 3)
        h = pick(r, [sp.Rational(1, 2), sp.Integer(1)])
        b = a + 4 * h
        f = {"sqrt": sp.sqrt(x), "recip": 1 / x, "root1": sp.sqrt(1 + x**2)}[kind]
        xs = [a + i * h for i in range(5)]
        ys = [f.subs(x, v) for v in xs]
        val = _trap(ys, h)
        val3 = _trap([f.subs(x, a + i * sp.Rational(4, 3) * h) for i in range(4)], sp.Rational(4, 3) * h)
        return Generated(
            f"Use the trapezoidal rule with five function values (four subintervals) to estimate \\(\\displaystyle\\int_{{{a}}}^{{{L(b)}}} {L(f)}\\,dx\\). "
            "Give your answer correct to 2 decimal places.",
            A_round(val, 2), 3, 2,
            [f"\\(h = \\dfrac{{{L(b)} - {a}}}{{4}} = {L(h)}\\); the \\(x\\)-values are \\({', '.join(L(v) for v in xs)}\\).",
             "Function values: " + ", ".join(f"\\(f({L(v)}) \\approx {sp.N(y, 5)}\\)" for v, y in zip(xs, ys)) + ".",
             f"\\(\\displaystyle\\int \\approx \\frac{{{L(h)}}}{{2}}\\big(f_0 + 2(f_1 + f_2 + f_3) + f_4\\big) \\approx {sp.N(val, 6)}\\), so about \\({sp.N(val, 30):.2f}\\)."],
            "Five function values give four strips; the trapezoidal rule adds their areas.",
            "Tabulate the \\(x\\)-values and function values first, keeping 4 or more decimal places until the end.",
            quicker="Store each function value in the calculator memory rather than retyping rounded values.",
            common_errors=[err(rnd(val3, 2), "interpretation", "series formula", "Five function values make four subintervals, not three.", step=1),
                           err(rnd(h / 2 * sum(ys), 2), "formula selection", "series formula", "Interior values are counted twice.", step=3),
                           err(rnd(2 * val, 2), "formula selection", "series formula", "Multiply by \\(\\frac{h}{2}\\), not \\(h\\).", step=3)],
            skill="Apply the trapezoidal rule with four subintervals.",
            params={"form": "fn", "f": str(f), "lo": a, "h": str(h), "n": 4},
        )
    s = pick(r, [1, -1])
    bw = pick(r, [2, 4, 6])
    c = r.randint(1, 4) + (bw * bw if s < 0 else 0)
    f = c + s * x**2
    h = sp.Rational(bw, 4)
    xs = [i * h for i in range(5)]
    ys = [f.subs(x, v) for v in xs]
    T = _trap(ys, h)
    exact = sp.integrate(f, (x, 0, bw))
    opts = mcq_options("an overestimate", "an underestimate", "exactly equal to the integral")
    ans = "A" if s > 0 else "B"
    text = multipart(
        f"Let \\(f(x) = {L(f)}\\).",
        [("a", f"Use the trapezoidal rule with four subintervals to find an approximation to \\(\\displaystyle\\int_0^{{{bw}}} f(x)\\,dx\\). Give the exact value of the approximation.", 2),
         ("b", f"Find the exact value of \\(\\displaystyle\\int_0^{{{bw}}} f(x)\\,dx\\).", 2),
         ("c", "Is the trapezoidal approximation an overestimate or an underestimate? Give a reason.", 1)])
    steps = [f"(a) \\(h = {L(h)}\\); the values are " + ", ".join(f"\\(f({L(v)}) = {L(y)}\\)" for v, y in zip(xs, ys)) + ".",
             f"\\(T = {L(h / 2)}\\big({L(ys[0])} + 2({L(ys[1])} + {L(ys[2])} + {L(ys[3])}) + {L(ys[4])}\\big) = {L(T)}\\).",
             f"(b) \\(\\big[{L(sp.integrate(f, x))}\\big]_0^{{{bw}}} = {L(exact)}\\).",
             f"(c) \\(f''(x) = {2 * s}\\) {'> 0' if s > 0 else '< 0'}, so the curve is concave {'up' if s > 0 else 'down'}: each chord lies {'above' if s > 0 else 'below'} the curve, "
             f"so the rule gives an {'over' if s > 0 else 'under'}estimate (indeed \\({L(T)} {'>' if s > 0 else '<'} {L(exact)}\\))."]
    return Generated(
        text, A_parts(P("a", 2, A_num(T)), P("b", 2, A_num(exact)), P("c", 1, A_mcq(ans, opts))), 5, 3, steps,
        "The trapezoidal rule overestimates where a curve is concave up (chords above the curve) and underestimates where it is concave down.",
        "For (c), the reason must mention concavity or chords — comparing two numbers alone is not a reason.",
        quicker="Compare with (b): the sign of \\(T - \\int f\\) confirms your concavity argument.",
        common_errors=[err(h / 2 * sum(ys), "formula selection", "series formula", "Interior values are counted twice.", step=2, part="a"),
                       err("B" if ans == "A" else "A", "conceptual", "concavity", f"The curve is concave {'up' if s > 0 else 'down'}, so the chords lie {'above' if s > 0 else 'below'} it.", step=4, part="c"),
                       err(-exact, "careless error", "sign error", "Subtract the lower limit's value from the upper.", step=3, part="b")],
        skill="Apply the trapezoidal rule and judge its accuracy from concavity.",
        params={"form": "parts", "c": c, "s": s, "b": bw},
    )


# ----------------------------------------------------------------------- 3H ---
def t_3H(r: Rng, d: int) -> Generated:
    if d == 1:
        b = nonzero(r, -6, 6)
        nn = r.randint(2, 6)
        if r.random() < 0.5:
            u, du = x**2 + b, 2 * x
        else:
            u, du = x**3 + b, 3 * x**2
        F = u ** (nn + 1) / (nn + 1)
        return Generated(
            f"Find \\(\\displaystyle\\int {L(du)}\\left({L(u)}\\right)^{{{nn}}}\\,dx\\).",
            A_prim(F), 2, 1,
            [f"The factor \\({L(du)}\\) is the derivative of \\({L(u)}\\), so this is \\(\\int f'(x)[f(x)]^n\\,dx\\) with \\(f(x) = {L(u)}\\).",
             f"\\(= \\dfrac{{({L(u)})^{{{nn + 1}}}}}{{{nn + 1}}} + C\\)."],
            "Reverse chain rule: \\(\\int f'(x)[f(x)]^n\\,dx = \\frac{[f(x)]^{n+1}}{n+1} + C\\).",
            "Point out that the outside factor is the derivative of the inside — that is the step being marked.",
            quicker="Differentiate your answer: the chain rule must produce exactly the integrand.",
            common_errors=[err(u ** (nn + 1) / (nn + 1) * du, "conceptual", "chain rule", "The factor \\(f'(x)\\) is used up by the reverse chain rule; it does not stay in the answer.", step=2),
                           err(u ** (nn + 1) / nn, "arithmetic", INTG, "Divide by the new index \\(n + 1\\).", step=2)],
            skill="Recognise and integrate f'(x)[f(x)]^n.",
            params={"form": "prim", "f": str(du * u**nn)},
        )
    if d == 2:
        b = r.randint(1, 9)
        kind = pick(r, ["half", "root", "cube"])
        if kind == "half":
            nn = r.randint(2, 5)
            integrand = x * (x**2 + b) ** nn
            F = (x**2 + b) ** (nn + 1) / (2 * (nn + 1))
            tl = f"x\\left(x^2 + {b}\\right)^{{{nn}}}"
            st = [f"\\(\\dfrac{{d}}{{dx}}(x^2 + {b})^{{{nn + 1}}} = {2 * (nn + 1)}x(x^2 + {b})^{{{nn}}}\\).",
                  f"So \\(\\displaystyle\\int {tl}\\,dx = \\frac{{(x^2 + {b})^{{{nn + 1}}}}}{{{2 * (nn + 1)}}} + C\\)."]
            wrong = (x**2 + b) ** (nn + 1) / (nn + 1)
        elif kind == "root":
            integrand = x / sp.sqrt(x**2 + b)
            F = sp.sqrt(x**2 + b)
            tl = f"\\frac{{x}}{{\\sqrt{{x^2 + {b}}}}}"
            st = [f"\\(\\dfrac{{d}}{{dx}}\\sqrt{{x^2 + {b}}} = \\dfrac{{x}}{{\\sqrt{{x^2 + {b}}}}}\\).",
                  f"So \\(\\displaystyle\\int {tl}\\,dx = \\sqrt{{x^2 + {b}}} + C\\)."]
            wrong = 2 * sp.sqrt(x**2 + b)
        else:
            nn = r.randint(2, 4)
            integrand = x**2 * (x**3 + b) ** nn
            F = (x**3 + b) ** (nn + 1) / (3 * (nn + 1))
            tl = f"x^2\\left(x^3 + {b}\\right)^{{{nn}}}"
            st = [f"\\(\\dfrac{{d}}{{dx}}(x^3 + {b})^{{{nn + 1}}} = {3 * (nn + 1)}x^2(x^3 + {b})^{{{nn}}}\\).",
                  f"So \\(\\displaystyle\\int {tl}\\,dx = \\frac{{(x^3 + {b})^{{{nn + 1}}}}}{{{3 * (nn + 1)}}} + C\\)."]
            wrong = (x**3 + b) ** (nn + 1) / (nn + 1)
        return Generated(
            f"Find \\(\\displaystyle\\int {tl}\\,dx\\).",
            A_prim(F), 3, 2, st,
            "When the outside factor is a constant multiple of the inside's derivative, adjust the constant and reverse the chain rule.",
            "Show the derivative you are reversing; it justifies the constant you divide by.",
            quicker="Guess the form, differentiate it, then fix the constant factor.",
            common_errors=[err(wrong, "formula selection", "chain rule", "The derivative of the inside brings in a constant factor: divide by it.", step=2),
                           err(-F, "careless error", "sign error", "Check the sign by differentiating.", step=2)],
            skill="Reverse the chain rule with a constant adjustment.",
            params={"form": "prim", "f": str(integrand)},
        )
    b = r.randint(1, 5)
    m = r.randint(3, 5)
    c = pick(r, [1, 2])
    u = x**2 + b
    D = sp.expand(sp.diff(u**m, x))
    F = u**m / (2 * m)
    val = sp.Rational((c * c + b) ** m - b**m, 2 * m)
    text = multipart(
        "",
        [("a", f"Differentiate \\(\\left(x^2 + {b}\\right)^{{{m}}}\\).", 1),
         ("b", f"Hence find \\(\\displaystyle\\int x\\left(x^2 + {b}\\right)^{{{m - 1}}}\\,dx\\).", 2),
         ("c", f"Hence evaluate \\(\\displaystyle\\int_0^{{{c}}} x\\left(x^2 + {b}\\right)^{{{m - 1}}}\\,dx\\).", 2)])
    steps = [f"(a) Chain rule: \\(\\dfrac{{d}}{{dx}}(x^2 + {b})^{{{m}}} = {m}(x^2 + {b})^{{{m - 1}}}\\times 2x = {2 * m}x(x^2 + {b})^{{{m - 1}}}\\).",
             f"(b) So \\(\\displaystyle\\int {2 * m}x(x^2 + {b})^{{{m - 1}}}\\,dx = (x^2 + {b})^{{{m}}} + C\\).",
             f"Divide by \\({2 * m}\\): \\(\\displaystyle\\int x(x^2 + {b})^{{{m - 1}}}\\,dx = \\frac{{(x^2 + {b})^{{{m}}}}}{{{2 * m}}} + C\\).",
             f"(c) \\(\\left[\\dfrac{{(x^2 + {b})^{{{m}}}}}{{{2 * m}}}\\right]_0^{{{c}}} = \\dfrac{{{c * c + b}^{{{m}}} - {b}^{{{m}}}}}{{{2 * m}}} = {L(val)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(sp.factor(D))), P("b", 2, A_prim(F)), P("c", 2, A_num(val))), 5, 3, steps,
        "'Hence' questions: a derivative found in one part is read backwards as an integral in the next.",
        "In (b) write the line 'so \\(\\int 2mx(\\ldots)\\,dx = (\\ldots)^m + C\\)' before dividing by the constant.",
        quicker="In (c) evaluate the bracket \\(x^2 + b\\) at each limit before raising to the power.",
        common_errors=[err(m * u ** (m - 1), "careless error", "chain rule", "Multiply by the derivative of the inside, \\(2x\\).", step=1, part="a"),
                       err(u**m / m, "formula selection", "chain rule", f"Divide by \\({2 * m}\\), the full constant from (a).", step=3, part="b"),
                       err(sp.Rational((c * c + b) ** m, 2 * m), "incomplete reasoning", LIM, "Subtract the value at the lower limit \\(x = 0\\), which is not zero.", step=4, part="c")],
        skill="Use a derivative to find a related integral (reverse chain rule).",
        checkpoints=[cp(D, "the derivative from (a)", step=1, part="b")],
        params={"form": "parts", "b": b, "m": m, "c": c},
    )
