"""Year 11 assumed-knowledge review templates (owner: maths): functions, graph transformations,
trigonometry, introductory calculus, exponentials and logarithms, probability.

Same contract as the chapter modules: difficulty 1 is a one-skill foundation item, 2 is HSC-standard,
3 is an HSC-style multi-part question of 4–6 marks, so Year 11 revision is never stuck at foundation
level (audit selection-08, maths-10)."""
from __future__ import annotations

import math

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_iv, A_num, A_parts, A_round, A_set, A_units, Generated, L, P, Rng, S, co, cp, err, multipart, nonzero, pick, pl,
    pn, region, rnd, sgn, x,
)

pi = sp.pi
ALG, DR, SIGN = "algebra", "domain/range", "sign error"
TR, TEV, RAD = "transformations", "trig exact values", "radians"
DIFF, CHAIN, IDX, LOGS = "differentiation rules", "chain rule", "index laws", "log laws"
PROB, CALC = "probability interpretation", "calculator error"
GE, LE = "\\ge", "\\le"


def _two_roots(r: Rng) -> tuple[int, int]:
    p, q = sorted(r.sample([v for v in range(-6, 7) if v], 2))
    return p, q


# ================================================================== Y11-FUNC ===
def t_Y11_FUNC(r: Rng, d: int) -> Generated:
    if d == 1:
        form = pick(r, ["eval", "solve", "domain"])
        if form == "eval":
            a, b, c = nonzero(r, -3, 4), nonzero(r, -7, 7), r.randint(-9, 9)
            m = r.randint(-4, -1)
            f = a * x**2 + b * x + c
            val = f.subs(x, m)
            return Generated(
                f"Given \\(f(x) = {pl(f)}\\), find \\(f({m})\\).",
                A_num(val), 1, 1,
                [f"\\(f({m}) = {co(a)}{pn(m)}^2 {sgn(b)}\\times{pn(m)} {sgn(c)} = {val}\\)." if c else
                 f"\\(f({m}) = {co(a)}{pn(m)}^2 {sgn(b)}\\times{pn(m)} = {val}\\)."],
                "Function notation: \\(f(m)\\) is the output when \\(x = m\\) is substituted everywhere \\(x\\) appears.",
                "Bracket negative numbers when you substitute them.",
                quicker="\\((-a)^2 = a^2\\): squaring a negative number gives a positive result.",
                common_errors=[err(-a * m**2 + b * m + c, "careless error", SIGN, f"\\(({m})^2 = {m * m}\\), not \\(-{m * m}\\): bracket the negative number before squaring.", step=1)],
                skill="Evaluate a function at a negative input.",
                params={"form": "eval", "f": str(f), "m": m},
            )
        if form == "solve":
            p, q = _two_roots(r)
            while p == -q:  # keep the sign-slip diagnosis distinct from the answer
                p, q = _two_roots(r)
            a = pick(r, [1, 1, 2, 3, -1])
            f = sp.expand(a * (x - p) * (x - q))
            return Generated(
                f"Solve \\({pl(f)} = 0\\).",
                A_set([p, q]), 2, 1,
                [f"\\({pl(f)} = {L(sp.factor(f))} = 0\\).", f"So \\(x = {p}\\) or \\(x = {q}\\)."],
                "A product is zero exactly when one of its factors is zero.",
                "Take out any common factor, then factorise the monic quadratic.",
                quicker="Check: the two solutions add to \\(-\\frac{b}{a}\\) and multiply to \\(\\frac{c}{a}\\).",
                common_errors=[err(S(-p, -q), "careless error", SIGN, "Sign error: \\(x - p = 0\\) gives \\(x = p\\), not \\(-p\\).", step=2)],
                skill="Solve a quadratic equation by factorising.",
                params={"form": "solve", "f": str(f)},
            )
        a, b = pick(r, [1, 2, 3, -1, -2, -3]), nonzero(r, -8, 8)
        lim = sp.Rational(-b, a)
        rows = [(lim, None, True, False)] if a > 0 else [(None, lim, False, True)]
        inner = a * x + b
        return Generated(
            f"Find the natural domain of \\(f(x) = \\sqrt{{{pl(inner)}}}\\).",
            A_iv(rows), 1, 1,
            [f"The square root needs \\({pl(inner)} \\ge 0\\), so \\(x {GE if a > 0 else LE} {L(lim)}\\)."],
            "The natural domain is every \\(x\\) for which the formula is defined: \\(\\sqrt{u}\\) needs \\(u \\ge 0\\).",
            "Write the condition as an inequality and solve it; dividing by a negative reverses the sign.",
            quicker="Test a value: substitute a number from your answer and check the square root exists.",
            common_errors=[err(region([(lim, None, False, False)] if a > 0 else [(None, lim, False, False)]), "notation", DR,
                               "\\(\\sqrt{0} = 0\\) is defined, so the endpoint is included (use \\(\\ge\\) or \\(\\le\\)).", step=1)]
            + ([err(region([(lim, None, True, False)]), "careless error", "inequality direction",
                    "Dividing by a negative number reverses the inequality.", step=1)] if a < 0 else []),
            skill="Find the natural domain of a square-root function.",
            params={"form": "domain", "inner": str(inner)},
        )
    if d == 2:
        form = pick(r, ["comp", "ineq", "dom2"])
        if form == "comp":
            a, b = pick(r, [2, 3, -2, 4]), nonzero(r, -6, 6)
            c = nonzero(r, -5, 5)
            m = nonzero(r, -3, 3)
            f, g = a * x + b, x**2 + c
            fg = f.subs(x, g.subs(x, m))
            gf = g.subs(x, f.subs(x, m))
            return Generated(
                f"Let \\(f(x) = {pl(f)}\\) and \\(g(x) = {pl(g)}\\). Find \\(f(g({m}))\\).",
                A_num(fg), 2, 2,
                [f"Inside first: \\(g({m}) = {pn(m)}^2 {sgn(c)} = {g.subs(x, m)}\\).", f"Then \\(f({g.subs(x, m)}) = {co(a)}{pn(g.subs(x, m))} {sgn(b)} = {fg}\\)."],
                "A composite \\(f(g(x))\\) applies \\(g\\) first, then \\(f\\) to the result.",
                "Work from the inside out and write the intermediate value.",
                quicker="Name the intermediate value (\\(u = g(m)\\)) so the order cannot get mixed up.",
                common_errors=[err(gf, "conceptual", ALG, "That is \\(g(f(m))\\): apply \\(g\\) first, then \\(f\\).", step=1),
                               err(f.subs(x, m) * g.subs(x, m), "conceptual", ALG, "Composition is not multiplication: substitute \\(g(m)\\) into \\(f\\).", step=2)],
                skill="Evaluate a composite function.",
                checkpoints=[cp(g.subs(x, m), "the inner value g(m)", step=1)],
                params={"form": "comp", "f": str(f), "g": str(g), "m": m},
            )
        if form == "ineq":
            p, q = _two_roots(r)
            a = pick(r, [1, 1, 2, -1])
            f = sp.expand(a * (x - p) * (x - q))
            rel = pick(r, ["<", ">", "\\le", "\\ge"])
            pos = rel in (">", "\\ge")
            strict = rel in ("<", ">")
            inside = pos != (a > 0)  # the solution is between the roots
            rows = [(p, q, not strict, not strict)] if inside else [(None, p, False, not strict), (q, None, not strict, False)]
            wrong = [(None, p, False, not strict), (q, None, not strict, False)] if inside else [(p, q, not strict, not strict)]
            return Generated(
                f"Solve \\({pl(f)} {rel} 0\\).",
                A_iv(rows), 3, 2,
                [f"Factorise: \\({L(sp.factor(f))} {rel} 0\\); the zeros are \\(x = {p}\\) and \\(x = {q}\\).",
                 f"The parabola is {'concave up' if a > 0 else 'concave down'}, so it is {'below' if a > 0 else 'above'} the axis between the zeros.",
                 f"Hence \\({model_response_tex(rows)}\\)."],
                "A quadratic inequality is solved from a sketch: find the zeros, then read off where the graph is above or below the axis.",
                "Sketch the parabola with its zeros before deciding which region you need.",
                quicker="Test \\(x = 0\\) (or any easy value) in the original inequality to confirm the region.",
                common_errors=[err(region(wrong), "conceptual", "inequality direction", "That is the opposite region: check where the parabola is above or below the axis.", step=2)],
                skill="Solve a quadratic inequality using the graph.",
                params={"form": "ineq", "f": str(f), "rel": rel},
            )
        k = r.randint(2, 7)
        c = r.randint(-4, 4)
        return Generated(
            f"Find the natural domain of \\(f(x) = \\dfrac{{1}}{{\\sqrt{{{k * k} - {L((x - c) ** 2)}}}}}\\).",
            A_iv([(c - k, c + k, False, False)]), 2, 2,
            [f"We need \\({k * k} - {L((x - c) ** 2)} > 0\\) (strictly: the square root is in a denominator).",
             f"\\({L((x - c) ** 2)} < {k * k}\\) gives \\({-k} < {L(x - c)} < {k}\\), so \\({c - k} < x < {c + k}\\)."],
            "A square root needs a non-negative radicand, and a denominator cannot be zero, so a root in a denominator needs a positive radicand.",
            "List every restriction (root, denominator, log) and combine them.",
            quicker="Check an endpoint: it makes the denominator zero, so it must be excluded.",
            common_errors=[err(region([(c - k, c + k, True, True)]), "notation", DR, "The endpoints make the denominator zero, so they are excluded.", step=1)],
            skill="Find the natural domain when a root is in a denominator.",
            params={"form": "dom2", "k": k, "c": c},
        )
    # ---- d == 3 ----
    p, q = _two_roots(r)
    while (p + q) % 2:
        p, q = _two_roots(r)
    f = sp.expand((x - p) * (x - q))
    h = (p + q) // 2
    vy = f.subs(x, h)
    if r.random() < 0.5:
        rel = pick(r, ["\\le", ">"])
        rows = [(p, q, True, True)] if rel == "\\le" else [(None, p, False, False), (q, None, False, False)]
        text = multipart(f"Let \\(f(x) = {pl(f)}\\).",
                         [("a", "Find the \\(x\\)-intercepts of \\(y = f(x)\\).", 2),
                          ("b", "Find the coordinates of the vertex of the parabola.", 2),
                          ("c", f"Hence solve \\(f(x) {rel} 0\\).", 2)])
        return Generated(
            text, A_parts(P("a", 2, A_set([p, q])), P("b", 2, A_set([h, vy], ordered=True)), P("c", 2, A_iv(rows))), 6, 3,
            [f"(a) \\(f(x) = {L(sp.factor(f))}\\), so the intercepts are \\(x = {p}\\) and \\(x = {q}\\).",
             f"(b) The axis of symmetry is halfway between the zeros: \\(x = \\frac{{{p} + {pn(q)}}}{{2}} = {h}\\).",
             f"\\(f({h}) = {vy}\\), so the vertex is \\(({h}, {vy})\\).",
             f"(c) The parabola is concave up, so \\(f(x) {rel} 0\\) for \\({model_response_tex(rows)}\\)."],
            "The zeros, the axis of symmetry and the vertex of a parabola come from its factored form; a quadratic inequality is read from the graph.",
            "Sketch the parabola using (a) and (b) before answering (c).",
            quicker="The vertex lies on the axis of symmetry, halfway between the zeros.",
            common_errors=[err(S(-p, -q), "careless error", SIGN, "Sign error: \\(x - p = 0\\) gives \\(x = p\\).", step=1, part="a"),
                           err(S(-h, vy), "careless error", SIGN, "The axis of symmetry is \\(x = -\\frac{b}{2a}\\): check the sign.", step=2, part="b"),
                           err(region([(None, p, False, False), (q, None, False, False)] if rel == "\\le" else [(p, q, True, True)]), "conceptual",
                               "inequality direction", "That is the opposite region: a concave-up parabola is below the axis between its zeros.", step=4, part="c")],
            skill="Analyse a quadratic: intercepts, vertex and an inequality.",
            params={"form": "parts1", "f": str(f), "rel": rel},
        )
    hh = nonzero(r, -4, 4)
    g = x + hh
    fg = sp.expand(f.subs(x, g))
    text = multipart(f"Let \\(f(x) = {pl(f)}\\) and \\(g(x) = {pl(g)}\\).",
                     [("a", "Find \\(f(g(x))\\) in expanded form.", 2),
                      ("b", "Solve \\(f(g(x)) = 0\\).", 2),
                      ("c", "State the range of \\(y = f(x)\\).", 1)])
    return Generated(
        text, A_parts(P("a", 2, A_expr(fg)), P("b", 2, A_set([p - hh, q - hh])), P("c", 1, A_iv([(vy, None, True, False)], var="y"))), 5, 3,
        [f"(a) \\(f(g(x)) = f({pl(g)}) = ({pl(g)})^2 {sgn(f.coeff(x, 1))}({pl(g)}) {sgn(f.coeff(x, 0))} = {pl(fg)}\\)." if f.coeff(x, 1) else
         f"(a) \\(f(g(x)) = ({pl(g)})^2 {sgn(f.coeff(x, 0))} = {pl(fg)}\\).",
         f"(b) \\(f(u) = 0\\) when \\(u = {p}\\) or \\(u = {q}\\); with \\(u = {pl(g)}\\), \\(x = {p - hh}\\) or \\(x = {q - hh}\\).",
         f"(c) The vertex of \\(y = f(x)\\) is at \\(x = {h}\\), \\(y = {vy}\\); the parabola is concave up, so the range is \\(y \\ge {vy}\\)."],
        "\\(f(g(x))\\) substitutes the whole of \\(g(x)\\) for \\(x\\); the range of a concave-up parabola starts at its vertex.",
        "Bracket \\(g(x)\\) when substituting; for (b) solve \\(f(u) = 0\\) first, then undo \\(g\\).",
        quicker="Check (b): substitute each solution into \\(g\\) and confirm it gives a zero of \\(f\\).",
        common_errors=[err(S(p + hh, q + hh), "careless error", SIGN, f"If \\({pl(g)} = u\\) then \\(x = u {sgn(-hh)}\\).", step=2, part="b"),
                       err(S(p, q), "incomplete reasoning", ALG, "Those are the zeros of \\(f\\); undo \\(g\\) to find \\(x\\).", step=2, part="b"),
                       err(sp.expand(g.subs(x, f)), "conceptual", ALG, "That is \\(g(f(x))\\): substitute \\(g(x)\\) into \\(f\\).", step=1, part="a")],
        skill="Compose functions, solve the composite equation and state a range.",
        checkpoints=[cp(f.subs(x, g), "f(g(x)) before expanding", step=1, part="a")],
        params={"form": "parts2", "f": str(f), "g": str(g)},
    )


def model_response_tex(rows) -> str:
    """LaTeX for a region given as [(lo, hi, lo_closed, hi_closed)]."""
    out = []
    for lo, hi, lc, hc in rows:
        if lo is None:
            out.append(f"x {LE if hc else '<'} {L(hi)}")
        elif hi is None:
            out.append(f"x {GE if lc else '>'} {L(lo)}")
        else:
            out.append(f"{L(lo)} {LE if lc else '<'} x {LE if hc else '<'} {L(hi)}")
    return " \\text{ or } ".join(out)


# ================================================================= Y11-TRANS ===
BASES = [("x^2", x**2), ("x^3", x**3), ("\\sqrt{x}", sp.sqrt(x)), ("\\frac{1}{x}", 1 / x)]


def _units(v: int) -> str:
    return f"{abs(v)} unit" + ("" if abs(v) == 1 else "s")


def _shift_words(h: int, k: int) -> str:
    return f"{_units(h)} to the {'right' if h > 0 else 'left'} and {_units(k)} {'up' if k > 0 else 'down'}"


def t_Y11_TRANS(r: Rng, d: int) -> Generated:
    if d == 1:
        name, base = pick(r, BASES)
        h, k = nonzero(r, -5, 5), nonzero(r, -5, 5)
        g = base.subs(x, x - h) + k
        wrong = base.subs(x, x + h) + k
        return Generated(
            f"The graph of \\(y = {name}\\) is translated {_shift_words(h, k)}. Write the equation of the new graph.",
            A_expr(g), 1, 1,
            [f"A shift of {_units(h)} {'right' if h > 0 else 'left'} replaces \\(x\\) by \\({L(x - h)}\\); a shift {'up' if k > 0 else 'down'} adds \\({k}\\): \\(y = {L(g)}\\)."],
            "\\(y = f(x - h) + k\\) is \\(y = f(x)\\) translated \\(h\\) units right and \\(k\\) units up.",
            "Horizontal shifts act on \\(x\\) (the opposite way to the sign inside); vertical shifts are added outside.",
            quicker="Check with one point: the origin on the original graph should move to \\((h, k)\\).",
            common_errors=[err(wrong, "conceptual", TR, "A shift to the right replaces \\(x\\) by \\(x - h\\) (the sign inside is the opposite of the direction).", step=1)],
            skill="Write the equation of a translated graph.",
            params={"form": "shift", "base": str(base), "h": h, "k": k},
        )
    if d == 2:
        if r.random() < 0.5:
            name, base = pick(r, BASES[:3])
            a = pick(r, [2, 3, -2, sp.Rational(1, 2)])
            h, k = nonzero(r, -4, 4), nonzero(r, -5, 5)
            g = a * base.subs(x, x - h) + k
            how = (f"reflected in the \\(x\\)-axis and dilated vertically by a factor of \\({L(-a)}\\)" if a < 0 else f"dilated vertically by a factor of \\({L(a)}\\)")
            return Generated(
                f"The graph of \\(y = {name}\\) is {how}, then translated {_shift_words(h, k)}. Write the equation of the new graph.",
                A_expr(g), 2, 2,
                [f"The dilation{' and reflection' if a < 0 else ''} gives \\(y = {L(a * base)}\\).",
                 f"Then the translation gives \\(y = {L(g)}\\)."],
                "\\(y = a f(x - h) + k\\): dilate (and reflect) vertically by \\(a\\), then translate \\(h\\) right and \\(k\\) up.",
                "Apply the transformations one at a time, in the order given, writing the equation after each.",
                quicker="Check: a point \\((x_0, y_0)\\) on the original graph should move to \\((x_0 + h, a y_0 + k)\\).",
                common_errors=[err(a * (base.subs(x, x - h) + k), "conceptual", TR, "The translation comes after the dilation, so \\(k\\) is not multiplied by \\(a\\).", step=2),
                               err(a * base.subs(x, x + h) + k, "conceptual", TR, "A shift to the right replaces \\(x\\) by \\(x - h\\).", step=2)],
                skill="Combine a vertical dilation, reflection and translation.",
                checkpoints=[cp(a * base, "the dilated graph", step=1)],
                params={"form": "dil", "base": str(base), "a": str(a), "h": h, "k": k},
            )
        p0, q0 = nonzero(r, -6, 6), nonzero(r, -6, 6)
        a, b, c = pick(r, [2, 3, -1, -2]), pick(r, [2, 3, sp.Rational(1, 2)]), nonzero(r, -4, 4)
        xi, yi = sp.Rational(p0) / b, a * q0 + c
        return Generated(
            f"The point \\(({p0}, {q0})\\) lies on the graph of \\(y = f(x)\\). Find the coordinates of the corresponding point on the graph of \\(y = {co(a)}f({co(b, 'x')}) {sgn(c)}\\).",
            A_set([xi, yi], ordered=True), 2, 2,
            [f"Horizontally, \\(f({co(b, 'x')})\\) is a dilation by factor \\(\\frac{{1}}{{{L(b)}}}\\) from the \\(y\\)-axis: \\(x = {p0} \\div {L(b)} = {L(xi)}\\).",
             f"Vertically, multiply by \\({a}\\) then add \\({c}\\): \\(y = {a} \\times {pn(q0)} {sgn(c)} = {yi}\\). The point is \\(({L(xi)}, {yi})\\)."],
            "In \\(y = a f(bx) + c\\), \\(x\\)-values are divided by \\(b\\) and \\(y\\)-values are multiplied by \\(a\\) and then shifted by \\(c\\).",
            "Treat the horizontal and vertical changes separately.",
            quicker="Check: substituting your \\(x\\) gives \\(bx = " + str(p0) + "\\), the original input.",
            common_errors=[err(S(p0 * b, yi), "conceptual", TR, "\\(f(bx)\\) squeezes the graph horizontally: divide the \\(x\\)-value by \\(b\\).", step=1),
                           err(S(xi, a * (q0 + c)), "conceptual", TR, "Multiply by \\(a\\) first, then add the vertical shift.", step=2)],
            skill="Find the image of a point under combined transformations.",
            params={"form": "point", "p": p0, "q": q0, "a": a, "b": str(b), "c": c},
        )
    m = nonzero(r, -4, 4)
    f = x**2 - 2 * m * x
    a = pick(r, [2, 3, -1, -2])
    h, k = nonzero(r, -4, 4), nonzero(r, -6, 6)
    g = sp.expand(a * f.subs(x, x - h) + k)
    vx, vy = m + h, -a * m * m + k
    how = (f"reflected in the \\(x\\)-axis" + (f" and dilated vertically by a factor of \\({-a}\\)" if a != -1 else "") if a < 0
           else f"dilated vertically by a factor of \\({a}\\)")
    text = multipart(f"Let \\(f(x) = {pl(f)}\\).",
                     [("a", "Find the coordinates of the vertex of \\(y = f(x)\\).", 1),
                      ("b", f"The graph of \\(y = f(x)\\) is {how}, then translated {_shift_words(h, k)}. Find the coordinates of the vertex of the new graph.", 2),
                      ("c", "Write the equation of the new graph in expanded form.", 2)])
    return Generated(
        text, A_parts(P("a", 1, A_set([m, -m * m], ordered=True)), P("b", 2, A_set([vx, vy], ordered=True)), P("c", 2, A_expr(g))), 5, 3,
        [f"(a) Complete the square: \\(f(x) = {L((x - m) ** 2)} - {m * m}\\), so the vertex is \\(({m}, {-m * m})\\).",
         f"(b) The vertical change maps \\(y \\mapsto {co(a, 'y')} {sgn(k)}\\) and the horizontal shift maps \\(x \\mapsto {L(x + h)}\\).",
         f"So \\(({m}, {-m * m})\\) moves to \\(({vx}, {vy})\\).",
         f"(c) \\(y = {co(a)}f({L(x - h)}) {sgn(k)} = {co(a)}\\left({L((x - h) ** 2)} {sgn(-2 * m)}({L(x - h)})\\right) {sgn(k)} = {pl(g)}\\)."],
        "Transformations move every point of a graph: \\(y = a f(x - h) + k\\) sends \\((x_0, y_0)\\) to \\((x_0 + h, a y_0 + k)\\).",
        "Track the vertex through each transformation, then check the expanded equation has that vertex.",
        quicker=f"Check (c): \\(x = -\\frac{{b}}{{2a}}\\) for your expanded quadratic should give \\(x = {vx}\\).",
        common_errors=[err(S(m - h, vy), "conceptual", TR, "A shift to the right adds \\(h\\) to the \\(x\\)-coordinate.", step=2, part="b"),
                       err(S(vx, a * (-m * m + k)), "conceptual", TR, "Dilate first, then translate: \\(k\\) is not multiplied by \\(a\\).", step=2, part="b"),
                       err(sp.expand(a * (f.subs(x, x - h) + k)), "conceptual", TR, "The translation comes after the dilation, so \\(k\\) is not multiplied by \\(a\\).", step=4, part="c"),
                       err(S(-m, -m * m), "careless error", SIGN, "The vertex of \\(x^2 - 2mx\\) is at \\(x = m\\).", step=1, part="a")],
        skill="Track a parabola's vertex and equation through dilations, reflections and translations.",
        checkpoints=[cp(a * f.subs(x, x - h) + k, "the transformed equation before expanding", step=4, part="c")],
        params={"form": "parts", "f": str(f), "a": a, "h": h, "k": k},
    )


# ================================================================== Y11-TRIG ===
FNS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan}
ANGLES = [k * pi / 6 for k in range(1, 12) if k % 3] + [k * pi / 4 for k in (1, 3, 5, 7)]


def _eq_forms():
    """(function, coefficient, constant) with coefficient·f(x) = constant."""
    s2, s3 = sp.sqrt(2), sp.sqrt(3)
    out = []
    for fn_ in ("sin", "cos"):
        out += [(fn_, 2, 1), (fn_, 2, s3), (fn_, s2, 1)]
    out += [("tan", 1, 1), ("tan", 1, s3), ("tan", s3, 1)]
    return out


def _solutions(fn_: str, v) -> list:
    cands = sorted({sp.nsimplify(kk * pi / 12) for kk in range(0, 25) if kk % 2 == 0 or kk % 3 == 0}, key=float)
    out = []
    for th in cands:
        if fn_ == "tan" and sp.cos(th) == 0:
            continue
        val = FNS[fn_](th)
        if abs(float(val - v)) < 1e-12 and th not in out:
            out.append(th)
    return out


def _dp(v: float, dp: int = 1) -> str:
    """A float rounded half-up to ``dp`` places, as typed by a student (for common errors)."""
    from decimal import ROUND_HALF_UP, Decimal

    return str(Decimal(repr(v)).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP))


def _triangle(r: Rng):
    while True:
        a, b = r.randint(4, 15), r.randint(4, 15)
        C = pick(r, [35, 40, 50, 55, 65, 70, 75, 80, 100, 105, 110, 115, 125, 130])
        c2 = a * a + b * b - 2 * a * b * math.cos(math.radians(C))
        c = math.sqrt(c2)
        area = 0.5 * a * b * math.sin(math.radians(C))
        A = math.degrees(math.acos((b * b + c2 - a * a) / (2 * b * c)))
        c1 = round(c + 1e-12, 1)
        A_from_rounded = math.degrees(math.acos((b * b + c1 * c1 - a * a) / (2 * b * c1)))
        safe = all(abs((v * 10 ** dp) % 1 - 0.5) > 0.06 for v, dp in ((c, 1), (area, 1), (A, 0)))
        if a != b and safe and round(A) == round(A_from_rounded):
            return a, b, C, c, area, A


def t_Y11_TRIG(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.65:
            fn_ = pick(r, ["sin", "cos", "tan"])
            th = pick(r, ANGLES)
            while fn_ == "tan" and sp.cos(th) == 0:
                th = pick(r, ANGLES)
            val = sp.nsimplify(FNS[fn_](th))
            while val == 0:
                th = pick(r, ANGLES)
                val = sp.nsimplify(FNS[fn_](th))
            q = int(float(th) // (float(pi) / 2)) + 1
            acute = {1: th, 2: pi - th, 3: th - pi, 4: 2 * pi - th}[q]
            return Generated(
                f"Find the exact value of \\(\\{fn_} {L(th)}\\).",
                A_num(val), 1, 1,
                [f"\\({L(th)}\\) is in quadrant {q}, with related acute angle \\({L(acute)}\\); {fn_} is {'positive' if val > 0 else 'negative'} there (ASTC).",
                 f"\\(\\{fn_} {L(th)} = {L(val)}\\)."],
                "Exact values come from the 45°–45°–90° and 30°–60°–90° triangles; the quadrant (ASTC) gives the sign.",
                "Find the related acute angle, take its exact value, then attach the sign for the quadrant.",
                quicker="Sketch the unit circle: the point at that angle shows the sign of sin (y), cos (x) and tan (y/x).",
                common_errors=[err(-val, "careless error", SIGN, f"Wrong sign: {fn_} is {'positive' if val > 0 else 'negative'} in quadrant {q}.", step=1)],
                skill="Find an exact trigonometric value using the related angle and ASTC.",
                params={"form": "exact", "fn": fn_, "th": str(th)},
            )
        deg = pick(r, [30, 45, 60, 120, 135, 150, 210, 225, 240, 270, 300, 315, 330])
        rad = sp.Rational(deg, 180) * pi
        return Generated(
            f"Express \\({deg}^\\circ\\) in radians, as an exact value.",
            A_num(rad), 1, 1,
            [f"\\(180^\\circ = \\pi\\) radians, so \\({deg}^\\circ = {deg} \\times \\dfrac{{\\pi}}{{180}} = {L(rad)}\\)."],
            "\\(\\pi\\) radians is \\(180^\\circ\\).",
            "Multiply by \\(\\frac{\\pi}{180}\\) and simplify the fraction.",
            quicker=f"Sanity check: \\(90^\\circ = \\frac{{\\pi}}{{2}}\\), so \\({deg}^\\circ\\) should be \\(\\frac{{{deg}}}{{90}} \\times \\frac{{\\pi}}{{2}}\\).",
            common_errors=[err(sp.Rational(deg, 180), "formula selection", RAD, "The conversion factor is \\(\\frac{\\pi}{180}\\): the \\(\\pi\\) is missing.", step=1),
                           err(sp.Rational(180, deg) * pi, "formula selection", RAD, "Multiply by \\(\\frac{\\pi}{180}\\), not \\(\\frac{180}{\\pi}\\): the fraction is upside down.", step=1)],
            skill="Convert degrees to radians.",
            params={"form": "rad", "deg": deg},
        )
    if d == 2:
        if r.random() < 0.55:
            fn_, c0, k0 = pick(r, _eq_forms())
            s = pick(r, [1, -1])
            v = s * k0 / c0
            sols = _solutions(fn_, v)
            wrong = _solutions(fn_, -v)
            lhs = co(c0, "\\" + fn_ + " x")
            eq = f"{lhs} = {L(k0)}" if s > 0 else f"{lhs} + {L(k0)} = 0"
            return Generated(
                f"Solve \\({eq}\\) for \\(0 \\le x \\le 2\\pi\\).",
                A_set(sols), 2, 2,
                [f"\\(\\{fn_} x = {L(v)}\\); the related acute angle is \\({L(_solutions(fn_, abs(v))[0])}\\).",
                 f"\\(\\{fn_}\\) is {'positive' if v > 0 else 'negative'} in quadrants {', '.join(str(int(float(t_) // (float(pi) / 2)) + 1) for t_ in sols)}, so \\(x = {', '.join(L(t_) for t_ in sols)}\\)."],
                "Solve for the trig function first, find the related acute angle, then use ASTC to place every solution in the domain.",
                "Draw the quadrant diagram and list all solutions in \\([0, 2\\pi]\\), not just the calculator's.",
                quicker="Check each solution numerically on the calculator (in radian mode).",
                common_errors=[err(S(*wrong), "careless error", SIGN, f"Those solve \\(\\{fn_} x = {L(-v)}\\): check the sign and the quadrants.", step=2),
                               err(S(*[t_ * 180 / pi for t_ in sols]), "notation", RAD, "The domain is in radians, so give the solutions in radians.", step=2)],
                skill="Solve a trigonometric equation over \\([0, 2\\pi]\\).",
                params={"form": "eq", "fn": fn_, "v": str(v)},
            )
        a, b, C, c, area, A = _triangle(r)
        cc = sp.sqrt(a * a + b * b - 2 * a * b * sp.cos(pi * sp.Rational(C, 180)))
        radmode = math.sqrt(a * a + b * b - 2 * a * b * math.cos(C))
        return Generated(
            f"In triangle \\(ABC\\), \\(a = {a}\\) cm, \\(b = {b}\\) cm and \\(C = {C}^\\circ\\). Find the length of side \\(c\\), correct to 1 decimal place.",
            A_round(cc, 1, "cm"), 2, 2,
            [f"Cosine rule: \\(c^2 = a^2 + b^2 - 2ab\\cos C = {a * a} + {b * b} - {2 * a * b}\\cos {C}^\\circ\\).",
             f"\\(c^2 \\approx {c * c:.3f}\\), so \\(c \\approx {c:.1f}\\) cm."],
            "Two sides and the included angle: use the cosine rule.",
            "Write the rule with the letters first, then substitute; keep the calculator in degree mode.",
            quicker="The longest side is opposite the largest angle: an obtuse \\(C\\) must give the longest side.",
            common_errors=[err(_dp(radmode), "careless error", CALC, "Your calculator is in radian mode: the angle is in degrees.", step=2),
                           err(_dp(c * c), "incomplete reasoning", ALG, "That is \\(c^2\\): take the square root.", step=2)],
            skill="Find a side with the cosine rule.",
            params={"form": "cos", "a": a, "b": b, "C": C},
        )
    if r.random() < 0.5:
        a, b, C, c, area, A = _triangle(r)
        cc = sp.sqrt(a * a + b * b - 2 * a * b * sp.cos(pi * sp.Rational(C, 180)))
        ar = sp.Rational(1, 2) * a * b * sp.sin(pi * sp.Rational(C, 180))
        text = multipart(f"In triangle \\(ABC\\), \\(a = {a}\\) cm, \\(b = {b}\\) cm and \\(C = {C}^\\circ\\).",
                         [("a", "Find the length of side \\(c\\), correct to 1 decimal place.", 2),
                          ("b", "Find the area of the triangle, correct to 1 decimal place.", 1),
                          ("c", "Find the size of angle \\(A\\), correct to the nearest degree.", 2)])
        return Generated(
            text, A_parts(P("a", 2, A_round(cc, 1, "cm")), P("b", 1, A_round(ar, 1, "cm^2")), P("c", 2, {"type": "num", "value": f"{A:.10f}", "dp": 0, "units": "°"})), 5, 3,
            [f"(a) \\(c^2 = {a * a} + {b * b} - {2 * a * b}\\cos {C}^\\circ \\approx {c * c:.3f}\\), so \\(c \\approx {c:.1f}\\) cm.",
             f"(b) Area \\(= \\frac{{1}}{{2}}ab\\sin C = \\frac{{1}}{{2}} \\times {a} \\times {b} \\times \\sin {C}^\\circ \\approx {area:.1f}\\) cm².",
             f"(c) \\(\\cos A = \\dfrac{{b^2 + c^2 - a^2}}{{2bc}} \\approx {(b * b + c * c - a * a) / (2 * b * c):.4f}\\), so \\(A \\approx {round(A)}^\\circ\\)."],
            "The cosine rule finds a side from two sides and the included angle (or an angle from three sides); the area is \\(\\frac{1}{2}ab\\sin C\\).",
            "Keep the unrounded value of \\(c\\) in the calculator memory for part (c); use degree mode throughout.",
            quicker="Using the cosine rule for an angle avoids the ambiguous case of the sine rule.",
            common_errors=[err(_dp(math.sqrt(a * a + b * b - 2 * a * b * math.cos(C))), "careless error", CALC, "Your calculator is in radian mode: the angle is in degrees.", step=1, part="a"),
                           err(_dp(a * b * math.sin(math.radians(C))), "formula selection", ALG, "The area is \\(\\frac{1}{2}ab\\sin C\\): the half is missing.", step=2, part="b")],
            skill="Solve a triangle with the cosine rule and find its area.",
            params={"form": "tri", "a": a, "b": b, "C": C},
        )
    rr = r.randint(3, 12)
    th = pick(r, [pi / 6, pi / 4, pi / 3, pi / 2, 2 * pi / 3, 3 * pi / 4, 5 * pi / 6])
    arc, sec = rr * th, sp.Rational(rr * rr, 2) * th
    seg = sp.Rational(rr * rr, 2) * (th - sp.sin(th))
    deg = int(th * 180 / pi)
    text = multipart(f"A sector of a circle has radius {rr} cm and angle \\({L(th)}\\) at the centre.",
                     [("a", "Find the exact arc length.", 1), ("b", "Find the exact area of the sector.", 1),
                      ("c", "Find the exact area of the minor segment cut off by the chord.", 2)])
    return Generated(
        text, A_parts(P("a", 1, A_units(arc, "cm")), P("b", 1, A_units(sec, "cm^2")), P("c", 2, A_units(seg, "cm^2"))), 4, 3,
        [f"(a) \\(\\ell = r\\theta = {rr} \\times {L(th)} = {L(arc)}\\) cm.",
         f"(b) \\(A = \\frac{{1}}{{2}}r^2\\theta = \\frac{{1}}{{2}} \\times {rr * rr} \\times {L(th)} = {L(sec)}\\) cm².",
         f"(c) Segment \\(= \\frac{{1}}{{2}}r^2(\\theta - \\sin\\theta) = {L(sp.Rational(rr * rr, 2))}\\left({L(th)} - {L(sp.sin(th))}\\right) = {L(sp.expand(seg))}\\) cm²."],
        "With \\(\\theta\\) in radians: arc length \\(r\\theta\\), sector area \\(\\frac{1}{2}r^2\\theta\\), segment = sector − triangle \\(= \\frac{1}{2}r^2(\\theta - \\sin\\theta)\\).",
        "Use radians in every formula; keep \\(\\pi\\) and surds for exact answers.",
        quicker="The segment must be smaller than the sector: compare your decimal values.",
        common_errors=[err(rr * deg, "conceptual", RAD, "The formula \\(\\ell = r\\theta\\) needs \\(\\theta\\) in radians, not degrees.", step=1, part="a"),
                       err(rr * rr * th, "formula selection", ALG, "The sector area is \\(\\frac{1}{2}r^2\\theta\\): the half is missing.", step=2, part="b"),
                       err(sec, "incomplete reasoning", ALG, "That is the sector; subtract the triangle \\(\\frac{1}{2}r^2\\sin\\theta\\) to get the segment.", step=3, part="c")],
        skill="Arc length, sector area and segment area in radians.",
        params={"form": "sector", "r": rr, "th": str(th)},
    )


# ================================================================== Y11-CALC ===
def t_Y11_CALC(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            a, b, c = r.randint(1, 5), nonzero(r, -6, 6), r.randint(2, 4)
            f = a * x**c + b * x
            m = nonzero(r, -2, 3)
            g = sp.diff(f, x).subs(x, m)
            return Generated(
                f"Find the gradient of the tangent to \\(y = {pl(f)}\\) at the point where \\(x = {m}\\).",
                A_num(g), 1, 1,
                [f"\\(\\dfrac{{dy}}{{dx}} = {pl(sp.diff(f, x))}\\); at \\(x = {m}\\) the gradient is \\({g}\\)."],
                "The derivative gives the gradient of the tangent at each point.",
                "Differentiate first, then substitute.",
                quicker="\\(\\frac{d}{dx}x^n = nx^{n-1}\\) term by term.",
                common_errors=[err(f.subs(x, m), "conceptual", DIFF, "That is the \\(y\\)-value; the gradient is \\(\\frac{dy}{dx}\\) at that point.", step=1),
                               err(a * c * m**c + b, "algebraic", DIFF, "\\(\\frac{d}{dx}x^n = nx^{n-1}\\): reduce the index by one.", step=1)],
                skill="Find the gradient of a tangent.",
                params={"form": "grad", "f": str(f), "m": m},
            )
        a, p = nonzero(r, -5, 6), r.randint(2, 5)
        b, q = nonzero(r, -6, 6), r.randint(1, 3)
        f = a * x**p + b / x**q
        df = sp.diff(f, x)
        return Generated(
            f"Differentiate \\(y = {co(a, f'x^{{{p}}}')} {'+' if b > 0 else '-'} \\dfrac{{{abs(b)}}}{{{L(x**q)}}}\\).",
            A_expr(df), 2, 1,
            [f"Write \\(\\dfrac{{{abs(b)}}}{{{L(x**q)}}} = {co(abs(b), 'x')}^{{{-q}}}\\).",
             f"\\(\\dfrac{{dy}}{{dx}} = {L(a * p * x**(p - 1))} {'-' if b > 0 else '+'} {co(abs(b * q), 'x')}^{{{-q - 1}}} = {L(df)}\\)."],
            "Rewrite reciprocals as negative powers, then use \\(\\frac{d}{dx}x^n = nx^{n-1}\\) for every \\(n\\).",
            "Index form first; the index of a negative power becomes more negative.",
            quicker="Check the second term: \\(-q - 1\\) is further from zero than \\(-q\\).",
            common_errors=[err(a * p * x**(p - 1) - b * q * x**(-q + 1), "algebraic", IDX, "Subtracting 1 from a negative index makes it more negative: \\(x^{-q} \\to x^{-q-1}\\).", step=2),
                           err(a * p * x**(p - 1) + b * q * x**(-q - 1), "careless error", SIGN, "Bring down the negative index: the coefficient changes sign.", step=2)],
            skill="Differentiate negative powers.",
            checkpoints=[cp(a * x**p + b * x**(-q), "the index form", step=1)],
            params={"form": "neg", "f": str(f)},
        )
    if d == 2:
        form = pick(r, ["tangent", "chain", "quot"])
        if form == "tangent":
            a, b, c = nonzero(r, -2, 3), nonzero(r, -5, 5), r.randint(-6, 6)
            f = a * x**2 + b * x + c
            m = nonzero(r, -3, 3)
            g, y0 = sp.diff(f, x).subs(x, m), f.subs(x, m)
            tan_ = sp.expand(g * (x - m) + y0)
            normal = sp.expand(-(x - m) / g + y0) if g else None
            ces = [err(sp.expand(g * x), "incomplete reasoning", ALG, "The tangent passes through the point of contact: use \\(y - y_1 = m(x - x_1)\\).", step=3)]
            if normal is not None:
                ces.append(err(normal, "conceptual", DIFF, "That is the normal; the tangent has gradient \\(f'(x_1)\\) itself.", step=3))
            return Generated(
                f"Find the equation of the tangent to \\(y = {pl(f)}\\) at the point where \\(x = {m}\\).",
                A_expr(tan_), 3, 2,
                [f"\\(y' = {pl(sp.diff(f, x))}\\), so the gradient at \\(x = {m}\\) is \\({g}\\).",
                 f"The point of contact is \\(({m}, {y0})\\).",
                 f"\\(y - {pn(y0)} = {g}(x - {pn(m)})\\), so \\(y = {pl(tan_)}\\)."],
                "The tangent at \\(x_1\\) passes through \\((x_1, f(x_1))\\) with gradient \\(f'(x_1)\\).",
                "Find the point, the gradient, then use the point–gradient form \\(y - y_1 = m(x - x_1)\\).",
                quicker="Check: your tangent and the curve give the same \\(y\\) at \\(x = " + str(m) + "\\).",
                common_errors=ces,
                skill="Find the equation of a tangent.",
                checkpoints=[cp(sp.diff(f, x), "the derivative", step=1)],
                params={"form": "tangent", "f": str(f), "m": m},
            )
        if form == "chain":
            a, b, nn = nonzero(r, -4, 5), nonzero(r, -7, 7), r.randint(3, 6)
            while a in (1, -1):
                a = nonzero(r, -4, 5)
            inner = a * x + b
            f = inner**nn
            df = nn * a * inner ** (nn - 1)
            return Generated(
                f"Differentiate \\(y = ({pl(inner)})^{{{nn}}}\\).",
                A_expr(df), 2, 2,
                [f"Let \\(u = {pl(inner)}\\), so \\(y = u^{{{nn}}}\\) and \\(\\frac{{du}}{{dx}} = {a}\\).",
                 f"\\(\\dfrac{{dy}}{{dx}} = {nn}u^{{{nn - 1}}} \\times {pn(a)} = {L(nn * a)}({pl(inner)})^{{{nn - 1}}}\\)."],
                "Chain rule: \\(\\frac{dy}{dx} = \\frac{dy}{du} \\times \\frac{du}{dx}\\).",
                "Differentiate the outside, keep the inside, then multiply by the derivative of the inside.",
                quicker="For \\((ax + b)^n\\) the derivative is \\(na(ax + b)^{n-1}\\).",
                common_errors=[err(nn * inner ** (nn - 1), "algebraic", CHAIN, "Multiply by the derivative of the inside (the chain-rule factor).", step=2)],
                skill="Differentiate a power of a linear function with the chain rule.",
                params={"form": "chain", "f": str(f)},
            )
        a, b, c, dd = nonzero(r, -4, 4), r.randint(-6, 6), r.randint(1, 3), nonzero(r, -5, 5)
        while a * dd - b * c == 0:
            b = r.randint(-6, 6)
        num, den = a * x + b, c * x + dd
        df = sp.Rational(a * dd - b * c) / den**2
        return Generated(
            f"Differentiate \\(y = \\dfrac{{{pl(num)}}}{{{pl(den)}}}\\).",
            A_expr(df), 2, 2,
            [f"Quotient rule with \\(u = {pl(num)}\\), \\(v = {pl(den)}\\): \\(u' = {a}\\), \\(v' = {c}\\).",
             f"\\(\\dfrac{{dy}}{{dx}} = \\dfrac{{vu' - uv'}}{{v^2}} = \\dfrac{{{a}({pl(den)}) - {c}({pl(num)})}}{{({pl(den)})^2}} = {L(df)}\\)."],
            "Quotient rule: \\(\\frac{d}{dx}\\frac{u}{v} = \\frac{vu' - uv'}{v^2}\\).",
            "Write \\(u, v, u', v'\\) first; the order in the numerator matters.",
            quicker="For \\(\\frac{ax + b}{cx + d}\\) the numerator simplifies to the constant \\(ad - bc\\).",
            common_errors=[err(-df, "careless error", "quotient rule", "The numerator is \\(vu' - uv'\\), not \\(uv' - vu'\\).", step=2)],
            skill="Differentiate a quotient.",
            params={"form": "quot", "f": str(num / den)},
        )
    s0 = nonzero(r, -2, 2)
    p, qq, c0 = 3 * s0, r.randint(-9, 9), r.randint(-8, 8)
    f = x**3 + p * x**2 + qq * x + c0
    m = nonzero(r, -3, 3)
    while m == -s0:
        m = nonzero(r, -3, 3)
    df = sp.diff(f, x)
    g, y0 = df.subs(x, m), f.subs(x, m)
    tan_ = sp.expand(g * (x - m) + y0)
    other = -m - 2 * s0
    text = multipart(f"A curve has equation \\(y = {pl(f)}\\).",
                     [("a", "Find \\(\\dfrac{dy}{dx}\\).", 1),
                      ("b", f"Find the equation of the tangent to the curve at the point where \\(x = {m}\\).", 2),
                      ("c", "Find the \\(x\\)-coordinate of the other point on the curve where the tangent is parallel to this tangent.", 2)])
    return Generated(
        text, A_parts(P("a", 1, A_expr(df)), P("b", 2, A_expr(tan_)), P("c", 2, A_num(other))), 5, 3,
        [f"(a) \\(\\dfrac{{dy}}{{dx}} = {pl(df)}\\).",
         f"(b) At \\(x = {m}\\): \\(y = {y0}\\) and the gradient is \\({g}\\).",
         f"\\(y - {pn(y0)} = {g}(x - {pn(m)})\\), so \\(y = {pl(tan_)}\\).",
         f"(c) Parallel tangents have equal gradients: \\({pl(df)} = {g}\\), i.e. \\({pl(sp.expand(df - g))} = 0\\).",
         f"\\(x = {m}\\) is one root, so factorise: \\({L(sp.factor(df - g))} = 0\\), giving the other point at \\(x = {other}\\)."],
        "Parallel lines have equal gradients, so parallel tangents occur where \\(\\frac{dy}{dx}\\) takes the same value.",
        "In (c) you already know one root of the quadratic, which makes factorising quick.",
        quicker=f"The two \\(x\\)-values are symmetric about the point of inflection \\(x = {-s0}\\): their average is \\({-s0}\\).",
        common_errors=[err(m, "interpretation", DIFF, "That is the original point; the question asks for the other one.", step=5, part="c"),
                       err(-other, "careless error", SIGN, "Sign error when factorising the quadratic.", step=5, part="c"),
                       err(sp.expand(g * x), "incomplete reasoning", ALG, "The tangent passes through the point of contact: use \\(y - y_1 = m(x - x_1)\\).", step=3, part="b")],
        skill="Tangents to a cubic and parallel tangents.",
        checkpoints=[cp(df, "the derivative", step=1, part="b"), cp(sp.expand(df - g), "the gradient equation", step=4, part="c")],
        params={"form": "parts", "f": str(f), "m": m},
    )


# ================================================================ Y11-EXPLOG ===
PRODUCTS = {2: [(4, 2, 3), (8, 1, 3), (8, 2, 4), (16, 1, 4), (8, 4, 5), (16, 2, 5)], 3: [(9, 1, 2), (9, 3, 3), (27, 1, 3), (27, 3, 4)],
            5: [(25, 1, 2), (25, 5, 3)]}


def _log_diff(r: Rng):
    b = pick(r, [2, 3, 5])
    u = pick(r, [v for v in (3, 5, 6, 7) if v % b])
    k = r.randint(1, 3)
    return b, u * b**k, u, k


def _log_eq(r: Rng):
    b = pick(r, [2, 3, 5])
    big, small, m = pick(r, PRODUCTS[b])
    if r.random() < 0.5:  # log x + log(x - k) = m: x = big, x - k = small
        return b, m, big - small, big, -small, "-"
    return b, m, big - small, small, -big, "+"  # log x + log(x + k) = m: x = small


def t_Y11_EXPLOG(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            b, X, Y, k = _log_diff(r)
            return Generated(
                f"Evaluate \\(\\log_{{{b}}} {X} - \\log_{{{b}}} {Y}\\) without a calculator.",
                A_num(k), 1, 1,
                [f"\\(\\log_{{{b}}} {X} - \\log_{{{b}}} {Y} = \\log_{{{b}}} \\dfrac{{{X}}}{{{Y}}} = \\log_{{{b}}} {b**k} = {k}\\)."],
                "\\(\\log_b M - \\log_b N = \\log_b \\frac{M}{N}\\) and \\(\\log_b b^n = n\\).",
                "Combine into one logarithm, then write the number as a power of the base.",
                quicker=f"Check: \\({b}^{{{k}}} = {b**k}\\).",
                common_errors=[err(b**k, "incomplete reasoning", LOGS, f"\\(\\frac{{{X}}}{{{Y}}} = {b**k}\\), and \\(\\log_{{{b}}} {b**k}\\) is the power, {k}.", step=1)],
                skill="Use the log laws to evaluate without a calculator.",
                params={"form": "logdiff", "b": b, "X": X, "Y": Y},
            )
        b = pick(r, [2, 3, 5])
        a, c = pick(r, [2, 3]), nonzero(r, -3, 3)
        k = r.randint(1, 3)
        sign = pick(r, [1, -1])
        rhs = f"{b**k}" if sign > 0 else f"\\frac{{1}}{{{b**k}}}"
        sol = sp.Rational(sign * k - c, a)
        return Generated(
            f"Solve \\({b}^{{{L(a * x + c)}}} = {rhs}\\).",
            A_num(sol), 1, 1,
            [f"\\({rhs} = {b}^{{{sign * k}}}\\), so \\({L(a * x + c)} = {sign * k}\\) and \\(x = {L(sol)}\\)."],
            "Write both sides as powers of the same base and equate the indices.",
            "Express the right-hand side as a power of the base first" + (" (a reciprocal is a negative power)." if sign < 0 else "."),
            quicker="Substitute your \\(x\\) back into the index to check.",
            common_errors=[err(sp.Rational((b**k if sign > 0 else 1) - c, a) if sign > 0 else sp.Rational(k - c, a), "conceptual", IDX,
                               "Equate the indices, not the index and the number." if sign > 0 else "\\(\\frac{1}{b^k} = b^{-k}\\): the index is negative.", step=1)],
            skill="Solve an exponential equation by matching bases.",
            params={"form": "index", "b": b, "a": a, "c": c, "rhs": str(sp.Integer(b) ** (sign * k))},
        )
    if d == 2:
        if r.random() < 0.5:
            a = pick(r, [2, 3, 5, 7])
            c = pick(r, [v for v in range(5, 60) if not sp.log(v, a).is_Rational])
            sol = sp.log(c) / sp.log(a)
            return Generated(
                f"Solve \\({a}^x = {c}\\), giving \\(x\\) correct to 2 decimal places.",
                A_round(sol, 2), 2, 2,
                [f"Take logarithms: \\(x\\ln {a} = \\ln {c}\\).", f"\\(x = \\dfrac{{\\ln {c}}}{{\\ln {a}}} \\approx {rnd(sol, 2)}\\)."],
                "Logarithms bring the unknown index down: \\(\\ln a^x = x\\ln a\\).",
                "Take ln of both sides, then divide; round only at the end.",
                quicker=f"Estimate: \\({a}^{{{int(math.log(c, a))}}} = {a ** int(math.log(c, a))}\\) and \\({a}^{{{int(math.log(c, a)) + 1}}} = {a ** (int(math.log(c, a)) + 1)}\\), so \\(x\\) lies between {int(math.log(c, a))} and {int(math.log(c, a)) + 1}.",
                common_errors=[err(rnd(sp.log(sp.Rational(c, a)), 2), "algebraic", LOGS, "\\(\\frac{\\ln c}{\\ln a}\\) is not \\(\\ln\\frac{c}{a}\\).", step=2),
                               err(rnd(sp.Rational(c, a), 2), "conceptual", LOGS, "Dividing by the base does not undo a power; take logarithms.", step=1)],
                skill="Solve an exponential equation with logarithms.",
                params={"form": "ln", "a": a, "c": c},
            )
        b, m, k, sol, bad, op = _log_eq(r)
        return Generated(
            f"Solve \\(\\log_{{{b}}} x + \\log_{{{b}}}(x {op} {k}) = {m}\\).",
            A_num(sol), 3, 2,
            [f"\\(\\log_{{{b}}} x(x {op} {k}) = {m}\\), so \\(x(x {op} {k}) = {b}^{{{m}}} = {b**m}\\).",
             f"\\(x^2 {op} {k}x - {b**m} = 0\\) gives \\({L((x - sol) * (x - bad))} = 0\\), so \\(x = {sol}\\) or \\(x = {bad}\\).",
             f"\\(\\log_{{{b}}} x\\) needs \\(x > 0\\), so \\(x = {bad}\\) is rejected: \\(x = {sol}\\)."],
            "Combine the logs, convert to index form, solve, then check every solution against the domain of each logarithm.",
            "Always test candidate solutions in the original equation: a log of a negative number is undefined.",
            quicker="Check: \\(" + f"{sol} \\times {sol + (k if op == '+' else -k)} = {b**m}" + "\\).",
            common_errors=[err(bad, "interpretation", DR, "That solution makes \\(\\log_b x\\) undefined (\\(x > 0\\) is needed): reject it.", step=3)],
            skill="Solve a logarithmic equation and reject invalid solutions.",
            checkpoints=[cp(b**m, "the index form", step=1)],
            params={"form": "logeq", "b": b, "m": m, "k": k, "op": op},
        )
    b1 = pick(r, [2, 3])
    i, j = sorted(r.sample(range(0, 4), 2))
    p_, q_ = b1**i, b1**j
    lb, X, Y, kk = _log_diff(r)
    b, m, k, sol, bad, op = _log_eq(r)
    text = multipart("",
                     [("a", f"Evaluate \\(\\log_{{{lb}}} {X} - \\log_{{{lb}}} {Y}\\).", 1),
                      ("b", f"Solve \\({b1}^{{2x}} - {p_ + q_} \\times {b1}^x + {p_ * q_} = 0\\).", 3),
                      ("c", f"Solve \\(\\log_{{{b}}} x + \\log_{{{b}}}(x {op} {k}) = {m}\\).", 2)])
    return Generated(
        text, A_parts(P("a", 1, A_num(kk)), P("b", 3, A_set([i, j])), P("c", 2, A_num(sol))), 6, 3,
        [f"(a) \\(\\log_{{{lb}}} \\dfrac{{{X}}}{{{Y}}} = \\log_{{{lb}}} {lb**kk} = {kk}\\).",
         f"(b) Let \\(u = {b1}^x\\): \\(u^2 - {p_ + q_}u + {p_ * q_} = 0\\), so \\((u - {p_})(u - {q_}) = 0\\).",
         f"\\({b1}^x = {p_}\\) or \\({b1}^x = {q_}\\), so \\(x = {i}\\) or \\(x = {j}\\).",
         f"(c) \\(x(x {op} {k}) = {b**m}\\), so \\(x = {sol}\\) or \\(x = {bad}\\); \\(x > 0\\) is needed, so \\(x = {sol}\\)."],
        "Log laws combine logarithms; an equation in \\(b^{2x}\\) and \\(b^x\\) is a quadratic in \\(u = b^x\\); logarithm equations need a domain check.",
        "Substitute \\(u = b^x\\) to see the quadratic; return to \\(x\\) at the end.",
        quicker="Check (b) by substituting each \\(x\\) into the original equation.",
        common_errors=[err(S(p_, q_), "incomplete reasoning", IDX, "Those are the values of \\(u = b^x\\); solve \\(b^x = u\\) for \\(x\\).", step=3, part="b"),
                       err(bad, "interpretation", DR, "That solution makes \\(\\log_b x\\) undefined: reject it.", step=4, part="c"),
                       err(lb**kk, "incomplete reasoning", LOGS, "That is the number inside the log; its logarithm is the power.", step=1, part="a")],
        skill="Log laws, exponential equations reducible to quadratics, and log equations.",
        checkpoints=[cp(b**m, "the index form in (c)", step=4, part="c")],
        params={"form": "parts", "lb": lb, "X": X, "Y": Y, "b1": b1, "p": p_, "q": q_, "b": b, "m": m, "k": k, "op": op},
    )


# ================================================================== Y11-PROB ===
def _survey(r: Rng):
    while True:
        N = pick(r, [40, 50, 60, 80, 100, 120])
        nab = r.randint(3, N // 5)
        na, nb = nab + r.randint(3, N // 3), nab + r.randint(3, N // 3)
        if na + nb - nab < N - 2:
            return N, na, nb, nab


SUBJ = [("Chemistry", "Biology"), ("Economics", "Legal Studies"), ("Music", "Drama"), ("Physics", "Software Engineering")]


def t_Y11_PROB(r: Rng, d: int) -> Generated:
    F = sp.Rational
    if d == 1:
        form = pick(r, ["union", "dice"])
        if form == "union":
            p1 = pick(r, [F(1, 2), F(1, 3), F(2, 5), F(3, 10)])
            p2 = pick(r, [F(1, 4), F(3, 4), F(1, 6), F(2, 3)])
            ans = p1 + p2 - p1 * p2
            return Generated(
                f"Events \\(A\\) and \\(B\\) are independent, with \\(P(A) = {L(p1)}\\) and \\(P(B) = {L(p2)}\\). Find \\(P(A \\cup B)\\).",
                A_num(ans), 2, 1,
                [f"Independent: \\(P(A \\cap B) = P(A)P(B) = {L(p1 * p2)}\\).",
                 f"\\(P(A \\cup B) = P(A) + P(B) - P(A \\cap B) = {L(ans)}\\)."],
                "For independent events \\(P(A \\cap B) = P(A)P(B)\\); the addition rule subtracts the overlap once.",
                "Write the addition rule before substituting.",
                quicker=f"Or use the complement: \\(1 - (1 - {L(p1)})(1 - {L(p2)})\\).",
                common_errors=[err(p1 + p2, "conceptual", PROB, "The overlap \\(P(A \\cap B)\\) has been counted twice: subtract it.", step=2),
                               err(p1 * p2, "conceptual", PROB, "That is \\(P(A \\cap B)\\) ('and'); the union means 'or'.", step=2)],
                skill="Use the addition rule with independent events.",
                params={"form": "union", "p1": str(p1), "p2": str(p2)},
            )
        s = r.randint(3, 11)
        ways = sum(1 for i in range(1, 7) for j in range(1, 7) if i + j == s)
        return Generated(
            f"Two fair six-sided dice are rolled. Find the probability that the sum of the two numbers is {s}.",
            A_num(F(ways, 36)), 1, 1,
            [f"There are 36 equally likely ordered outcomes, and {ways} of them give a sum of {s}, so the probability is \\({L(F(ways, 36))}\\)."],
            "With equally likely outcomes, probability = favourable outcomes ÷ total outcomes.",
            "List the outcomes in a 6 × 6 table so none is missed or double counted.",
            quicker="A sum of 7 is the most likely (6 ways); the number of ways rises by one from a sum of 2 up to 7, then falls.",
            common_errors=[err(F(1, 11), "conceptual", PROB, "The 11 possible sums are not equally likely: count the 36 ordered outcomes.", step=1)],
            skill="Probability from a sample space of equally likely outcomes.",
            params={"form": "dice", "s": s},
        )
    if d == 2:
        if r.random() < 0.5:
            N, na, nb, nab = _survey(r)
            sa, sb = pick(r, SUBJ)
            return Generated(
                f"Of {N} students, {na} study {sa}, {nb} study {sb} and {nab} study both. A student is chosen at random. "
                f"Given that the student studies {sb}, find the probability that they also study {sa}.",
                A_num(F(nab, nb)), 2, 2,
                [f"Let \\(A\\) = studies {sa}, \\(B\\) = studies {sb}. \\(P(A \\mid B) = \\dfrac{{P(A \\cap B)}}{{P(B)}}\\).",
                 f"\\(= \\dfrac{{{nab}/{N}}}{{{nb}/{N}}} = \\dfrac{{{nab}}}{{{nb}}} = {L(F(nab, nb))}\\)."],
                "Conditional probability restricts the sample space to the given event: \\(P(A \\mid B) = \\frac{P(A \\cap B)}{P(B)}\\).",
                "Identify which event is given; it goes in the denominator.",
                quicker=f"Think of only the {nb} students who study {sb}: how many of them study {sa}?",
                common_errors=[err(F(nab, N), "interpretation", PROB, "That is \\(P(A \\cap B)\\); the condition restricts the sample space.", step=2),
                               err(F(nab, na), "interpretation", PROB, "That is \\(P(B \\mid A)\\): the given event goes in the denominator.", step=2)],
                skill="Find a conditional probability from counts.",
                params={"form": "cond", "N": N, "na": na, "nb": nb, "nab": nab},
            )
        R, B = r.randint(3, 8), r.randint(2, 7)
        T = R + B
        ans = F(2 * R * B, T * (T - 1))
        return Generated(
            f"A bag contains {R} red and {B} blue marbles. Two marbles are drawn at random without replacement. Find the probability that one of each colour is drawn.",
            A_num(ans), 2, 2,
            [f"\\(P(RB) = \\dfrac{{{R}}}{{{T}}} \\times \\dfrac{{{B}}}{{{T - 1}}}\\) and \\(P(BR) = \\dfrac{{{B}}}{{{T}}} \\times \\dfrac{{{R}}}{{{T - 1}}}\\).",
             f"\\(P(\\text{{one of each}}) = 2 \\times \\dfrac{{{R * B}}}{{{T * (T - 1)}}} = {L(ans)}\\)."],
            "Without replacement the second probability changes; 'one of each' happens in two orders.",
            "Draw a two-stage tree diagram and add the branches that fit.",
            quicker=f"Or count combinations: \\(\\dfrac{{{R} \\times {B}}}{{\\binom{{{T}}}{{2}}}}\\).",
            common_errors=[err(F(R * B, T * (T - 1)), "incomplete reasoning", PROB, "One of each can happen in two orders (red then blue, or blue then red).", step=2),
                           err(F(2 * R * B, T * T), "conceptual", PROB, "The marbles are not replaced, so the second denominator is one less.", step=1)],
            skill="Two-stage probability without replacement.",
            params={"form": "draw", "R": R, "B": B},
        )
    if r.random() < 0.5:
        N, na, nb, nab = _survey(r)
        sa, sb = pick(r, SUBJ)
        union, neither, one = F(na + nb - nab, N), F(N - na - nb + nab, N), F(na + nb - 2 * nab, N)
        text = multipart(f"Of {N} students, {na} study {sa}, {nb} study {sb} and {nab} study both. A student is chosen at random.",
                         [("a", f"Find the probability that the student studies {sa} or {sb}.", 1),
                          ("b", "Find the probability that the student studies neither.", 1),
                          ("c", f"Given that the student studies {sb}, find the probability that they also study {sa}.", 2),
                          ("d", "Find the probability that the student studies exactly one of the two subjects.", 1)])
        return Generated(
            text, A_parts(P("a", 1, A_num(union)), P("b", 1, A_num(neither)), P("c", 2, A_num(F(nab, nb))), P("d", 1, A_num(one))), 5, 3,
            [f"Venn diagram: only {sa} \\(= {na - nab}\\), both \\(= {nab}\\), only {sb} \\(= {nb - nab}\\), neither \\(= {N - na - nb + nab}\\).",
             f"(a) \\(P(A \\cup B) = \\dfrac{{{na} + {nb} - {nab}}}{{{N}}} = {L(union)}\\).",
             f"(b) \\(P(\\text{{neither}}) = 1 - P(A \\cup B) = {L(neither)}\\).",
             f"(c) \\(P(A \\mid B) = \\dfrac{{{nab}}}{{{nb}}} = {L(F(nab, nb))}\\).",
             f"(d) \\(P(\\text{{exactly one}}) = \\dfrac{{{na - nab} + {nb - nab}}}{{{N}}} = {L(one)}\\)."],
            "A Venn diagram organises overlapping events; 'or' includes both, 'exactly one' excludes the overlap, and a condition restricts the sample space.",
            "Fill in the Venn diagram from the inside (the overlap) outwards before answering.",
            quicker="Check: the four Venn regions add to the total " + str(N) + ".",
            common_errors=[err(F(na + nb, N), "conceptual", PROB, "The students studying both have been counted twice.", step=2, part="a"),
                           err(F(nab, na), "interpretation", PROB, "That is \\(P(B \\mid A)\\): the given event goes in the denominator.", step=4, part="c"),
                           err(union, "interpretation", PROB, "That includes the students who study both; 'exactly one' excludes them.", step=5, part="d")],
            skill="Venn diagrams, the addition rule and conditional probability.",
            params={"form": "venn", "N": N, "na": na, "nb": nb, "nab": nab},
        )
    R, B = r.randint(3, 8), r.randint(2, 7)
    T = R + B
    rr_ = F(R * (R - 1), T * (T - 1))
    mix = F(2 * R * B, T * (T - 1))
    atl = 1 - F(B * (B - 1), T * (T - 1))
    text = multipart(f"A bag contains {R} red and {B} blue marbles. Two marbles are drawn at random without replacement.",
                     [("a", "Find the probability that both marbles are red.", 1),
                      ("b", "Find the probability that one marble of each colour is drawn.", 2),
                      ("c", "Find the probability that at least one marble is red.", 1),
                      ("d", "Given that at least one marble is red, find the probability that both are red.", 2)])
    return Generated(
        text, A_parts(P("a", 1, A_num(rr_)), P("b", 2, A_num(mix)), P("c", 1, A_num(atl)), P("d", 2, A_num(rr_ / atl))), 6, 3,
        [f"(a) \\(P(RR) = \\dfrac{{{R}}}{{{T}}} \\times \\dfrac{{{R - 1}}}{{{T - 1}}} = {L(rr_)}\\).",
         f"(b) \\(P(RB) + P(BR) = 2 \\times \\dfrac{{{R} \\times {B}}}{{{T} \\times {T - 1}}} = {L(mix)}\\).",
         f"(c) \\(P(\\text{{at least one red}}) = 1 - P(BB) = 1 - \\dfrac{{{B}}}{{{T}}} \\times \\dfrac{{{B - 1}}}{{{T - 1}}} = {L(atl)}\\).",
         f"(d) \\(P(RR \\mid \\text{{at least one red}}) = \\dfrac{{P(RR)}}{{P(\\text{{at least one red}})}} = \\dfrac{{{L(rr_)}}}{{{L(atl)}}} = {L(rr_ / atl)}\\)."],
        "Without replacement the probabilities change after the first draw; 'at least one' is easiest by the complement; conditional probability divides by the probability of the given event.",
        "Draw the two-stage tree with all four branches labelled before answering.",
        quicker="Check: \\(P(RR) + P(\\text{one of each}) + P(BB) = 1\\).",
        common_errors=[err(F(R * R, T * T), "conceptual", PROB, "The first marble is not replaced: the second fraction is out of one fewer.", step=1, part="a"),
                       err(F(R * B, T * (T - 1)), "incomplete reasoning", PROB, "One of each can happen in two orders.", step=2, part="b"),
                       err(rr_, "interpretation", PROB, "That is \\(P(RR)\\) itself; divide by the probability of the given event.", step=4, part="d")],
        skill="Tree diagrams without replacement, complements and conditional probability.",
        params={"form": "draws", "R": R, "B": B},
    )
