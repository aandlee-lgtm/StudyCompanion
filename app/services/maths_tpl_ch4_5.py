"""Chapters 4 and 5 — Exponential and logarithmic functions (owner: maths).

Trigonometric calculus is not used here (it comes in chapter 6 of the learning sequence)."""
from __future__ import annotations

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_iv, A_mcq, A_num, A_parts, A_prim, A_set, A_units, Generated, L, P, Rng, S, co, cp, err, k, mcq_options, multipart,
    nonzero, pick, pn, region, x,
)

DIFF = "differentiation rules"
INTG = "integration rules"
STAT = "stationary points"
E = sp.E
ln = sp.log
exp = sp.exp


def ee(a, b=0) -> str:
    """LaTeX for e^{ax + b}."""
    return f"e^{{{L(a * x + b)}}}"


# ======================================================================= 4A ===
def t_4A(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            a, b, c = r.randint(2, 6), nonzero(r, -4, 5), nonzero(r, -3, 4)
            while a + b - c == 0:
                c = nonzero(r, -3, 4)
            res = exp((a + b - c) * x)
            return Generated(
                f"Simplify \\(\\dfrac{{{ee(a)}\\times {ee(b)}}}{{{ee(c)}}}\\), writing your answer as a single power of \\(e\\).",
                A_expr(res), 1, 1,
                [f"Add indices to multiply and subtract to divide: \\(e^{{{a}x {'+' if b > 0 else '-'} {co(abs(b), 'x')} {'-' if c > 0 else '+'} {co(abs(c), 'x')}}} = {L(res)}\\)."],
                "The index laws hold for base \\(e\\): \\(e^m e^n = e^{m+n}\\) and \\(\\frac{e^m}{e^n} = e^{m-n}\\).",
                "Write the combined index before simplifying it.",
                quicker="Collect the indices in one line: numerator indices minus denominator index.",
                common_errors=[err(exp(a * b * x**2 / (c * x)), "conceptual", "index laws", "Multiply powers by adding indices, not multiplying them.", step=1),
                               err(exp((a + b + c) * x), "careless error", "sign error", "Dividing subtracts the index.", step=1)],
                skill="Use the index laws with base e.",
                params={"form": "simp", "a": a, "b": b, "c": c},
            )
        a, kv = pick(r, [2, 3, 4, 5]), pick(r, [2, 3, 5, 6, 7, 10])
        val = ln(kv) / a
        return Generated(
            f"Solve \\(e^{{{a}x}} = {kv}\\), giving the exact value of \\(x\\).",
            A_num(val), 1, 1,
            [f"Take natural logarithms: \\({a}x = \\ln {kv}\\), so \\(x = \\dfrac{{\\ln {kv}}}{{{a}}}\\)."],
            "\\(y = e^x\\) and \\(y = \\ln x\\) are inverse functions, so \\(e^{u} = k\\) exactly when \\(u = \\ln k\\).",
            "Give the exact answer with \\(\\ln\\) unless a decimal is asked for.",
            quicker=f"Check: \\(e^{{{a}x}} = (e^{{x}})^{{{a}}}\\), and \\(e^{{\\ln {kv}}} = {kv}\\).",
            common_errors=[err(ln(sp.Rational(kv, a)), "algebraic", "log laws", f"Take logs first, then divide by {a}: \\(\\ln\\frac{{{kv}}}{{{a}}}\\) is not \\(\\frac{{\\ln {kv}}}{{{a}}}\\).", step=1),
                           err(a * ln(kv), "algebraic", "algebra", f"Divide by \\({a}\\) to isolate \\(x\\).", step=1)],
            skill="Solve a simple exponential equation exactly.",
            params={"form": "solve", "a": a, "k": kv},
        )
    if d == 2:
        p, q = r.sample([1, 2, 3, 4, 5, 6], 2)
        reject = r.random() < 0.4
        if reject:
            b1, c1 = q - p, -p * q   # (e^x - p)(e^x + q) = e^2x + (q - p)e^x - pq
            ans = A_num(ln(p))
            sols = f"\\(e^x = {p}\\) or \\(e^x = -{q}\\). Since \\(e^x > 0\\) for all \\(x\\), reject \\(e^x = -{q}\\): \\(x = \\ln {p}\\)" + (" \\(= 0\\)." if p == 1 else ".")
            ces = [err(p, "incomplete reasoning", "log laws", "That is the value of \\(e^x\\); take logarithms to find \\(x\\).", step=3)]
        else:
            b1, c1 = -(p + q), p * q
            ans = A_set([ln(p), ln(q)])
            sols = f"\\(e^x = {p}\\) or \\(e^x = {q}\\), so \\(x = \\ln {p}\\) or \\(x = \\ln {q}\\)."
            ces = [err(S(p, q), "incomplete reasoning", "log laws", "Those are the values of \\(e^x\\); take logarithms to find \\(x\\).", step=3)]
        quad = f"e^{{2x}} {'+' if b1 > 0 else '-'} {co(abs(b1), 'e^x')} {'+' if c1 > 0 else '-'} {abs(c1)} = 0".replace("+ 0e^x ", "").replace("- 0e^x ", "")
        if b1 == 0:
            quad = f"e^{{2x}} {'+' if c1 > 0 else '-'} {abs(c1)} = 0"
        return Generated(
            f"Solve \\({quad}\\), giving exact answers.",
            ans, 3, 2,
            ["Let \\(u = e^x\\); then \\(e^{2x} = u^2\\).",
             f"\\(u^2 {'+' if b1 > 0 else '-'} {co(abs(b1), 'u')} {'+' if c1 > 0 else '-'} {abs(c1)} = 0\\) factorises as \\((u - {p})(u {'+' if reject else '-'} {q}) = 0\\).".replace(" + 0u", "").replace(" - 0u", ""),
             sols],
            "An equation in \\(e^{2x}\\) and \\(e^x\\) is a quadratic in \\(u = e^x\\); then each solution for \\(u\\) is turned back into \\(x\\).",
            "State the substitution, and check each \\(u\\)-solution against \\(e^x > 0\\).",
            quicker="\\(e^{2x} = (e^x)^2\\) — spot the quadratic before reaching for logarithms.",
            common_errors=ces, skill="Solve an exponential equation that is a quadratic in e^x.",
            params={"form": "quad", "b1": b1, "c1": c1},
        )
    A = pick(r, [1, 2, 3, 4, 5])
    s = pick(r, [1, -1, 2, -2])
    sign = pick(r, [1, -1])
    c = -sign * r.randint(1, 6)
    A = sign * A
    while A + c == 0:
        c = -sign * r.randint(1, 6)
    f = A * exp(s * x) + c
    rng_iv = [(c, None, False, False)] if A > 0 else [(None, c, False, False)]
    xint = ln(sp.Rational(-c, A)) / s
    text = multipart(
        f"Consider the function \\(y = {co(A, 'e^{' + L(s * x) + '}')} {'+' if c > 0 else '-'} {abs(c)}\\).",
        [("a", "Find the \\(y\\)-intercept.", 1), ("b", "Write down the equation of the horizontal asymptote (enter the value of \\(y\\)).", 1),
         ("c", "State the range of the function.", 1), ("d", "Find the exact \\(x\\)-intercept.", 2)])
    steps = [f"(a) At \\(x = 0\\): \\(y = {A}\\times e^0 {'+' if c > 0 else '-'} {abs(c)} = {A + c}\\).",
             f"(b) As \\(x \\to {'-' if s > 0 else ''}\\infty\\), \\(e^{{{L(s * x)}}} \\to 0\\), so \\(y \\to {c}\\): the asymptote is \\(y = {c}\\).",
             f"(c) \\(e^{{{L(s * x)}}} > 0\\), so \\({L(A * exp(s * x))}\\) is always {'positive' if A > 0 else 'negative'}: the range is \\({region(rng_iv, 'y')}\\).",
             f"(d) \\({L(A * exp(s * x))} = {-c}\\), so \\(e^{{{L(s * x)}}} = {L(sp.Rational(-c, A))}\\) and \\({L(s * x)} = \\ln {L(sp.Rational(-c, A))}\\).",
             f"So \\(x = {L(xint)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(A + c)), P("b", 1, A_num(c)), P("c", 1, A_iv(rng_iv, var="y")), P("d", 2, A_num(xint))), 5, 3, steps,
        "\\(y = Ae^{sx} + c\\) is \\(y = e^x\\) stretched, possibly reflected, and shifted by \\(c\\): its asymptote is \\(y = c\\) and the range lies on one side of it.",
        "Sketch the curve with its asymptote dashed before stating the range.",
        quicker="The range is decided by the sign of \\(A\\) alone: \\(e^{sx}\\) takes every positive value.",
        common_errors=[err(A, "incomplete reasoning", "transformations", "Include the vertical shift.", step=1, part="a"),
                       err(region([(None, c, False, False)] if A > 0 else [(c, None, False, False)], "y"), "conceptual", "domain/range",
                           "The curve lies on the other side of its asymptote.", step=3, part="c"),
                       err(region([(c, None, True, False)] if A > 0 else [(None, c, False, True)], "y"), "notation", "domain/range",
                           f"The asymptote value \\(y = {c}\\) is never reached: use a strict inequality.", step=3, part="c"),
                       err(ln(sp.Rational(-c, A)) * s, "algebraic", "log laws", f"Divide \\(\\ln\\) by {s} to isolate \\(x\\).", step=5, part="d")
                       if abs(s) != 1 else err(-xint, "careless error", "sign error", "Sign error isolating \\(x\\).", step=5, part="d")],
        skill="Analyse a transformed exponential graph.",
        params={"form": "parts", "A": A, "s": s, "c": c},
    )


# ======================================================================= 4B ===
def t_4B(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, -2, 5]), nonzero(r, -5, 5), r.randint(-6, 6)
        f = A * exp(a * x + b)
        fp = sp.diff(f, x)
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), 1, 1,
            [f"\\(\\dfrac{{d}}{{dx}}e^{{ax + b}} = ae^{{ax + b}}\\), so \\(\\dfrac{{dy}}{{dx}} = {L(fp)}\\)."],
            "\\(\\frac{d}{dx}e^{f(x)} = f'(x)e^{f(x)}\\) — the chain rule with \\(e^u\\) as the outer function.",
            "Write the rule you are applying, then substitute.",
            quicker="The exponential stays; it is multiplied by the derivative of its index.",
            common_errors=[err(f, "conceptual", "chain rule", "Multiply by the derivative of the index (chain rule).", step=1),
                           err(A * (a * x + b) * exp(a * x + b - 1), "conceptual", DIFF, "The power rule does not apply when the variable is in the index.", step=1)],
            skill="Differentiate e^(ax + b).",
            params={"form": "diff", "f": str(f)},
        )
    if d == 2:
        form = pick(r, ["prod", "quot", "chain"])
        a = nonzero(r, -3, 3)
        if form == "prod":
            m = pick(r, [1, 2, 3])
            f = x**m * exp(a * x)
            lab, steps_ = "product", [f"Product rule with \\(u = {L(x**m)}\\), \\(v = e^{{{L(a * x)}}}\\): \\(u' = {L(sp.diff(x**m, x))}\\), \\(v' = {L(sp.diff(exp(a * x), x))}\\)."]
            wrong = sp.diff(x**m, x) * sp.diff(exp(a * x), x)
            mk = 2
        elif form == "quot":
            f = exp(a * x) / x
            lab, steps_ = "quotient", [f"Quotient rule with \\(u = e^{{{L(a * x)}}}\\), \\(v = x\\): \\(\\dfrac{{vu' - uv'}}{{v^2}}\\)."]
            wrong = (exp(a * x) - x * a * exp(a * x)) / x**2
            mk = 3
        else:
            b = nonzero(r, -5, 5)
            f = exp(x**2 + b * x)
            lab, steps_ = "chain", [f"Chain rule: the index \\({L(x**2 + b * x)}\\) has derivative \\({L(2 * x + b)}\\)."]
            wrong = (x**2 + b * x) * exp(x**2 + b * x - 1)
            mk = 2
        fp = sp.diff(f, x)
        shown = f"\\left({L(2 * x + b)}\\right)e^{{{L(x**2 + b * x)}}}" if form == "chain" else L(sp.factor(fp))
        steps_.append(f"\\(\\dfrac{{dy}}{{dx}} = {shown}\\).")
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), mk, 2, steps_,
            f"Exponentials combine with the {lab} rule exactly like other functions.",
            "Write \\(u\\), \\(v\\), \\(u'\\) and \\(v'\\) first; then factorise the common exponential.",
            quicker="Factor out the exponential at the end — it makes later stationary-point work easy.",
            common_errors=[err(wrong, "formula selection", "product rule" if form == "prod" else ("quotient rule" if form == "quot" else "chain rule"),
                               {"prod": "That is \\(u'v'\\): the product rule is \\(u'v + uv'\\).",
                                "quot": "The quotient rule is \\(\\frac{vu' - uv'}{v^2}\\): the order of the terms in the numerator matters.",
                                "chain": "The power rule does not apply to \\(e^u\\); multiply by the derivative of the index."}[form], step=1)],
            skill=f"Differentiate exponentials with the {lab} rule.",
            checkpoints=[cp(fp, "the derivative", step=2)],
            params={"form": "diff", "f": str(f)},
        )
    p, q = r.sample([-4, -3, -2, -1, 1, 2, 3, 4, 5], 2)
    y = exp(k * x)
    B, C = -(p + q), p * q
    ode = "\\dfrac{d^2y}{dx^2}" + (f" {'+' if B > 0 else '-'} {co(abs(B), '')}\\dfrac{{dy}}{{dx}}" if B else "") + f" {'+' if C > 0 else '-'} {co(abs(C), 'y')} = 0"
    aux = "k^2e^{kx}" + (f" {'+' if B > 0 else '-'} {co(abs(B), 'k')}e^{{kx}}" if B else "") + f" {'+' if C > 0 else '-'} {co(abs(C), 'e^{kx}')} = 0"
    text = multipart(
        "Let \\(y = e^{kx}\\), where \\(k\\) is a constant.",
        [("a", "Find \\(\\dfrac{dy}{dx}\\).", 1), ("b", "Find \\(\\dfrac{d^2y}{dx^2}\\).", 1),
         ("c", f"Find the values of \\(k\\) for which \\({ode}\\).", 3)])
    steps = ["(a) \\(\\dfrac{dy}{dx} = ke^{kx}\\).", "(b) \\(\\dfrac{d^2y}{dx^2} = k^2e^{kx}\\).",
             f"(c) Substitute: \\({aux}\\).",
             f"\\(e^{{kx}}\\) is never zero, so \\({pl_k(p, q)} = 0\\), i.e. \\((k {'-' if p > 0 else '+'} {abs(p)})(k {'-' if q > 0 else '+'} {abs(q)}) = 0\\): \\(k = {p}\\) or \\(k = {q}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(k * y, ("x", "k"))), P("b", 1, A_expr(k**2 * y, ("x", "k"))), P("c", 3, A_set([p, q]))), 5, 3, steps,
        "Each derivative of \\(e^{kx}\\) brings down another factor of \\(k\\); a relation between \\(y\\) and its derivatives then becomes a polynomial equation in \\(k\\).",
        "Divide by \\(e^{kx}\\) only after saying why it is allowed: \\(e^{kx} > 0\\).",
        quicker="Replace \\(y''\\), \\(y'\\), \\(y\\) by \\(k^2\\), \\(k\\), \\(1\\) — the 'auxiliary' quadratic appears at once.",
        common_errors=[err(k * exp(k * x - 1) * x, "conceptual", DIFF, "The power rule does not apply when the variable is in the index.", step=1, part="a"),
                       err(S(-p, -q), "careless error", "sign error", "Sign error when factorising the quadratic in \\(k\\).", step=4, part="c"),
                       err(k * exp(k * x), "careless error", "chain rule", "Differentiate again: another factor of \\(k\\) appears.", step=2, part="b")],
        skill="Differentiate e^(kx) repeatedly and solve for k.",
        params={"form": "parts", "p": p, "q": q},
    )


def pl_k(p, q) -> str:
    return L(sp.expand((k - p) * (k - q)))


# ======================================================================= 4C ===
def t_4C(r: Rng, d: int) -> Generated:
    if d == 1:
        a = nonzero(r, -4, 5)
        A = pick(r, [1, 2, 3])
        f = A * exp(a * x)
        tan = sp.expand(A * a * x + A)
        return Generated(
            f"Find the equation of the tangent to \\(y = {L(f)}\\) at the point where \\(x = 0\\). (Enter the expression for \\(y\\).)",
            A_expr(tan), 2, 1,
            [f"\\(y' = {L(sp.diff(f, x))}\\), so the gradient at \\(x = 0\\) is \\({A * a}\\); the point is \\((0, {A})\\).",
             f"\\(y - {A} = {A * a}(x - 0)\\), so \\(y = {L(tan)}\\)."],
            "The tangent has the curve's gradient at the point of contact: \\(y - y_1 = m(x - x_1)\\).",
            "Find both the point and the gradient before writing the line.",
            quicker="At \\(x = 0\\), \\(e^0 = 1\\): the gradient is just the coefficient brought down.",
            common_errors=[err(A * a * x, "incomplete reasoning", "algebra", f"The tangent passes through \\((0, {A})\\), so its \\(y\\)-intercept is \\({A}\\).", step=2),
                           err(A * x + A, "conceptual", "chain rule", "Differentiate \\(e^{ax}\\) to \\(ae^{ax}\\).", step=1)],
            skill="Find a tangent to an exponential curve.",
            params={"form": "tangent", "A": A, "a": a},
        )
    if d == 2:
        a = pick(r, [1, 2, 3, -1, -2, -3])
        c = r.randint(-2, 2)
        f = (x + c) * exp(a * x)
        xs = sp.Rational(-1, a) - c
        ys = sp.simplify(f.subs(x, xs))
        fp = sp.factor(sp.diff(f, x))
        return Generated(
            f"Find the coordinates of the stationary point of \\(y = {L(f)}\\) (give \\(x, y\\)).",
            A_set([xs, ys], ordered=True), 3, 2,
            [f"Product rule with \\(u = {L(x + c)}\\), \\(v = e^{{{L(a * x)}}}\\): \\(u' = 1\\), \\(v' = {co(a, 'e^{' + L(a * x) + '}')}\\), so \\(y' = {L(fp)}\\).",
             f"\\(e^{{{L(a * x)}}} > 0\\), so \\(y' = 0\\) when \\({L(sp.expand(1 + a * (x + c)))} = 0\\), i.e. \\(x = {L(xs)}\\).",
             f"\\(y = ({L(xs + c)})e^{{{L(a * xs)}}} = {L(ys)}\\)."],
            "Stationary points need \\(y' = 0\\); since \\(e^{u}\\) is never zero, only the other factor can vanish.",
            "Factorise \\(y'\\) with the exponential outside and say that it cannot be zero.",
            quicker=f"For \\((x + c)e^{{ax}}\\) the stationary point is at \\(x = -c - \\frac{{1}}{{a}}\\).",
            common_errors=[err(S(xs, (xs + c) * E), "arithmetic", "index laws", "Evaluate the exponential at the stationary point.", step=3),
                           err(S(-xs, f.subs(x, -xs)), "careless error", "sign error", "Sign error solving \\(y' = 0\\).", step=2)],
            skill="Find a stationary point of a product with an exponential.",
            checkpoints=[cp(fp, "the derivative", step=1)],
            params={"form": "stat", "a": a, "c": c},
        )
    s = pick(r, [1, -1])
    c = r.randint(-2, 3)
    f = s * (x - c) * exp(x)
    fp = sp.factor(sp.diff(f, x))
    xs = c - 1
    ys = f.subs(x, xs)
    nature = "B" if s > 0 else "A"
    tan = sp.expand(s * E**c * (x - c))
    opts = mcq_options("a local maximum", "a local minimum", "a horizontal point of inflection")
    text = multipart(
        f"Let \\(f(x) = {'' if s > 0 else '-'}{'x' if c == 0 else '(' + L(x - c) + ')'}e^{{x}}\\).",
        [("a", "Find \\(f'(x)\\).", 1), ("b", "Find the exact coordinates of the stationary point (give \\(x, y\\)).", 2),
         ("c", "Determine the nature of the stationary point.", 1),
         ("d", f"Find the equation of the tangent at the point where the curve crosses the \\(x\\)-axis. (Enter the expression for \\(y\\).)", 2)])
    f2 = sp.factor(sp.diff(f, x, 2))
    steps = [f"(a) Product rule: \\(f'(x) = {L(fp)}\\).",
             f"(b) \\(e^x > 0\\), so \\(f'(x) = 0\\) when \\(x = {xs}\\); then \\(y = {L(ys)}\\).",
             f"(c) \\(f''(x) = {L(f2)}\\), so \\(f''({xs}) = {L(f2.subs(x, xs))}\\) {'> 0: a local minimum' if s > 0 else '< 0: a local maximum'}.",
             f"(d) The curve meets the \\(x\\)-axis at \\(x = {c}\\), where \\(f'({c}) = {L(fp.subs(x, c))}\\).",
             f"Tangent: \\(y - 0 = {L(fp.subs(x, c))}(x - {pn(c)})\\), i.e. \\(y = {L(tan)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(fp)), P("b", 2, A_set([xs, ys], ordered=True)), P("c", 1, A_mcq(nature, opts)), P("d", 2, A_expr(tan))), 6, 3,
        steps,
        "Stationary points, their nature and tangents all come from \\(f'\\) and \\(f''\\); with \\(e^x\\) the exponential factor never vanishes.",
        "Give exact values (\\(e^{c}\\) not a decimal) and justify the nature with \\(f''\\) or a table of gradients.",
        quicker=f"\\(f'(x) = f(x) + {'' if s > 0 else '-'}e^x\\): differentiating \\((x - c)e^x\\) just adds one \\(e^x\\).",
        common_errors=[err(s * exp(x), "formula selection", "product rule", "Use the product rule: both factors depend on \\(x\\).", step=1, part="a"),
                       err("A" if nature == "B" else "B", "conceptual", STAT, f"\\(f''({xs})\\) is {'positive' if s > 0 else 'negative'}, so the curve is concave {'up' if s > 0 else 'down'} there.", step=3, part="c"),
                       err(S(xs, ys * E), "arithmetic", "index laws", "Recheck the exponential at the stationary point.", step=2, part="b"),
                       err(sp.expand(s * E**c * x), "incomplete reasoning", "algebra", f"The tangent passes through \\(({c}, 0)\\).", step=5, part="d")
                       if c != 0 else err(s * x * E, "arithmetic", "index laws", "\\(e^0 = 1\\).", step=5, part="d")],
        skill="Analyse an exponential curve: stationary point, nature, tangent.",
        checkpoints=[cp(fp, "the derivative", step=1, part="b"), cp(fp, "the derivative", step=1, part="d")],
        params={"form": "parts", "s": s, "c": c},
    )


# ======================================================================= 4D ===
def t_4D(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, 4, 6, 12]), nonzero(r, -4, 4), r.randint(-5, 5)
        integrand = A * exp(a * x + b)
        F = sp.Rational(A, a) * exp(a * x + b)
        return Generated(
            f"Find \\(\\displaystyle\\int {L(integrand)}\\,dx\\).",
            A_prim(F), 1, 1,
            [f"\\(\\displaystyle\\int e^{{ax + b}}\\,dx = \\frac{{1}}{{a}}e^{{ax + b}} + C\\), so the primitive is \\({L(F)} + C\\)."],
            "Reverse the chain rule: \\(\\int e^{ax + b}\\,dx = \\frac{1}{a}e^{ax + b} + C\\).",
            "Check by differentiating: you should get the integrand back exactly.",
            quicker="Integrating \\(e^{ax+b}\\) divides by \\(a\\); differentiating multiplies by \\(a\\).",
            common_errors=[err(A * a * exp(a * x + b), "conceptual", "chain rule", "You multiplied by \\(a\\) (as when differentiating); integrating divides by \\(a\\).", step=1),
                           err(A * exp(a * x + b + 1) / (a * x + b + 1), "conceptual", INTG, "The power rule for integrals does not apply to \\(e^u\\).", step=1)],
            skill="Integrate e^(ax + b).",
            params={"form": "prim", "f": str(integrand)},
        )
    if d == 2:
        if r.random() < 0.5:
            a, m = nonzero(r, -3, 3), pick(r, [1, 2, 3])
            val = (exp(a * m) - 1) / a
            return Generated(
                f"Evaluate \\(\\displaystyle\\int_0^{{{m}}} e^{{{L(a * x)}}}\\,dx\\), giving an exact answer.",
                A_num(val), 2, 2,
                [f"\\(\\displaystyle\\int_0^{{{m}}} e^{{{L(a * x)}}}\\,dx = \\Big[{L(exp(a * x) / a)}\\Big]_0^{{{m}}}\\).",
                 f"\\(= {L(exp(a * m) / a)} - {pn(sp.Rational(1, a))} = {L(sp.simplify(val))}\\)."],
                "Definite integrals of exponentials: find the primitive, then use \\(e^0 = 1\\) at the lower limit.",
                "Remember the lower limit gives \\(e^0 = 1\\), not \\(0\\).",
                quicker="The answer must be positive: \\(e^{ax}\\) is always above the axis.",
                common_errors=[err(exp(a * m) / a, "incomplete reasoning", "limits of integration", "At the lower limit \\(e^0 = 1\\), not \\(0\\).", step=2),
                               err(a * (exp(a * m) - 1), "conceptual", "chain rule", "Divide by the coefficient of \\(x\\), don't multiply.", step=1)],
                skill="Evaluate a definite integral of an exponential exactly.",
                params={"form": "def", "f": str(exp(a * x)), "lo": 0, "hi": m},
            )
        c = nonzero(r, -4, 4)
        integrand = (exp(x) + c) ** 2
        F = exp(2 * x) / 2 + 2 * c * exp(x) + c**2 * x
        return Generated(
            f"Find \\(\\displaystyle\\int \\left(e^x {'+' if c > 0 else '-'} {abs(c)}\\right)^2 dx\\).",
            A_prim(F), 2, 2,
            [f"Expand: \\(\\left(e^x {'+' if c > 0 else '-'} {abs(c)}\\right)^2 = e^{{2x}} {'+' if c > 0 else '-'} {abs(2 * c)}e^x + {c * c}\\).",
             f"\\(\\displaystyle\\int = {L(F)} + C\\)."],
            "Expand first: there is no rule for integrating a square directly.",
            "Remember \\((e^x)^2 = e^{2x}\\), whose primitive is \\(\\frac12 e^{2x}\\).",
            quicker="Check by differentiating each term.",
            common_errors=[err((exp(x) + c) ** 3 / 3, "conceptual", "chain rule", "That reverse chain rule needs the derivative of \\(e^x + c\\) as a factor: expand instead.", step=1),
                           err(exp(2 * x) + 2 * c * exp(x) + c**2 * x, "arithmetic", INTG, "The primitive of \\(e^{2x}\\) is \\(\\frac12e^{2x}\\).", step=2)],
            skill="Expand and integrate an exponential expression.",
            params={"form": "prim", "f": str(integrand)},
        )
    a = pick(r, [1, 2, 3, -1, -2])
    D = sp.diff(x * exp(a * x), x)
    F = x * exp(a * x) / a - exp(a * x) / a**2
    val = sp.simplify(F.subs(x, 1) - F.subs(x, 0))
    text = multipart(
        "",
        [("a", f"Differentiate \\(x e^{{{L(a * x)}}}\\).", 1),
         ("b", f"Hence find \\(\\displaystyle\\int x e^{{{L(a * x)}}}\\,dx\\).", 2),
         ("c", f"Hence evaluate \\(\\displaystyle\\int_0^1 x e^{{{L(a * x)}}}\\,dx\\), giving an exact answer.", 2)])
    steps = [f"(a) Product rule: \\(\\dfrac{{d}}{{dx}}\\big(xe^{{{L(a * x)}}}\\big) = e^{{{L(a * x)}}} {'+' if a > 0 else '-'} {co(abs(a), 'x')}e^{{{L(a * x)}}}\\).",
             f"(b) Integrate both sides: \\(xe^{{{L(a * x)}}} = \\displaystyle\\int e^{{{L(a * x)}}}\\,dx + {co(a, '')}{'' if abs(a) == 1 else ''}\\int xe^{{{L(a * x)}}}\\,dx\\).".replace("+ -", "- "),
             f"So \\({co(a, '')}\\displaystyle\\int xe^{{{L(a * x)}}}\\,dx = xe^{{{L(a * x)}}} - {L(exp(a * x) / a)} + C\\), giving \\(\\displaystyle\\int xe^{{{L(a * x)}}}\\,dx = {L(F)} + C\\).".replace("- -", "+ "),
             f"(c) \\(\\Big[{L(F)}\\Big]_0^1 = {L(sp.simplify(F.subs(x, 1)))} - {pn(sp.simplify(F.subs(x, 0)))} = {L(val)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(D)), P("b", 2, A_prim(F)), P("c", 2, A_num(val))), 5, 3, steps,
        "'Hence' integration: a derivative from one part, read backwards, gives an integral that has no direct rule in this course.",
        "In (b) write the integrated form of (a) in full, then rearrange for the unknown integral.",
        quicker="Check (b) by differentiating: you must get \\(xe^{ax}\\) back exactly.",
        common_errors=[err(a * exp(a * x), "formula selection", "product rule", "Both \\(x\\) and the exponential vary: use the product rule.", step=1, part="a"),
                       err(x * exp(a * x) / a, "incomplete reasoning", INTG, "Subtract the integral of the other term from (a).", step=3, part="b"),
                       err(sp.simplify(F.subs(x, 1)), "incomplete reasoning", "limits of integration", "The lower limit does not give zero here: \\(e^0 = 1\\).", step=4, part="c")],
        skill="Integrate x e^(ax) using a given derivative.",
        checkpoints=[cp(D, "the derivative from (a)", step=1, part="b")],
        params={"form": "parts", "a": a},
    )


# ======================================================================= 4E ===
def t_4E(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b = pick(r, [1, 2, 3, -1, -2]), pick(r, [1, 2, 3])
        area = (exp(a * b) - 1) / a
        return Generated(
            f"Find the exact area of the region bounded by \\(y = e^{{{L(a * x)}}}\\), the \\(x\\)-axis, the \\(y\\)-axis and the line \\(x = {b}\\).",
            A_units(area, "units^2"), 2, 1,
            [f"\\(e^{{{L(a * x)}}} > 0\\), so the area is \\(\\displaystyle\\int_0^{{{b}}} e^{{{L(a * x)}}}\\,dx = \\Big[{L(exp(a * x) / a)}\\Big]_0^{{{b}}}\\).",
             f"\\(= {L(sp.expand(area))}\\) square units."],
            "An exponential curve is always above the \\(x\\)-axis, so the area under it is its definite integral.",
            "Give the exact answer, then a decimal check if you like.",
            quicker="Sanity check: the area lies between the rectangle heights at the two ends times the width.",
            common_errors=[err(exp(a * b) / a, "incomplete reasoning", "limits of integration", "At \\(x = 0\\), \\(e^0 = 1\\), so subtract the lower-limit value.", step=2),
                           err(a * (exp(a * b) - 1), "conceptual", "chain rule", "Divide by the coefficient of \\(x\\).", step=1)],
            skill="Find the area under an exponential curve.",
            params={"form": "area", "f": str(exp(a * x)), "lo": 0, "hi": b},
        )
    if d == 2:
        m = r.randint(2, 6)
        area = m * ln(m) - m + 1
        return Generated(
            f"Find the exact area of the region bounded by the curve \\(y = e^x\\), the line \\(y = {m}\\) and the \\(y\\)-axis.",
            A_units(area, "units^2"), 3, 2,
            [f"The curve meets \\(y = {m}\\) where \\(e^x = {m}\\), i.e. \\(x = \\ln {m}\\).",
             f"On \\([0, \\ln {m}]\\) the line is above the curve: \\(A = \\displaystyle\\int_0^{{\\ln {m}}} ({m} - e^x)\\,dx = \\big[{m}x - e^x\\big]_0^{{\\ln {m}}}\\).",
             f"\\(= ({m}\\ln {m} - {m}) - (0 - 1) = {L(area)}\\) square units."],
            "Area between two graphs: integrate (upper − lower) between their intersections.",
            "Find the limit \\(x = \\ln m\\) first and say which graph is on top.",
            quicker=f"Rectangle \\({m}\\times\\ln {m}\\) minus the area under \\(e^x\\), which is \\({m} - 1\\).",
            common_errors=[err(m - 1, "interpretation", "area below the axis", "That is the area under the curve; the region is between the curve and the line.", step=2),
                           err(m * ln(m) - m, "incomplete reasoning", "limits of integration", "At \\(x = 0\\), \\(e^0 = 1\\): subtract \\((0 - 1)\\).", step=3)],
            skill="Find an area between an exponential curve and a line.",
            params={"form": "line", "m": m},
        )
    m = r.randint(2, 7)
    area = sp.Rational((m - 1) ** 2, 2)
    text = multipart(
        f"The curves \\(y = e^{{2x}}\\) and \\(y = {m}e^x\\) intersect at the point \\(P\\).",
        [("a", "Find the exact \\(x\\)-coordinate of \\(P\\).", 2),
         ("b", "Find the exact area of the region bounded by the two curves and the \\(y\\)-axis.", 3)])
    steps = [f"(a) \\(e^{{2x}} = {m}e^x\\); divide by \\(e^x > 0\\): \\(e^x = {m}\\), so \\(x = \\ln {m}\\).",
             f"(b) At \\(x = 0\\), \\({m}e^0 = {m} > 1 = e^0\\), so \\(y = {m}e^x\\) is the upper curve on \\([0, \\ln {m}]\\).",
             f"\\(A = \\displaystyle\\int_0^{{\\ln {m}}} ({m}e^x - e^{{2x}})\\,dx = \\Big[{m}e^x - \\tfrac12e^{{2x}}\\Big]_0^{{\\ln {m}}}\\).",
             f"\\(= \\big({m * m} - \\tfrac{{{m * m}}}{{2}}\\big) - \\big({m} - \\tfrac12\\big) = {L(area)}\\) square units."]
    return Generated(
        text, A_parts(P("a", 2, A_num(ln(m))), P("b", 3, A_units(area, "units^2"))), 5, 3, steps,
        "Find where the curves meet, decide which is on top, then integrate the difference; \\(e^{\\ln m} = m\\) and \\(e^{2\\ln m} = m^2\\) keep the answer exact.",
        "Test a point (e.g. \\(x = 0\\)) to decide which curve is on top.",
        quicker=f"\\(e^{{2\\ln {m}}} = {m}^2\\): simplify the exponentials before substituting.",
        common_errors=[err(m, "incomplete reasoning", "log laws", "That is the value of \\(e^x\\); take logarithms.", step=1, part="a"),
                       err(-area, "careless error", "sign error", "Subtract the lower curve from the upper one.", step=3, part="b"),
                       err(sp.Rational(m * m, 2) - m, "incomplete reasoning", "limits of integration", "Subtract the value at \\(x = 0\\), which is not zero.", step=4, part="b")],
        skill="Find the area between two exponential curves.",
        checkpoints=[cp(m * exp(x) - exp(2 * x), "the difference upper − lower", step=3, part="b")],
        params={"form": "parts", "m": m},
    )


# ======================================================================= 4F ===
def t_4F(r: Rng, d: int) -> Generated:
    a = pick(r, [2, 3, 5, 10])
    if d == 1:
        if r.random() < 0.5:
            A = pick(r, [1, 2, 3, 4])
            f = A * a**x
            return Generated(
                f"Differentiate \\(y = {co(A, '')}{a}^x\\).",
                A_expr(sp.diff(f, x)), 1, 1,
                [f"\\({a}^x = e^{{x\\ln {a}}}\\), so \\(\\dfrac{{d}}{{dx}}{a}^x = {a}^x\\ln {a}\\); hence \\(\\dfrac{{dy}}{{dx}} = {L(sp.diff(f, x))}\\)."],
                "\\(\\frac{d}{dx}a^x = a^x\\ln a\\), because \\(a^x = e^{x\\ln a}\\).",
                "Write \\(a^x\\) as \\(e^{x\\ln a}\\) if you forget the rule.",
                quicker="Only base \\(e\\) has the factor \\(\\ln e = 1\\); every other base brings down \\(\\ln a\\).",
                common_errors=[err(A * x * a ** (x - 1), "conceptual", DIFF, "The power rule does not apply when the variable is in the index.", step=1),
                               err(f, "formula selection", DIFF, "Only \\(e^x\\) is its own derivative; multiply by \\(\\ln a\\).", step=1)],
                skill="Differentiate a^x.",
                params={"form": "diff", "f": str(f)},
            )
        F = a**x / ln(a)
        return Generated(
            f"Find \\(\\displaystyle\\int {a}^x\\,dx\\).",
            A_prim(F), 1, 1,
            [f"\\(\\displaystyle\\int a^x\\,dx = \\frac{{a^x}}{{\\ln a}} + C\\), so \\(\\displaystyle\\int {a}^x\\,dx = \\frac{{{a}^x}}{{\\ln {a}}} + C\\)."],
            "Since \\(\\frac{d}{dx}a^x = a^x\\ln a\\), the primitive of \\(a^x\\) is \\(\\frac{a^x}{\\ln a}\\).",
            "Check by differentiating.",
            quicker="Integrating divides by \\(\\ln a\\); differentiating multiplies by it.",
            common_errors=[err(a**x * ln(a), "conceptual", INTG, "That is the derivative; integrating divides by \\(\\ln a\\).", step=1),
                           err(a ** (x + 1) / (x + 1), "conceptual", INTG, "The power rule does not apply when the variable is in the index.", step=1)],
            skill="Integrate a^x.",
            params={"form": "prim", "f": str(a**x)},
        )
    if d == 2:
        if r.random() < 0.5:
            b, c = pick(r, [2, 3, -1, -2]), r.randint(-3, 3)
            f = a ** (b * x + c)
            fp = sp.diff(f, x)
            return Generated(
                f"Differentiate \\(y = {a}^{{{L(b * x + c)}}}\\).",
                A_expr(fp), 2, 2,
                [f"Write \\(y = e^{{({L(b * x + c)})\\ln {a}}}\\).",
                 f"Chain rule: \\(\\dfrac{{dy}}{{dx}} = {b}\\ln {a}\\cdot {a}^{{{L(b * x + c)}}}\\)."],
                "Convert to base \\(e\\): \\(a^{u} = e^{u\\ln a}\\), then use the chain rule.",
                "Show the conversion to base \\(e\\) — it justifies the \\(\\ln a\\) factor.",
                quicker="Two factors come down: the derivative of the index, and \\(\\ln a\\).",
                common_errors=[err(a ** (b * x + c) * ln(a), "careless error", "chain rule", f"Also multiply by the derivative of the index, \\({b}\\).", step=2),
                               err(b * a ** (b * x + c), "formula selection", DIFF, "A base other than \\(e\\) brings down \\(\\ln a\\).", step=2)],
                skill="Differentiate a^(bx + c).",
                params={"form": "diff", "f": str(f)},
            )
        val = (a - 1) / ln(a)
        return Generated(
            f"Evaluate \\(\\displaystyle\\int_0^1 {a}^x\\,dx\\), giving an exact answer.",
            A_num(val), 2, 2,
            [f"\\(\\displaystyle\\int_0^1 {a}^x\\,dx = \\Big[\\frac{{{a}^x}}{{\\ln {a}}}\\Big]_0^1\\).",
             f"\\(= \\dfrac{{{a}}}{{\\ln {a}}} - \\dfrac{{1}}{{\\ln {a}}} = \\dfrac{{{a - 1}}}{{\\ln {a}}}\\)."],
            "The primitive of \\(a^x\\) is \\(\\frac{a^x}{\\ln a}\\); at \\(x = 0\\), \\(a^0 = 1\\).",
            "Keep \\(\\ln a\\) exact in the denominator.",
            quicker=f"Decimal check: \\(\\frac{{{a - 1}}}{{\\ln {a}}} \\approx {float(val):.3f}\\), between \\(1\\) and \\({a}\\) as it must be.",
            common_errors=[err(sp.Rational(a, 1) / ln(a), "incomplete reasoning", "limits of integration", "Subtract the value at \\(x = 0\\): \\(a^0 = 1\\).", step=2),
                           err((a - 1) * ln(a), "conceptual", INTG, "Integrating divides by \\(\\ln a\\).", step=1)],
            skill="Evaluate a definite integral of a^x.",
            params={"form": "def", "f": str(a**x), "lo": 0, "hi": 1},
        )
    text = multipart(
        f"Let \\(y = {a}^x\\).",
        [("a", f"Find the exact value of \\(k\\) such that \\({a}^x = e^{{kx}}\\) for all \\(x\\).", 1),
         ("b", "Find \\(\\dfrac{dy}{dx}\\).", 1),
         ("c", "Find the equation of the tangent to the curve at \\(x = 0\\). (Enter the expression for \\(y\\).)", 2),
         ("d", "Find the exact \\(x\\)-intercept of this tangent.", 1)])
    tan = x * ln(a) + 1
    steps = [f"(a) \\({a} = e^{{\\ln {a}}}\\), so \\({a}^x = e^{{x\\ln {a}}}\\): \\(k = \\ln {a}\\).",
             f"(b) \\(\\dfrac{{dy}}{{dx}} = \\ln {a}\\cdot e^{{x\\ln {a}}} = {a}^x\\ln {a}\\).",
             f"(c) At \\(x = 0\\): \\(y = 1\\) and the gradient is \\(\\ln {a}\\). Tangent: \\(y = x\\ln {a} + 1\\).",
             f"(d) \\(0 = x\\ln {a} + 1\\), so \\(x = -\\dfrac{{1}}{{\\ln {a}}}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(ln(a))), P("b", 1, A_expr(a**x * ln(a))), P("c", 2, A_expr(tan)), P("d", 1, A_num(-1 / ln(a)))), 5, 3, steps,
        "Every exponential \\(a^x\\) is \\(e^{kx}\\) with \\(k = \\ln a\\), so its calculus follows from that of \\(e^x\\).",
        "Use exact values (\\(\\ln a\\)) throughout; decimals belong only in a final check.",
        quicker="At \\(x = 0\\) every \\(a^x\\) passes through \\((0, 1)\\) with gradient \\(\\ln a\\).",
        common_errors=[err(a, "conceptual", "log laws", f"\\(e^{{kx}} = (e^k)^x\\), so \\(e^k = {a}\\) and \\(k = \\ln {a}\\).", step=1, part="a"),
                       err(x * a ** (x - 1), "conceptual", DIFF, "The power rule does not apply when the variable is in the index.", step=2, part="b"),
                       err(x * ln(a), "incomplete reasoning", "algebra", "The tangent passes through \\((0, 1)\\).", step=3, part="c"),
                       err(1 / ln(a), "careless error", "sign error", "Sign error solving for the intercept.", step=4, part="d")],
        skill="Convert a^x to base e and use its tangent.",
        params={"form": "parts", "a": a},
    )


# ======================================================================= 5A ===
def t_5A(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            a, b = r.sample([2, 3, 5, 6, 7], 2)
            c = pick(r, [2, 3, 4, 5, 7, 10])
            while c in (a, b):
                c = pick(r, [2, 3, 4, 5, 7, 10])
            val = ln(sp.Rational(a * b, c))
            return Generated(
                f"Write \\(\\ln {a} + \\ln {b} - \\ln {c}\\) as a single logarithm.",
                A_num(val), 1, 1,
                [f"\\(\\ln {a} + \\ln {b} = \\ln {a * b}\\), and subtracting \\(\\ln {c}\\) divides: \\(\\ln {L(sp.Rational(a * b, c))}\\)."],
                "Log laws: \\(\\ln a + \\ln b = \\ln ab\\) and \\(\\ln a - \\ln b = \\ln\\frac{a}{b}\\).",
                "Quote the law at each step.",
                quicker="Plus means multiply, minus means divide.",
                common_errors=[err(ln(a + b - c) if a + b - c > 0 else ln(a * b * c), "conceptual", "log laws",
                                   "\\(\\ln a + \\ln b\\) is \\(\\ln(ab)\\), not \\(\\ln(a + b)\\)." if a + b - c > 0 else "Subtracting a logarithm divides.", step=1)],
                skill="Combine logarithms with the log laws.",
                params={"form": "laws", "a": a, "b": b, "c": c},
            )
        a, b = pick(r, [1, 2, 3, -1, -2]), pick(r, [1, 2, 3, 4])
        A = pick(r, [2, 3, 1])
        sol = exp(sp.Rational(b, A)) - a
        return Generated(
            f"Solve \\({co(A, '')}\\ln(x {'+' if a > 0 else '-'} {abs(a)}) = {b}\\), giving the exact value of \\(x\\).",
            A_num(sol), 1, 1,
            [f"\\(\\ln(x {'+' if a > 0 else '-'} {abs(a)}) = {L(sp.Rational(b, A))}\\), so \\(x {'+' if a > 0 else '-'} {abs(a)} = e^{{{L(sp.Rational(b, A))}}}\\) and \\(x = {L(sol)}\\)."],
            "\\(\\ln u = c\\) exactly when \\(u = e^c\\).",
            "Isolate the logarithm first, then exponentiate both sides.",
            quicker="Check: the bracket must be positive at your answer.",
            common_errors=[err(exp(b) - a, "algebraic", "algebra", f"Divide by \\({A}\\) before exponentiating.", step=1) if A != 1 else
                           err(exp(b) + a, "careless error", "sign error", "Sign error isolating \\(x\\).", step=1),
                           err(ln(b) - a, "conceptual", "log laws", "Undo \\(\\ln\\) with \\(e\\), not with another \\(\\ln\\).", step=1)],
            skill="Solve a logarithmic equation.",
            params={"form": "solve", "a": a, "b": b, "A": A},
        )
    if d == 2:
        rr, a = r.randint(1, 6), r.randint(1, 6)
        c = rr * (rr + a)
        return Generated(
            f"Solve \\(\\ln x + \\ln(x + {a}) = \\ln {c}\\).",
            A_num(rr), 3, 2,
            [f"Combine: \\(\\ln\\big(x(x + {a})\\big) = \\ln {c}\\), so \\(x^2 + {co(a, 'x')} - {c} = 0\\).",
             f"\\((x - {rr})(x + {rr + a}) = 0\\), so \\(x = {rr}\\) or \\(x = {-rr - a}\\).",
             f"\\(\\ln x\\) needs \\(x > 0\\), so reject \\(x = {-rr - a}\\): the solution is \\(x = {rr}\\)."],
            "Use the log laws to reach \\(\\ln A = \\ln B\\), so \\(A = B\\); then check every solution lies in the domain of each logarithm.",
            "Always check solutions in the original equation's domain — this is where marks are lost.",
            quicker=f"Try factor pairs of {c} that differ by {a}.",
            common_errors=[err(-rr - a, "interpretation", "domain/range", "\\(\\ln x\\) is undefined for negative \\(x\\): reject that root.", step=3),
                           err(sp.Rational(c - a, 2) if (c - a) > 0 else c, "conceptual", "log laws", "\\(\\ln x + \\ln(x + a) = \\ln(x(x + a))\\), not \\(\\ln(2x + a)\\).", step=1)],
            skill="Solve a log equation and reject roots outside the domain.",
            params={"form": "eq", "a": a, "c": c},
        )
    h, kk_ = r.randint(-4, 4), nonzero(r, -3, 3)
    f = ln(x - h) + kk_
    xint = h + exp(-kk_)
    xpt = h + exp(2)
    text = multipart(
        f"Consider the function \\(y = \\ln({L(x - h)}) {'+' if kk_ > 0 else '-'} {abs(kk_)}\\).".replace("(x)", "x"),
        [("a", "State the domain of the function.", 1), ("b", "Write down the equation of the vertical asymptote (enter the value of \\(x\\)).", 1),
         ("c", "Find the exact \\(x\\)-intercept.", 2), ("d", f"Find the exact value of \\(x\\) for which \\(y = {kk_ + 2}\\).", 1)])
    steps = [f"(a) The logarithm needs \\({L(x - h)} > 0\\), so the domain is \\(x > {h}\\).",
             f"(b) As \\(x \\to {h}^+\\), \\(y \\to -\\infty\\): the asymptote is \\(x = {h}\\).",
             f"(c) \\(\\ln({L(x - h)}) = {-kk_}\\), so \\({L(x - h)} = e^{{{-kk_}}}\\) and \\(x = {L(xint)}\\).".replace("(x)", "x"),
             f"(d) \\(\\ln({L(x - h)}) = 2\\), so \\(x = {L(xpt)}\\).".replace("(x)", "x")]
    return Generated(
        text, A_parts(P("a", 1, A_iv([(h, None, False, False)])), P("b", 1, A_num(h)), P("c", 2, A_num(xint)), P("d", 1, A_num(xpt))), 5, 3, steps,
        "\\(y = \\ln(x - h) + k\\) is \\(y = \\ln x\\) shifted right \\(h\\) and up \\(k\\): its domain and asymptote move with it.",
        "State the domain first; every later answer must lie inside it.",
        quicker="Undo the transformations in reverse order: subtract \\(k\\), exponentiate, add \\(h\\).",
        common_errors=[err(region([(h, None, True, False)]), "notation", "domain/range", f"\\(\\ln 0\\) is undefined: \\(x = {h}\\) is not in the domain.", step=1, part="a"),
                       err(-h, "careless error", "sign error", f"\\(x - h = 0\\) gives \\(x = h\\).", step=2, part="b") if h != 0 else
                       err(1, "conceptual", "domain/range", "The asymptote is where the logarithm's argument is zero.", step=2, part="b"),
                       err(h + exp(kk_), "careless error", "sign error", "Move the constant across first: \\(\\ln(x - h) = -k\\).", step=3, part="c")],
        skill="Analyse a transformed logarithmic graph.",
        params={"form": "parts", "h": h, "k": kk_},
    )


# ======================================================================= 5B ===
def t_5B(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, 4, -2]), pick(r, [1, 2, 3, 5, -1]), r.randint(-6, 6)
        f = A * ln(a * x + b)
        fp = sp.diff(f, x)
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), 1, 1,
            [f"\\(\\dfrac{{d}}{{dx}}\\ln(f(x)) = \\dfrac{{f'(x)}}{{f(x)}}\\), so \\(\\dfrac{{dy}}{{dx}} = {L(fp)}\\)."],
            "\\(\\frac{d}{dx}\\ln f(x) = \\frac{f'(x)}{f(x)}\\) — the chain rule with \\(\\ln u\\) as the outer function.",
            "Write the rule, then substitute \\(f\\) and \\(f'\\).",
            quicker="Derivative of the inside over the inside.",
            common_errors=[err(A / (a * x + b), "careless error", "chain rule", f"Multiply by the derivative of the inside, \\({a}\\).", step=1)
                           if a != 1 else err(A * ln(x + b) / (x + b), "conceptual", DIFF, "Use \\(\\frac{f'(x)}{f(x)}\\).", step=1),
                           err(sp.Rational(A, a) / x, "conceptual", "log laws", "The derivative of \\(\\ln(ax + b)\\) is \\(\\frac{a}{ax + b}\\).", step=1)],
            skill="Differentiate ln of a linear function.",
            params={"form": "diff", "f": str(f)},
        )
    if d == 2:
        form = pick(r, ["prod", "laws", "quad"])
        if form == "prod":
            m = pick(r, [2, 3, 4])
            f = x**m * ln(x)
            hint = f"Product rule with \\(u = x^{m}\\), \\(v = \\ln x\\)."
            wrong = m * x ** (m - 1) / x
            tag = "product rule"
        elif form == "laws":
            a, b = r.sample([1, 2, 3, 4, 5], 2)
            f = ln((x + a) / (x + b))
            hint = f"Log laws first: \\(y = \\ln(x + {a}) - \\ln(x + {b})\\)."
            wrong = (x + b) / (x + a)
            tag = "log laws"
        else:
            a = r.randint(1, 9)
            f = ln(x**2 + a)
            hint = f"\\(\\dfrac{{f'(x)}}{{f(x)}}\\) with \\(f(x) = x^2 + {a}\\)."
            wrong = 1 / (x**2 + a)
            tag = "chain rule"
        fp = sp.factor(sp.simplify(sp.diff(f, x)))
        return Generated(
            f"Differentiate \\(y = {L(f)}\\).",
            A_expr(fp), 2, 2,
            [hint, f"\\(\\dfrac{{dy}}{{dx}} = {L(fp)}\\)."],
            "Logarithms combine with the product, quotient and chain rules; the log laws often simplify the work first.",
            "Simplify using log laws before differentiating where you can.",
            quicker="Check your answer at one value of \\(x\\) with a numerical derivative on the calculator.",
            common_errors=[err(wrong, "formula selection", tag, {"prod": "That is \\(u'v'\\): use \\(u'v + uv'\\).",
                                                                "laws": "That is the reciprocal of the inside: split with log laws, then differentiate each logarithm.",
                                                                "quad": "Multiply by the derivative of the inside (chain rule)."}[form], step=2)],
            skill="Differentiate logarithmic functions with the standard rules.",
            checkpoints=[cp(fp, "the derivative", step=2)],
            params={"form": "diff", "f": str(f)},
        )
    a, b = r.randint(1, 8), r.randint(1, 4)
    while sp.Rational(a, b) == 1:
        b = r.randint(1, 4)
    f = a * ln(x) - b * x
    fp = sp.diff(f, x)
    xs = sp.Rational(a, b)
    ys = f.subs(x, xs)
    tan = sp.expand((a - b) * (x - 1) - b)
    opts = mcq_options("a local maximum", "a local minimum", "a horizontal point of inflection")
    text = multipart(
        f"Let \\(f(x) = {co(a, '')}\\ln x - {co(b, 'x')}\\), for \\(x > 0\\).",
        [("a", "Find \\(f'(x)\\).", 1), ("b", "Find the exact coordinates of the stationary point (give \\(x, y\\)).", 2),
         ("c", "Determine the nature of the stationary point.", 1), ("d", "Find the equation of the tangent at \\(x = 1\\). (Enter the expression for \\(y\\).)", 2)])
    steps = [f"(a) \\(f'(x) = {L(fp)}\\).",
             f"(b) \\(f'(x) = 0\\) when \\(x = {L(xs)}\\); \\(f({L(xs)}) = {L(ys)}\\).",
             f"(c) \\(f''(x) = -\\dfrac{{{a}}}{{x^2}} < 0\\) for all \\(x\\), so the stationary point is a local maximum.",
             f"(d) \\(f(1) = {-b}\\), \\(f'(1) = {a - b}\\): \\(y + {b} = {pn(a - b)}(x - 1)\\), so \\(y = {L(tan)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(fp)), P("b", 2, A_set([xs, ys], ordered=True)), P("c", 1, A_mcq("A", opts)), P("d", 2, A_expr(tan))), 6, 3, steps,
        "Logarithmic functions are analysed like any other: \\(f' = 0\\) for stationary points, the sign of \\(f''\\) for their nature.",
        "Keep logs exact (\\(\\ln\\frac{a}{b}\\)) and state the domain \\(x > 0\\) when you solve.",
        quicker="\\(f''(x) = -\\frac{a}{x^2}\\) is negative everywhere, so any stationary point must be a maximum.",
        common_errors=[err(a / x, "careless error", DIFF, "Differentiate the linear term too.", step=1, part="a"),
                       err(S(xs, a * ln(xs)), "incomplete reasoning", "algebra", "Include the linear term when finding \\(y\\).", step=2, part="b"),
                       err("B", "conceptual", STAT, "\\(f''(x) < 0\\): the curve is concave down, so it is a maximum.", step=3, part="c"),
                       err(sp.expand((a - b) * x - b), "incomplete reasoning", "algebra", "Use the point \\((1, f(1))\\) in \\(y - y_1 = m(x - x_1)\\).", step=4, part="d")],
        skill="Analyse a curve involving ln x.",
        checkpoints=[cp(fp, "the derivative", step=1, part="b")],
        params={"form": "parts", "a": a, "b": b},
    )


# ======================================================================= 5C ===
def t_5C(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, c = pick(r, [1, 2, 3, 4, 5]), pick(r, [2, 3, 4, 5]), pick(r, [1, 2, 3, 4, 5, 6])
        f = A * ln(a * x)
        g = sp.Rational(A, c)
        return Generated(
            f"Find the gradient of the tangent to \\(y = {L(f)}\\) at the point where \\(x = {c}\\).",
            A_num(g), 1, 1,
            [f"\\(\\ln({a}x) = \\ln {a} + \\ln x\\), so \\(y' = \\dfrac{{{A}}}{{x}}\\); at \\(x = {c}\\) the gradient is \\({L(g)}\\)."],
            "The gradient of the tangent is the derivative at the point; \\(\\frac{d}{dx}\\ln(ax) = \\frac1x\\) for any constant \\(a > 0\\).",
            "Differentiate before substituting.",
            quicker="\\(\\ln(ax)\\) is \\(\\ln x\\) shifted up by \\(\\ln a\\), so it has the same gradient as \\(\\ln x\\).",
            common_errors=[err(sp.Rational(A * a, c), "careless error", "chain rule", "\\(\\frac{d}{dx}\\ln(ax) = \\frac{a}{ax} = \\frac1x\\): the \\(a\\) cancels.", step=1),
                           err(A * ln(a * c), "conceptual", DIFF, "That is the \\(y\\)-value; the gradient is the derivative.", step=1)],
            skill="Find the gradient of a logarithmic curve.",
            params={"form": "grad", "A": A, "a": a, "c": c},
        )
    if d == 2:
        a = pick(r, [2, 3, 4, 5, 6])
        tan = x / a + ln(a) - 1
        return Generated(
            f"Find the equation of the tangent to \\(y = \\ln x\\) at the point where \\(x = {a}\\). (Enter the expression for \\(y\\).)",
            A_expr(tan), 3, 2,
            [f"The point is \\(({a}, \\ln {a})\\) and \\(y' = \\dfrac{{1}}{{x}}\\), so the gradient is \\(\\dfrac{{1}}{{{a}}}\\).",
             f"\\(y - \\ln {a} = \\dfrac{{1}}{{{a}}}(x - {a})\\).",
             f"\\(y = \\dfrac{{x}}{{{a}}} + \\ln {a} - 1\\)."],
            "Tangent: the gradient is the derivative at the point, and the line passes through the point of contact.",
            "Keep \\(\\ln a\\) exact.",
            quicker="Check: your tangent must pass through \\((a, \\ln a)\\).",
            common_errors=[err(x / a + ln(a), "arithmetic", "algebra", f"Expand \\(\\frac{{1}}{{{a}}}(x - {a})\\): the constant is \\(-1\\).", step=3),
                           err(x / a, "incomplete reasoning", "algebra", f"The tangent passes through \\(({a}, \\ln {a})\\).", step=2)],
            skill="Find a tangent to y = ln x.",
            params={"form": "tangent", "a": a},
        )
    c, p = r.randint(-3, 3), pick(r, [2, 3, 4, 5])
    f = ln(x) + c
    tan = x / p + ln(p) + c - 1
    nor = -p * x + p * p + ln(p) + c
    text = multipart(
        f"Let \\(f(x) = \\ln x {'+' if c > 0 else '-'} {abs(c)}\\).".replace(" + 0", "").replace(" - 0", ""),
        [("a", f"Find the gradient of the curve at \\(x = {p}\\).", 1),
         ("b", f"Find the equation of the tangent at \\(x = {p}\\). (Enter the expression for \\(y\\).)", 2),
         ("c", f"Find the equation of the normal at \\(x = {p}\\). (Enter the expression for \\(y\\).)", 2)])
    yp = ln(p) + c
    ypt = f"\\ln {p}" + (f" {'+' if c > 0 else '-'} {abs(c)}" if c else "")
    cst = lambda v: (f" {'+' if v > 0 else '-'} {abs(v)}" if v else "")  # noqa: E731
    steps = [f"(a) \\(f'(x) = \\dfrac1x\\), so \\(f'({p}) = \\dfrac{{1}}{{{p}}}\\). The point is \\(({p},\\ {ypt})\\).",
             f"(b) \\(y - ({ypt}) = \\dfrac{{1}}{{{p}}}(x - {p})\\), so \\(y = \\dfrac{{x}}{{{p}}} + \\ln {p}{cst(c - 1)}\\).",
             f"(c) The normal is perpendicular: gradient \\(-{p}\\). \\(y - ({ypt}) = -{p}(x - {p})\\), so \\(y = -{p}x + \\ln {p}{cst(p * p + c)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(sp.Rational(1, p))), P("b", 2, A_expr(tan)), P("c", 2, A_expr(nor))), 5, 3, steps,
        "Tangent and normal at a point share the point; their gradients are \\(m\\) and \\(-\\frac1m\\).",
        "Write the point with exact log values before forming each line.",
        quicker="The normal's gradient is the negative reciprocal of the tangent's.",
        common_errors=[err(ln(p) + c, "conceptual", DIFF, "That is the \\(y\\)-value; the gradient is \\(f'(x)\\).", step=1, part="a"),
                       err(x / p + ln(p) + c, "arithmetic", "algebra", f"Expand \\(\\frac{{1}}{{{p}}}(x - {p})\\): it contributes \\(-1\\).", step=2, part="b"),
                       err(x / p * -1 + ln(p) + c + 1, "formula selection", "algebra", "The normal's gradient is \\(-\\frac{1}{m}\\), i.e. \\(-" + str(p) + "\\).", step=3, part="c")],
        skill="Find the tangent and normal to a logarithmic curve.",
        params={"form": "parts", "c": c, "p": p},
    )


# ======================================================================= 5D ===
def t_5D(r: Rng, d: int) -> Generated:
    if d == 1:
        A, a, b = pick(r, [1, 2, 3, 5, 6]), pick(r, [1, 2, 3, 4]), nonzero(r, -7, 7)
        while sp.gcd(a, b) != 1 or A == a:
            a, b = pick(r, [1, 2, 3, 4]), nonzero(r, -7, 7)
        integrand = A / (a * x + b)
        F = sp.Rational(A, a) * ln(a * x + b)
        return Generated(
            f"Find \\(\\displaystyle\\int {L(integrand)}\\,dx\\).",
            A_prim(F), 2, 1,
            [f"\\(\\displaystyle\\int \\frac{{1}}{{ax + b}}\\,dx = \\frac{{1}}{{a}}\\ln|ax + b| + C\\).",
             f"So \\(\\displaystyle\\int {L(integrand)}\\,dx = {co(sp.Rational(A, a), '')}\\ln|{L(a * x + b)}| + C\\)."],
            "The primitive of \\(\\frac{1}{ax + b}\\) is \\(\\frac1a\\ln|ax + b|\\): the reverse of \\(\\frac{d}{dx}\\ln(ax + b) = \\frac{a}{ax + b}\\).",
            "Include the absolute value and \\(+C\\).",
            quicker="Differentiate your answer to check the constant factor.",
            common_errors=[err(A * ln(a * x + b), "formula selection", "chain rule", f"Divide by \\(a = {a}\\).", step=1) if a != 1 else
                           err(-A / (x + b) ** 2, "conceptual", INTG, "That is the derivative; integrate to a logarithm.", step=1),
                           err(A * a * ln(a * x + b), "conceptual", "chain rule", "Integrating divides by \\(a\\); it does not multiply.", step=1)],
            skill="Integrate a reciprocal of a linear function.",
            params={"form": "prim", "f": str(integrand)},
        )
    if d == 2:
        if r.random() < 0.5:
            a, m = r.randint(1, 5), r.randint(1, 6)
            val = ln(sp.Rational(m + a, a))
            return Generated(
                f"Evaluate \\(\\displaystyle\\int_0^{{{m}}} \\frac{{1}}{{x + {a}}}\\,dx\\), giving an exact answer.",
                A_num(val), 2, 2,
                [f"\\(\\Big[\\ln(x + {a})\\Big]_0^{{{m}}} = \\ln {m + a} - \\ln {a}\\).", f"\\(= \\ln{L(sp.Rational(m + a, a))}\\)." if a != 1 else f"\\(= \\ln {m + 1}\\)."],
                "\\(\\int \\frac{1}{x + a}dx = \\ln|x + a|\\); a difference of logs is the log of a quotient.",
                "Simplify \\(\\ln A - \\ln B\\) to \\(\\ln\\frac{A}{B}\\) at the end.",
                quicker="Positive integrand, so the answer must be positive.",
                common_errors=[err(ln(m + a), "incomplete reasoning", "limits of integration", f"Subtract the value at the lower limit, \\(\\ln {a}\\).", step=1),
                               err(sp.Rational(1, a) - sp.Rational(1, m + a), "conceptual", INTG, "That treats \\(\\frac{1}{x + a}\\) like \\((x + a)^{-2}\\): the primitive is a logarithm.", step=1)],
                skill="Evaluate a definite integral giving a logarithm.",
                params={"form": "def", "f": str(1 / (x + a)), "lo": 0, "hi": m},
            )
        b, c = nonzero(r, -6, 6), r.randint(1, 9)
        q = x**2 + b * x + c
        F = ln(q)
        return Generated(
            f"Find \\(\\displaystyle\\int \\frac{{{L(2 * x + b)}}}{{{L(q)}}}\\,dx\\).",
            A_prim(F), 2, 2,
            [f"The numerator \\({L(2 * x + b)}\\) is the derivative of the denominator.",
             f"So \\(\\displaystyle\\int \\frac{{f'(x)}}{{f(x)}}\\,dx = \\ln|{L(q)}| + C\\)."],
            "\\(\\int \\frac{f'(x)}{f(x)}\\,dx = \\ln|f(x)| + C\\).",
            "State that the numerator is the derivative of the denominator — that is the recognition being marked.",
            quicker="Differentiate the denominator and compare with the numerator.",
            common_errors=[err(ln(q) * (2 * x + b), "conceptual", "chain rule", "The numerator is used up by the rule; it does not stay in the answer.", step=2),
                           err((x**2 + b * x) / (x**3 / 3 + b * x**2 / 2 + c * x), "conceptual", INTG, "Integrals of quotients are not quotients of integrals.", step=1)],
            skill="Recognise and integrate f'(x)/f(x).",
            params={"form": "prim", "f": str((2 * x + b) / q)},
        )
    a, m = r.randint(1, 9), r.randint(1, 3)
    D = 2 * x / (x**2 + a)
    F = ln(x**2 + a) / 2
    val = ln(sp.Rational(m * m + a, a)) / 2
    text = multipart(
        "",
        [("a", f"Differentiate \\(\\ln\\left(x^2 + {a}\\right)\\).", 1),
         ("b", f"Hence find \\(\\displaystyle\\int \\frac{{x}}{{x^2 + {a}}}\\,dx\\).", 2),
         ("c", f"Hence evaluate \\(\\displaystyle\\int_0^{{{m}}} \\frac{{x}}{{x^2 + {a}}}\\,dx\\), giving an exact answer.", 2)])
    steps = [f"(a) \\(\\dfrac{{d}}{{dx}}\\ln(x^2 + {a}) = \\dfrac{{2x}}{{x^2 + {a}}}\\).",
             f"(b) So \\(\\displaystyle\\int \\frac{{2x}}{{x^2 + {a}}}\\,dx = \\ln(x^2 + {a}) + C\\), and \\(\\displaystyle\\int \\frac{{x}}{{x^2 + {a}}}\\,dx = \\frac12\\ln(x^2 + {a}) + C\\).",
             f"(c) \\(\\tfrac12\\big[\\ln(x^2 + {a})\\big]_0^{{{m}}} = \\tfrac12(\\ln {m * m + a} - \\ln {a}) = {L(val)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(D)), P("b", 2, A_prim(F)), P("c", 2, A_num(val))), 5, 3, steps,
        "A derivative of \\(\\ln f(x)\\) read backwards is an integral of \\(\\frac{f'(x)}{f(x)}\\); constants are adjusted outside the integral.",
        "Write the adjusting factor \\(\\frac12\\) explicitly before integrating.",
        quicker="Since \\(x^2 + a > 0\\), no absolute value is needed.",
        common_errors=[err(1 / (x**2 + a), "careless error", "chain rule", "Multiply by the derivative of the inside, \\(2x\\).", step=1, part="a"),
                       err(ln(x**2 + a), "formula selection", "chain rule", "The numerator is \\(x\\), half of \\(2x\\): include the factor \\(\\frac12\\).", step=2, part="b"),
                       err(ln(m * m + a) / 2, "incomplete reasoning", "limits of integration", f"Subtract the value at \\(x = 0\\), which is \\(\\frac12\\ln {a}\\).", step=3, part="c")
                       if a != 1 else err(ln(m * m + 1), "formula selection", "chain rule", "Include the factor \\(\\frac12\\).", step=3, part="c")],
        skill="Use a log derivative to integrate x/(x² + a).",
        checkpoints=[cp(D, "the derivative from (a)", step=1, part="b")],
        params={"form": "parts", "a": a, "m": m},
    )


# ======================================================================= 5E ===
def t_5E(r: Rng, d: int) -> Generated:
    if d == 1:
        A = pick(r, [1, 2, 3, 4, 5])
        if r.random() < 0.5:
            m = pick(r, [1, 2, 3])
            lo, hi, hi_t, area = 1, exp(m), (f"e^{{{m}}}" if m != 1 else "e"), A * m
        else:
            lo, hi = pick(r, [1, 2, 3]), pick(r, [4, 5, 6, 8])
            hi_t, area = str(hi), A * ln(sp.Rational(hi, lo))
        return Generated(
            f"Find the exact area under the curve \\(y = {L(A / x)}\\) between \\(x = {lo}\\) and \\(x = {hi_t}\\).",
            A_units(area, "units^2"), 2, 1,
            [f"\\(A = \\displaystyle\\int_{{{lo}}}^{{{hi_t}}} {L(A / x)}\\,dx = {co(A, '')}\\big[\\ln x\\big]_{{{lo}}}^{{{hi_t}}}\\).",
             f"\\(= {co(A, '')}(\\ln {hi_t} - \\ln {lo}) = {L(area)}\\) square units."],
            "The area under \\(y = \\frac{k}{x}\\) between \\(a\\) and \\(b\\) (both positive) is \\(k\\ln\\frac{b}{a}\\).",
            "Simplify \\(\\ln e^m = m\\) and \\(\\ln 1 = 0\\).",
            quicker="\\(\\ln\\) turns the ratio of the limits into the area (per unit of \\(k\\)).",
            common_errors=[err(A * (1 / sp.sympify(lo) - 1 / sp.sympify(hi)), "conceptual", INTG, "The primitive of \\(\\frac1x\\) is \\(\\ln x\\), not \\(-\\frac1x\\).", step=1),
                           err(A * ln(hi), "incomplete reasoning", "limits of integration", "Subtract the value at the lower limit.", step=2) if lo != 1 else
                           err(ln(hi), "careless error", INTG, f"Multiply by \\({A}\\).", step=2)],
            skill="Find an area under a hyperbola.",
            params={"form": "area", "f": str(A / x), "lo": lo, "hi": str(hi)},
        )
    if d == 2:
        a, b, c = pick(r, [1, 2, 3, 4, 6]), r.randint(1, 4), r.randint(2, 8)
        area = a * ln(sp.Rational(c + b, b))
        return Generated(
            f"Find the exact area of the region bounded by \\(y = \\dfrac{{{a}}}{{x + {b}}}\\), the \\(x\\)-axis, the \\(y\\)-axis and the line \\(x = {c}\\).",
            A_units(area, "units^2"), 3, 2,
            [f"The curve is above the axis for \\(x > -{b}\\): \\(A = \\displaystyle\\int_0^{{{c}}} \\frac{{{a}}}{{x + {b}}}\\,dx\\).",
             f"\\(= {a}\\big[\\ln(x + {b})\\big]_0^{{{c}}} = {a}(\\ln {c + b} - \\ln {b})\\).".replace("{1}(", "("),
             f"\\(= {L(area)}\\) square units."],
            "Areas under reciprocal curves give logarithms: \\(\\int \\frac{a}{x + b}dx = a\\ln|x + b|\\).",
            "Combine the logs into a single log for the final answer.",
            quicker="Decimal check against a rough sketch: area between \\(c\\times\\frac{a}{c + b}\\) and \\(c\\times\\frac{a}{b}\\).",
            common_errors=[err(a * ln(c + b), "incomplete reasoning", "limits of integration", f"Subtract \\({a}\\ln {b}\\) for the lower limit.", step=2),
                           err(a * (sp.Rational(1, b) - sp.Rational(1, c + b)), "conceptual", INTG, "The primitive is a logarithm.", step=1)],
            skill="Find an area under a translated hyperbola.",
            params={"form": "area", "f": str(a / (x + b)), "lo": 0, "hi": str(c)},
        )
    p, q = pick(r, [(1, 2), (1, 3), (1, 4), (2, 3), (1, 5), (2, 4), (2, 5), (3, 4)])
    kv, s = p * q, p + q
    area = s * (q - p) - sp.Rational(q * q - p * p, 2) - kv * ln(sp.Rational(q, p))
    text = multipart(
        f"The line \\(x + y = {s}\\) meets the curve \\(y = \\dfrac{{{kv}}}{{x}}\\) at two points.",
        [("a", "Find the \\(x\\)-coordinates of the points of intersection.", 2),
         ("b", "Find the exact area of the region enclosed between the line and the curve.", 3)])
    steps = [f"(a) \\({s} - x = \\dfrac{{{kv}}}{{x}}\\), so \\(x^2 - {s}x + {kv} = 0\\), i.e. \\((x - {p})(x - {q}) = 0\\): \\(x = {p}\\) or \\(x = {q}\\).".replace("(x - 1)", "(x - 1)"),
             f"(b) Between them the line is above the curve: \\(A = \\displaystyle\\int_{{{p}}}^{{{q}}} \\Big({s} - x - \\frac{{{kv}}}{{x}}\\Big)dx\\).",
             f"\\(= \\Big[{s}x - \\tfrac12x^2 - {kv}\\ln x\\Big]_{{{p}}}^{{{q}}}\\).",
             f"\\(= {L(area)}\\) square units."]
    return Generated(
        text, A_parts(P("a", 2, A_set([p, q])), P("b", 3, A_units(area, "units^2"))), 5, 3, steps,
        "Enclosed area: find the intersections, then integrate (upper − lower); the hyperbola contributes a logarithm.",
        "Show which graph is on top by testing a point between the intersections.",
        quicker=f"Check (b) numerically: the region fits inside a triangle of area about \\(\\tfrac12({q - p})^2\\).",
        common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error solving the quadratic.", step=1, part="a"),
                       err(-area, "careless error", "sign error", "Integrate upper minus lower.", step=2, part="b"),
                       err(s * (q - p) - sp.Rational(q * q - p * p, 2) - kv * (sp.Rational(1, p) - sp.Rational(1, q)), "conceptual", INTG,
                           "The primitive of \\(\\frac{k}{x}\\) is \\(k\\ln x\\).", step=3, part="b")],
        skill="Find the area enclosed by a line and a hyperbola.",
        checkpoints=[cp(s - x - kv / x, "the difference upper − lower", step=2, part="b")],
        params={"form": "parts", "p": p, "q": q},
    )


# ======================================================================= 5F ===
def t_5F(r: Rng, d: int) -> Generated:
    a = pick(r, [2, 3, 5, 10])
    if d == 1:
        A = pick(r, [1, 2, 3])
        f = A * ln(x) / ln(a)
        return Generated(
            f"Differentiate \\(y = {co(A, '')}\\log_{{{a}}} x\\).",
            A_expr(sp.diff(f, x)), 1, 1,
            [f"Change of base: \\(\\log_{{{a}}} x = \\dfrac{{\\ln x}}{{\\ln {a}}}\\).",
             f"\\(\\dfrac{{dy}}{{dx}} = \\dfrac{{{A}}}{{x\\ln {a}}}\\).".replace("{1}", "1")],
            "\\(\\frac{d}{dx}\\log_a x = \\frac{1}{x\\ln a}\\), from \\(\\log_a x = \\frac{\\ln x}{\\ln a}\\).",
            "Show the change of base — it justifies the \\(\\ln a\\).",
            quicker="\\(\\frac{1}{\\ln a}\\) is just a constant multiplier.",
            common_errors=[err(A / x, "formula selection", "log laws", "Only \\(\\ln x\\) differentiates to \\(\\frac1x\\); convert the base first.", step=1),
                           err(A * ln(a) / x, "algebraic", "log laws", "\\(\\ln a\\) belongs in the denominator.", step=2)],
            skill="Differentiate a logarithm to another base.",
            params={"form": "diff", "f": str(f)},
        )
    if d == 2:
        b = r.randint(1, 9)
        f = ln(x**2 + b) / ln(a)
        fp = sp.diff(f, x)
        return Generated(
            f"Differentiate \\(y = \\log_{{{a}}}\\left(x^2 + {b}\\right)\\).",
            A_expr(fp), 2, 2,
            [f"\\(y = \\dfrac{{\\ln(x^2 + {b})}}{{\\ln {a}}}\\).",
             f"\\(\\dfrac{{dy}}{{dx}} = \\dfrac{{1}}{{\\ln {a}}}\\cdot\\dfrac{{2x}}{{x^2 + {b}}} = \\dfrac{{2x}}{{(x^2 + {b})\\ln {a}}}\\)."],
            "Change to base \\(e\\), then use \\(\\frac{d}{dx}\\ln f(x) = \\frac{f'(x)}{f(x)}\\).",
            "Keep the constant \\(\\frac{1}{\\ln a}\\) outside while differentiating.",
            quicker="Derivative of the inside over (inside × \\(\\ln a\\)).",
            common_errors=[err(2 * x / (x**2 + b), "formula selection", "log laws", "Divide by \\(\\ln a\\) for a base other than \\(e\\).", step=2),
                           err(1 / ((x**2 + b) * ln(a)), "careless error", "chain rule", "Multiply by the derivative of the inside, \\(2x\\).", step=2)],
            skill="Differentiate log_a of a function.",
            checkpoints=[cp(fp, "the derivative", step=2)],
            params={"form": "diff", "f": str(f)},
        )
    c = pick(r, [1, 2, 3, 4, 5])
    tan = x / (a * ln(a)) + 1 - 1 / ln(a)
    text = multipart(
        f"Let \\(y = \\log_{{{a}}} x\\).",
        [("a", f"Express \\(\\log_{{{a}}} x\\) in terms of natural logarithms.", 1),
         ("b", f"Find the exact gradient of the curve at \\(x = {c}\\).", 1),
         ("c", f"Find the equation of the tangent at the point \\(({a}, 1)\\). (Enter the expression for \\(y\\).)", 2)])
    steps = [f"(a) \\(\\log_{{{a}}} x = \\dfrac{{\\ln x}}{{\\ln {a}}}\\).",
             f"(b) \\(\\dfrac{{dy}}{{dx}} = \\dfrac{{1}}{{x\\ln {a}}}\\), so at \\(x = {c}\\) the gradient is \\(\\dfrac{{1}}{{{c}\\ln {a}}}\\).".replace("{1}\\ln", "\\ln"),
             f"(c) At \\(x = {a}\\) the gradient is \\(\\dfrac{{1}}{{{a}\\ln {a}}}\\): \\(y - 1 = \\dfrac{{1}}{{{a}\\ln {a}}}(x - {a})\\).",
             f"So \\(y = \\dfrac{{x}}{{{a}\\ln {a}}} + 1 - \\dfrac{{1}}{{\\ln {a}}}\\)."]
    return Generated(
        text.replace("\\(1\\ln", "\\(\\ln"),
        A_parts(P("a", 1, A_expr(ln(x) / ln(a))), P("b", 1, A_num(1 / (c * ln(a)))), P("c", 2, A_expr(tan))), 4, 3, steps,
        "The change-of-base law \\(\\log_a x = \\frac{\\ln x}{\\ln a}\\) turns every logarithm into a constant multiple of \\(\\ln x\\).",
        "Keep \\(\\ln a\\) exact; don't round the gradient.",
        quicker=f"\\(\\log_{{{a}}} {a} = 1\\), so the point of contact is \\(({a}, 1)\\) without any calculation.",
        common_errors=[err(ln(a) / ln(x), "algebraic", "log laws", "Change of base puts \\(\\ln x\\) on top.", step=1, part="a"),
                       err(sp.Rational(1, c), "formula selection", "log laws", "Divide by \\(\\ln a\\) for a base other than \\(e\\).", step=2, part="b"),
                       err(x / (a * ln(a)) + 1, "arithmetic", "algebra", "Expand the bracket: it contributes \\(-\\frac{1}{\\ln a}\\).", step=4, part="c")],
        skill="Calculus of logarithms to other bases.",
        params={"form": "parts", "a": a, "c": c},
    )
