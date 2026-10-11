"""Chapter 1 — Sequences and series (owner: maths)."""
from __future__ import annotations

import math

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_iv, A_num, A_parts, A_set, Generated, L, P, Rng, co, cp, err, ex, k, lt, multipart, n, nonzero, ordinal, pick, series, sgn, x,
)

SEQ = "sequence formula"
SER = "series formula"


# ----------------------------------------------------------------------- 1A ---
def t_1A(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = r.randint(1, 3), r.randint(-6, 6), r.randint(-9, 9)
        T = a * n**2 + b * n + c
        m = r.randint(5, 12)
        val = T.subs(n, m)
        ces = [err(T.subs(n, m - 1), "interpretation", SEQ, f"You found \\(T_{{{m - 1}}}\\): the term number is {m}.", step=1)]
        if a > 1:
            ces.append(err((a * m) ** 2 + b * m + c, "arithmetic", "index laws", f"You squared \\({a}\\times {m}\\); only \\(n\\) is squared: \\({a}n^2 = {a}\\times {m}^2\\).", step=1))
        return Generated(
            f"A sequence is defined by \\(T_n = {L(T)}\\). Find \\(T_{{{m}}}\\).",
            A_num(val), 1, 1,
            [f"Substitute \\(n = {m}\\): \\(T_{{{m}}} = {(str(a) + ' \\times ') if a != 1 else ''}{m}^2 {sgn(b * m)} {sgn(c)} = {val}\\)."],
            "The formula for \\(T_n\\) gives each term directly from its position \\(n\\).",
            "Show the substitution line: it earns the method mark even if the arithmetic slips.",
            quicker="Square the term number first, then multiply — order of operations is where most slips happen.",
            common_errors=ces, skill="Evaluate a term of a sequence from an explicit formula.",
            params={"form": "explicit", "a": a, "b": b, "c": c, "m": m},
        )
    if d == 2:
        if r.random() < 0.5:
            p, q, s = nonzero(r, -5, 6), pick(r, [2, 3, -2, -1]), nonzero(r, -5, 5)
            m = r.randint(4, 6)
            terms = [p]
            for _ in range(m - 1):
                terms.append(q * terms[-1] + s)
            rule = f"T_{{n+1}} = {L(q * sp.Symbol('T_n'))} {sgn(s)}"
            return Generated(
                f"A sequence is defined recursively by \\(T_1 = {p}\\) and \\({rule}\\). Find \\(T_{{{m}}}\\).",
                A_num(terms[-1]), 2, 2,
                [f"\\(T_{{{i + 2}}} = {q}\\times({terms[i]}) {sgn(s)} = {terms[i + 1]}\\)" for i in range(m - 1)],
                "A recursive formula gives each term from the one before, so the terms must be generated in order.",
                "Set the terms out in a list or table so a slip is easy to find.",
                quicker="Use the calculator's answer memory: type the first term, then repeat 'Ans × q + s'.",
                common_errors=[err(terms[-2], "interpretation", SEQ, f"That is \\(T_{{{m - 1}}}\\): you stopped one term early.", step=m - 1),
                               err(q * terms[-1] + s, "careless error", SEQ, f"That is \\(T_{{{m + 1}}}\\): \\(T_1\\) is given, so only {m - 1} steps are needed.", step=m - 1)],
                skill="Generate terms of a recursively defined sequence.",
                params={"form": "recursive", "p": p, "q": q, "s": s, "m": m, "value": terms[-1]},
            )
        a1, c1 = r.randint(2, 7), r.randint(-10, 10)
        T1 = a1 * n + c1
        m = r.randint(12, 40)
        v = T1.subs(n, m)
        return Generated(
            f"A sequence has \\(T_n = {L(T1)}\\). Which term of the sequence is equal to \\({v}\\)? Give the term number.",
            A_num(m), 2, 2,
            [f"Solve \\({L(T1)} = {v}\\).", f"\\({a1}n = {v - c1}\\), so \\(n = {m}\\): it is the {ordinal(m)} term."],
            "A number is a term of a sequence exactly when solving \\(T_n = \\text{value}\\) gives a positive integer \\(n\\).",
            "Always state the conclusion in words: 'so it is the 23rd term'.",
            quicker=f"Count the steps of {a1} from \\(T_1 = {a1 + c1}\\): \\(({v} - {a1 + c1}) \\div {a1} + 1 = {m}\\).",
            common_errors=[err(v * a1 + c1, "interpretation", SEQ, f"You substituted {v} for \\(n\\); the question gives the term's value, so solve \\(T_n = {v}\\).", step=1),
                           err(sp.Rational(v + c1, a1), "careless error", "sign error", "Sign error when moving the constant across the equals sign.", step=2)],
            skill="Decide which term of a sequence has a given value.",
            params={"form": "which", "a": a1, "c": c1, "v": int(v), "m": m},
        )
    p = r.randint(5, 12)
    T = n**2 - p * n
    m = r.randint(p + 2, p + 7)
    w = r.randint(p + 1, p + 9)
    v = w**2 - p * w
    text = multipart(
        f"A sequence is defined by \\(T_n = {L(T)}\\), for \\(n = 1, 2, 3, \\ldots\\)",
        [("a", f"Find \\(T_{{{m}}}\\).", 1),
         ("b", f"Which term of the sequence is equal to \\({v}\\)?", 2),
         ("c", "How many terms of the sequence are negative?", 2)])
    steps = [f"(a) \\(T_{{{m}}} = {m}^2 - {p}\\times {m} = {m * m - p * m}\\).",
             f"(b) \\(n^2 - {p}n = {v}\\), so \\(n^2 - {p}n - {v} = 0\\), i.e. \\((n - {w})(n {sgn(w - p)}) = 0\\).",
             f"\\(n = {w}\\) or \\(n = {p - w}\\); \\(n\\) must be a positive integer, so it is the {ordinal(w)} term.",
             f"(c) \\(T_n < 0\\) when \\(n(n - {p}) < 0\\), i.e. \\(0 < n < {p}\\).",
             f"So \\(n = 1, 2, \\ldots, {p - 1}\\): there are {p - 1} negative terms (\\(T_{{{p}}} = 0\\) is not negative)."]
    return Generated(
        text,
        A_parts(P("a", 1, A_num(m * m - p * m)), P("b", 2, A_num(w)), P("c", 2, A_num(p - 1))),
        5, 3, steps,
        "Questions about a sequence's terms become equations or inequalities in \\(n\\), where \\(n\\) must be a positive integer.",
        "Reject solutions that are not positive integers and say why; for 'how many' questions list the first and last values of \\(n\\).",
        quicker=f"For (c), \\(T_n = n(n - {p})\\) is negative exactly between its zeros \\(0\\) and \\({p}\\).",
        common_errors=[err(p - w, "interpretation", "domain/range", "That root is not a positive integer, so it is not a term number: reject it.", step=3, part="b"),
                       err(p, "careless error", "inequality direction", f"\\(T_{{{p}}} = 0\\), which is not negative: count only \\(n = 1\\) to \\({p - 1}\\).", step=5, part="c"),
                       err(p - 2, "careless error", SEQ, "You have missed one term: count \\(1, 2, \\ldots\\) up to and including the last negative term.", step=5, part="c")],
        skill="Form and solve equations and inequalities in the term number n.",
        checkpoints=[cp(n**2 - p * n - v, "the quadratic in n for part (b)", step=2, part="b", vars_=("n",))],
        params={"form": "parts", "p": p, "m": m, "w": w, "v": v},
    )


# ----------------------------------------------------------------------- 1B ---
def t_1B(r: Rng, d: int) -> Generated:
    a, dd = r.randint(-15, 20), nonzero(r, -7, 7)
    Tn = sp.expand(a + (n - 1) * dd)
    if d == 1:
        m = r.randint(15, 60)
        terms = ", ".join(str(a + i * dd) for i in range(3))
        val = a + (m - 1) * dd
        return Generated(
            f"Find the {ordinal(m)} term of the arithmetic sequence \\({terms}, \\ldots\\)",
            A_num(val), 2, 1,
            [f"\\(a = {a}\\), \\(d = {a + dd} - ({a}) = {dd}\\).", f"\\(T_n = a + (n-1)d\\), so \\(T_{{{m}}} = {a} + {m - 1}\\times({dd}) = {val}\\)."],
            "In an AP each term is the previous term plus the common difference \\(d\\); \\(T_n = a + (n-1)d\\).",
            "Write \\(a\\) and \\(d\\) explicitly first; most AP errors come from a wrong \\(d\\).",
            quicker=f"Count steps: from term 1 to term {m} is {m - 1} steps of \\(d\\).",
            common_errors=[err(a + m * dd, "formula selection", SEQ, "You used \\(a + nd\\) instead of \\(a + (n-1)d\\): the first term already counts as term 1.", step=2),
                           err(a - (m - 1) * dd, "careless error", "sign error", "Your common difference has the wrong sign: \\(d = T_2 - T_1\\).", step=1)],
            skill="Find a term of an arithmetic sequence.",
            checkpoints=[cp(Tn, "the general term Tₙ", step=2, vars_=("n",))],
            params={"form": "nth", "a": a, "d": dd, "m": m},
        )
    if d == 2:
        p, q = r.randint(3, 8), r.randint(10, 20)
        Tp, Tq = a + (p - 1) * dd, a + (q - 1) * dd
        m = r.randint(25, 50)
        val = a + (m - 1) * dd
        return Generated(
            f"In an arithmetic sequence, \\(T_{{{p}}} = {Tp}\\) and \\(T_{{{q}}} = {Tq}\\). Find \\(T_{{{m}}}\\).",
            A_num(val), 3, 2,
            [f"\\(a + {p - 1}d = {Tp}\\) (1) and \\(a + {q - 1}d = {Tq}\\) (2).",
             f"(2) − (1): \\({q - p}d = {Tq - Tp}\\), so \\(d = {dd}\\).",
             f"Then \\(a = {Tp} - {p - 1}\\times({dd}) = {a}\\).",
             f"\\(T_{{{m}}} = {a} + {m - 1}\\times({dd}) = {val}\\)."],
            "Two terms of an AP give two linear equations in \\(a\\) and \\(d\\); subtracting eliminates \\(a\\).",
            "Label the simultaneous equations (1) and (2) and say which you subtract.",
            quicker=f"From term {q} to term {m} is {m - q} steps: \\(T_{{{m}}} = {Tq} + {m - q}\\times({dd})\\).",
            common_errors=[err(a + m * dd, "formula selection", SEQ, "You used \\(a + nd\\) instead of \\(a + (n-1)d\\).", step=4),
                           err(Tq + (m - q + 1) * dd, "careless error", SEQ, "Off by one step of \\(d\\): count the steps from the known term carefully.", step=4),
                           err(sp.Rational(Tq - Tp, q - p + 1) * (m - 1) + a, "arithmetic", SEQ, f"Between \\(T_{{{p}}}\\) and \\(T_{{{q}}}\\) there are {q - p} differences, not {q - p + 1}.", step=2)],
            skill="Find the first term and common difference of an AP from two terms.",
            checkpoints=[cp(Tn, "the general term Tₙ", step=3, vars_=("n",), marks=2)],
            params={"form": "two_terms", "p": p, "Tp": Tp, "q": q, "Tq": Tq, "m": m},
        )
    # (a) AP condition for x, (b) general term, (c) first term beyond a bound
    while True:
        p, q, s = r.randint(-5, 5), r.randint(-5, 8), r.randint(-6, 6)
        xx = 2 * q - p - s
        dd3 = xx + q - p
        if xx > 0 and dd3 > 1 and xx + p != 0:
            break
    a3 = xx + p
    B = r.choice([200, 300, 500, 1000])
    nn = 1
    while a3 + (nn - 1) * dd3 <= B:
        nn += 1
    T3 = sp.expand(a3 + (n - 1) * dd3)
    e1, e2, e3 = x + p, 2 * x + q, 4 * x + s
    text = multipart(
        f"The first three terms of an arithmetic sequence are \\({L(e1)}\\), \\({L(e2)}\\) and \\({L(e3)}\\).",
        [("a", "Find the value of \\(x\\).", 2), ("b", "Find an expression for \\(T_n\\) in terms of \\(n\\).", 1),
         ("c", f"Find the smallest value of \\(n\\) for which \\(T_n > {B}\\).", 2)])
    steps = [f"(a) Equal differences: \\(({L(e2)}) - ({L(e1)}) = ({L(e3)}) - ({L(e2)})\\).",
             f"\\({L(x + q - p)} = {L(2 * x + s - q)}\\), so \\(x = {xx}\\). The terms are \\({a3}, {a3 + dd3}, {a3 + 2 * dd3}\\).",
             f"(b) \\(a = {a3}\\), \\(d = {dd3}\\): \\(T_n = {a3} + (n - 1)\\times {dd3} = {L(T3)}\\).",
             f"(c) \\({L(T3)} > {B}\\) gives \\(n > {L(sp.Rational(B - a3 + dd3, dd3))}\\).",
             f"The smallest integer is \\(n = {nn}\\) (\\(T_{{{nn}}} = {a3 + (nn - 1) * dd3}\\), while \\(T_{{{nn - 1}}} = {a3 + (nn - 2) * dd3}\\))."]
    return Generated(
        text,
        A_parts(P("a", 2, A_num(xx)), P("b", 1, A_expr(T3, ("n",))), P("c", 2, A_num(nn), prompt="term number n")),
        5, 3, steps,
        "Three expressions are consecutive AP terms exactly when their differences are equal; then \\(T_n = a + (n-1)d\\) and inequalities in \\(n\\) locate terms.",
        "In (c) solve the inequality, then round up to the next whole number and check the terms either side.",
        quicker="For (a) use 'middle term = average of its neighbours': \\(2T_2 = T_1 + T_3\\).",
        common_errors=[err(-xx, "careless error", "sign error", "Sign error when collecting the \\(x\\) terms.", step=2, part="a"),
                       err(nn - 1, "careless error", "inequality direction", "That term is not yet greater than the bound: round \\(n\\) up.", step=5, part="c"),
                       err(sp.expand(a3 + n * dd3), "formula selection", SEQ, "Use \\((n-1)d\\), not \\(nd\\).", step=3, part="b")],
        skill="Use the AP condition, the general term and an inequality in n.",
        checkpoints=[cp(T3, "the general term Tₙ", step=3, part="c", vars_=("n",))],
        params={"form": "parts", "p": p, "q": q, "s": s, "x": xx, "B": B, "n": nn},
    )


# ----------------------------------------------------------------------- 1C ---
def t_1C(r: Rng, d: int) -> Generated:
    if d == 1:
        a = pick(r, [1, 2, 3, 4, 5, -2, -3])
        ratio = pick(r, [2, 3, -2, 4])
        m = r.randint(5, 8)
        terms = ", ".join(L(a * ratio**i) for i in range(3))
        val = a * ratio ** (m - 1)
        ces = [err(a * ratio**m, "formula selection", SEQ, "You used \\(ar^n\\) rather than \\(ar^{n-1}\\).", step=2)]
        if ratio < 0:
            ces.append(err(-val, "careless error", "sign error", "Sign error: a negative ratio raised to an odd power is negative, to an even power positive.", step=2))
        ces.append(err(a + (m - 1) * (a * ratio - a), "formula selection", SEQ, "That treats the sequence as arithmetic; here each term is multiplied by \\(r\\).", step=1))
        return Generated(
            f"Find the {ordinal(m)} term of the geometric sequence \\({terms}, \\ldots\\)",
            A_num(val), 2, 1,
            [f"\\(a = {a}\\), \\(r = \\dfrac{{{a * ratio}}}{{{a}}} = {ratio}\\).", f"\\(T_{{{m}}} = ar^{{{m - 1}}} = {a}\\times\\left({ratio}\\right)^{{{m - 1}}} = {val}\\)."],
            "In a GP each term is the previous term multiplied by the common ratio \\(r\\); \\(T_n = ar^{n-1}\\).",
            "Keep negative ratios in brackets when raising to a power.",
            quicker=f"Multiply on from the last given term: \\(T_{{{m}}} = T_3\\times r^{{{m - 3}}}\\).",
            common_errors=ces, skill="Find a term of a geometric sequence.",
            params={"form": "nth", "a": a, "r": ratio, "m": m},
        )
    if d == 2:
        a = pick(r, [1, 2, 3, 4, -1, -3, 5])
        ratio = pick(r, [2, 3, -2, sp.Rational(1, 2), sp.Rational(-1, 2), sp.Rational(2, 3), -3])
        T2, T5 = a * ratio, a * ratio**4
        T7 = a * ratio**6
        return Generated(
            f"In a geometric sequence, \\(T_2 = {L(T2)}\\) and \\(T_5 = {L(T5)}\\). Find \\(T_7\\).",
            A_num(T7), 3, 2,
            [f"\\(ar = {L(T2)}\\) (1) and \\(ar^4 = {L(T5)}\\) (2).",
             f"(2) ÷ (1): \\(r^3 = {L(T5 / T2)}\\), so \\(r = {L(ratio)}\\) (a cube root has one real value).",
             f"\\(T_7 = T_5\\times r^2 = {L(T5)}\\times {L(ratio**2)} = {L(T7)}\\)."],
            "Dividing two terms of a GP eliminates \\(a\\) and leaves a power of \\(r\\).",
            "Divide the later term by the earlier one, and state the root you take.",
            quicker="From \\(T_5\\) to \\(T_7\\) is two more multiplications by \\(r\\); you never need \\(a\\).",
            common_errors=[err(T5 * ratio**3, "careless error", SEQ, "That is \\(T_8\\): from \\(T_5\\) to \\(T_7\\) multiply by \\(r^2\\), not \\(r^3\\).", step=3),
                           err(T5 * (T5 / T2 / 3) ** 2, "formula selection", "index laws", "\\(r^3 = k\\) means \\(r = \\sqrt[3]{k}\\), not \\(k \\div 3\\).", step=2),
                           err(T5 + 2 * (T5 - T2) / 3, "formula selection", SEQ, "That treats the sequence as arithmetic.", step=1)],
            skill="Find the ratio of a GP from two terms and use it.",
            checkpoints=[cp(a * ratio ** (n - 1), "the general term Tₙ", step=3, vars_=("n",), marks=2)],
            params={"form": "two_terms", "T2": T2, "T5": T5},
        )
    a2, r2 = pick(r, [2, 3, 5, 7]), pick(r, [2, 3])
    bound = pick(r, [1000, 5000, 20000, 100000])
    nn = 1
    while a2 * r2 ** (nn - 1) <= bound:
        nn += 1
    Tn = a2 * r2 ** (n - 1)
    text = multipart(
        f"A geometric sequence has first term \\({a2}\\) and common ratio \\({r2}\\).",
        [("a", "Write an expression for \\(T_n\\).", 1),
         ("b", f"Use logarithms to find the smallest \\(n\\) for which \\(T_n > {bound}\\).", 2),
         ("c", "Find the value of that term.", 1)])
    steps = [f"(a) \\(T_n = ar^{{n-1}} = {a2}\\times {r2}^{{n-1}}\\).",
             f"(b) \\({a2}\\times {r2}^{{n-1}} > {bound}\\), so \\({r2}^{{n-1}} > {L(sp.Rational(bound, a2))}\\).",
             f"\\(n - 1 > \\dfrac{{\\ln {L(sp.Rational(bound, a2))}}}{{\\ln {r2}}} \\approx {math.log(bound / a2) / math.log(r2):.3f}\\), so the smallest integer is \\(n = {nn}\\).",
             f"(c) \\(T_{{{nn}}} = {a2}\\times {r2}^{{{nn - 1}}} = {a2 * r2 ** (nn - 1)}\\) (check: \\(T_{{{nn - 1}}} = {a2 * r2 ** (nn - 2)} \\le {bound}\\))."]
    return Generated(
        text,
        A_parts(P("a", 1, A_expr(Tn, ("n",))), P("b", 2, A_num(nn)), P("c", 1, A_num(a2 * r2 ** (nn - 1)))),
        4, 3, steps,
        "Inequalities involving \\(r^{n-1}\\) are solved by taking logarithms; \\(n\\) must then be rounded up to a whole term number.",
        "Always check the term before and after your answer: it catches off-by-one errors.",
        quicker="Trial on the calculator (multiply by the ratio repeatedly) confirms the log answer in seconds.",
        common_errors=[err(nn - 1, "careless error", "inequality direction", "You rounded down: the term must exceed the bound, so take the next whole number.", step=3, part="b"),
                       err(a2 * r2**n, "formula selection", SEQ, "Use \\(r^{n-1}\\), not \\(r^n\\).", step=1, part="a")],
        skill="Use logarithms to find the first term of a GP beyond a bound.",
        params={"form": "parts", "a": a2, "r": r2, "bound": bound, "n": nn},
    )


# ----------------------------------------------------------------------- 1D ---
def _gp_x(r: Rng):
    while True:
        a = r.randint(1, 6)
        b = r.randint(2 * a + 1, 2 * a + 6)
        if (a * a) % (b - 2 * a) == 0:
            return a, b, (a * a) // (b - 2 * a)


def t_1D(r: Rng, d: int) -> Generated:
    if d == 1:
        p = pick(r, [2, 3, 4, 5])
        q = pick(r, [2, 3, 4, 6, 8])
        m = p * q * q
        gm = p * q
        return Generated(
            f"The numbers \\({p}\\), \\(x\\) and \\({m}\\) are consecutive terms of a geometric sequence, with \\(x > 0\\). Find \\(x\\).",
            A_num(gm), 2, 1,
            [f"In a GP, \\(\\dfrac{{x}}{{{p}}} = \\dfrac{{{m}}}{{x}}\\).", f"\\(x^2 = {p * m}\\), so \\(x = \\pm{gm}\\).", f"Since \\(x > 0\\), \\(x = {gm}\\)."],
            "Three consecutive GP terms satisfy \\(\\frac{T_2}{T_1} = \\frac{T_3}{T_2}\\), i.e. the middle term is the geometric mean.",
            "Use the given restriction (here \\(x>0\\)) explicitly to reject a solution.",
            quicker=f"The geometric mean is \\(\\sqrt{{{p}\\times{m}}}\\).",
            common_errors=[err(sp.Rational(p + m, 2), "formula selection", SEQ, "You used the arithmetic mean \\(\\frac{a+b}{2}\\) (AP condition), not the geometric mean.", step=1),
                           err(-gm, "interpretation", "domain/range", "The question says \\(x > 0\\).", step=3)],
            skill="Use the GP condition (geometric mean).",
            params={"form": "gm", "p": p, "m": m},
        )
    if d == 2:
        if r.random() < 0.5:
            kk = r.randint(2, 6)
            c = r.randint(1, 4)
            # x, x + kk, (c+1)x - kk ... AP condition: 2(x+kk) = x + (c+1)x - kk  =>  c x = 3kk
            xx = sp.Rational(3 * kk, c)
            third = (c + 1) * x - kk
            return Generated(
                f"The numbers \\(x\\), \\(x + {kk}\\) and \\({L(third)}\\) are consecutive terms of an arithmetic sequence. Find \\(x\\).",
                A_num(xx), 2, 2,
                [f"In an AP, \\(T_2 - T_1 = T_3 - T_2\\): \\((x + {kk}) - x = ({L(third)}) - (x + {kk})\\).", f"\\({kk} = {L(c * x - 2 * kk)}\\), so \\(x = {L(xx)}\\)."],
                "Consecutive AP terms have equal differences, so the middle term is the average of its neighbours.",
                "Write the equal-differences equation before simplifying.",
                quicker="Middle term = average of neighbours: \\(2T_2 = T_1 + T_3\\).",
                common_errors=[err(sp.Rational(kk, c), "algebraic", "algebra", "Expand \\(-(x + k)\\) fully: both terms change sign.", step=2),
                               err(-xx, "careless error", "sign error", "Sign error when collecting terms.", step=2)],
                skill="Use the AP condition to find an unknown.",
                params={"form": "ap", "k": kk, "c": c},
            )
        a, b, xx = _gp_x(r)
        rr = sp.Rational(xx + a, xx)
        return Generated(
            f"The numbers \\(x\\), \\(x + {a}\\) and \\(x + {b}\\) are consecutive terms of a geometric sequence. Find \\(x\\).",
            A_num(xx), 2, 2,
            [f"GP condition: \\((x + {a})^2 = x(x + {b})\\).", f"\\(x^2 + {2 * a}x + {a * a} = x^2 + {b}x\\), so \\({co(b - 2 * a, "x")} = {a * a}\\) and \\(x = {xx}\\).",
             f"Check: \\({xx}, {xx + a}, {xx + b}\\) has ratio \\({L(rr)}\\)."],
            "For a GP the middle term squared equals the product of its neighbours.",
            "Expand carefully: the \\(x^2\\) terms cancel, leaving a linear equation.",
            quicker="Check your answer by computing both ratios \\(T_2/T_1\\) and \\(T_3/T_2\\).",
            common_errors=[err(sp.Rational(b, 2) - a, "formula selection", SEQ, "That uses the AP condition; the terms are geometric.", step=1),
                           err(sp.Rational(a * a, b), "algebraic", "algebra", "\\((x + a)^2 = x^2 + 2ax + a^2\\): the middle term \\(2ax\\) is missing.", step=2)],
            skill="Use the GP condition to find an unknown.",
            params={"form": "gp", "a": a, "b": b},
        )
    a, b, xx = _gp_x(r)
    rr = sp.Rational(xx + a, xx)
    bound = pick(r, [1000, 2000, 5000, 10000])
    nn = 1
    while xx * rr ** (nn - 1) <= bound:
        nn += 1
    text = multipart(
        f"The numbers \\(x\\), \\(x + {a}\\) and \\(x + {b}\\) are the first three terms of a geometric sequence.",
        [("a", "Find the value of \\(x\\).", 2), ("b", "Find the common ratio.", 1),
         ("c", f"Which term is the first to exceed \\({bound}\\)? Give its term number.", 2)])
    steps = [f"(a) \\((x + {a})^2 = x(x + {b})\\) gives \\({co(b - 2 * a, "x")} = {a * a}\\), so \\(x = {xx}\\).",
             f"(b) \\(r = \\dfrac{{{xx + a}}}{{{xx}}} = {L(rr)}\\).",
             f"(c) \\({xx}\\left({L(rr)}\\right)^{{n-1}} > {bound}\\), so \\(n - 1 > \\dfrac{{\\ln({L(sp.Rational(bound, xx))})}}{{\\ln({L(rr)})}} \\approx {math.log(bound / xx) / math.log(float(rr)):.3f}\\).",
             f"So \\(n = {nn}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_num(xx)), P("b", 1, A_num(rr)), P("c", 2, A_num(nn))), 5, 3, steps,
        "The GP condition \\(T_2^2 = T_1T_3\\) finds the unknown; logarithms then locate terms.",
        "Carry the exact ratio (a fraction) into the logarithm step, and round \\(n\\) up.",
        quicker=f"(c) can be checked on the calculator by repeatedly multiplying by \\({L(rr)}\\).",
        common_errors=[err(sp.Rational(b, 2) - a, "formula selection", SEQ, "That uses the AP condition; the terms are geometric.", step=1, part="a"),
                       err(nn - 1, "careless error", "inequality direction", "Round \\(n\\) up: that term does not yet exceed the bound.", step=4, part="c"),
                       err(1 / rr, "careless error", SEQ, "The ratio is a later term divided by the earlier term.", step=2, part="b")],
        skill="Combine the GP condition with logarithms.",
        params={"form": "parts", "a": a, "b": b, "bound": bound},
    )


# ----------------------------------------------------------------------- 1E ---
def t_1E(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b = r.randint(1, 6), nonzero(r, -5, 8)
        N = r.randint(4, 6)
        vals = [a * i + b for i in range(1, N + 1)]
        s = sum(vals)
        body = L(a * k + b)
        return Generated(
            f"Evaluate \\(\\displaystyle\\sum_{{k=1}}^{{{N}}} \\left({body}\\right)\\).",
            A_num(s), 1, 1,
            [f"Substitute \\(k = 1, 2, \\ldots, {N}\\): \\({' + '.join(f'({v})' for v in vals)}\\).", f"Sum \\(= {s}\\)."],
            "Sigma notation lists the terms obtained by substituting each integer value of the index, then adds them.",
            "Write out every term before adding — it is quick and safe for a small number of terms.",
            quicker=f"The terms form an AP: \\(\\frac{{{N}}}{{2}}(\\text{{first}} + \\text{{last}}) = \\frac{{{N}}}{{2}}({vals[0]} + {vals[-1]})\\).",
            common_errors=[err(s - vals[-1], "careless error", SER, "You stopped one term early: the upper limit is included.", step=1),
                           err(s + a * (N + 1) + b, "careless error", SER, "You included one term too many.", step=1)],
            skill="Evaluate a sum written in sigma notation.",
            params={"form": "sigma", "a": a, "b": b, "N": N},
        )
    if d == 2:
        if r.random() < 0.5:
            lo = r.randint(2, 6)
            cnt = r.randint(4, 6)
            s2 = sum(2**i for i in range(lo, lo + cnt))
            return Generated(
                f"Evaluate \\(\\displaystyle\\sum_{{k={lo}}}^{{{lo + cnt - 1}}} 2^k\\).",
                A_num(s2), 2, 2,
                [f"Write out the terms: \\({' + '.join(str(2**i) for i in range(lo, lo + cnt))}\\).", f"Sum \\(= {s2}\\)."],
                "Sigma notation lists the terms obtained by substituting each integer value of the index.",
                "Count the terms: from \\(k=a\\) to \\(k=b\\) there are \\(b-a+1\\) terms.",
                quicker=f"It is a GP with first term \\(2^{{{lo}}}\\), ratio 2 and {cnt} terms: \\(2^{{{lo}}}(2^{{{cnt}}}-1)\\).",
                common_errors=[err(s2 - 2 ** (lo + cnt - 1), "careless error", SER, "You stopped one term early: the upper limit is included.", step=1),
                               err(s2 + 2 ** (lo + cnt), "careless error", SER, "You added one term too many.", step=1),
                               err(sum(2**i for i in range(1, cnt + 1)), "interpretation", SER, f"The sum starts at \\(k = {lo}\\), not \\(k = 1\\).", step=1)],
                skill="Evaluate a sum written in sigma notation.",
                params={"form": "pow2", "lo": lo, "cnt": cnt},
            )
        pp, qq = r.randint(1, 5), r.randint(-6, 6)
        S = pp * n**2 + qq * n
        m = r.randint(5, 15)
        Tm = pp * (2 * m - 1) + qq
        return Generated(
            f"The sum of the first \\(n\\) terms of a sequence is \\(S_n = {L(S)}\\). Find \\(T_{{{m}}}\\).",
            A_num(Tm), 2, 2,
            [f"\\(T_{{{m}}} = S_{{{m}}} - S_{{{m - 1}}}\\).", f"\\(= ({S.subs(n, m)}) - ({S.subs(n, m - 1)}) = {Tm}\\)."],
            "Each partial sum adds one more term, so \\(T_n = S_n - S_{n-1}\\).",
            "Write \\(T_n = S_n - S_{n-1}\\) first — markers look for it.",
            quicker=f"Find \\(T_n\\) in general: \\(T_n = S_n - S_{{n-1}} = {L(sp.expand(S - S.subs(n, n - 1)))}\\), then substitute.",
            common_errors=[err(S.subs(n, m), "interpretation", SER, "That is \\(S_{m}\\), the sum of the first terms, not the term itself.", step=1),
                           err(S.subs(n, m) - S.subs(n, m + 1), "careless error", "sign error", "Subtract the other way: \\(T_n = S_n - S_{n-1}\\).", step=2)],
            skill="Recover a term from the partial sums.",
            params={"form": "SnTn", "p": pp, "q": qq, "m": m},
        )
    pp, qq = r.randint(1, 5), r.randint(-6, 8)
    S = pp * n**2 + qq * n
    Tn = sp.expand(S - S.subs(n, n - 1))
    w = r.randint(8, 25)
    v = Tn.subs(n, w)
    text = multipart(
        f"The sum of the first \\(n\\) terms of a sequence is given by \\(S_n = {L(S)}\\).",
        [("a", "Find the first term \\(T_1\\).", 1), ("b", "Find an expression for \\(T_n\\) in terms of \\(n\\).", 2),
         ("c", f"Which term of the sequence equals \\({v}\\)?", 1)])
    steps = [f"(a) \\(T_1 = S_1 = {S.subs(n, 1)}\\).",
             f"(b) \\(T_n = S_n - S_{{n-1}} = {L(S)} - \\left({L(S.subs(n, n - 1))}\\right)\\).",
             f"\\(= {L(Tn)}\\) (check: \\(n = 1\\) gives \\({Tn.subs(n, 1)}\\)).",
             f"(c) \\({L(Tn)} = {v}\\) gives \\(n = {w}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(S.subs(n, 1))), P("b", 2, A_expr(Tn, ("n",))), P("c", 1, A_num(w))), 4, 3, steps,
        "Partial sums determine the terms: \\(T_1 = S_1\\) and \\(T_n = S_n - S_{n-1}\\) for \\(n \\ge 2\\).",
        "Use brackets when substituting \\(n - 1\\) — the expansion is where the marks are lost.",
        quicker="(b) is linear because \\(S_n\\) is quadratic: find \\(T_1\\) and \\(T_2 = S_2 - S_1\\), then the AP formula.",
        common_errors=[err(S, "interpretation", SER, "That is \\(S_n\\); the term is \\(S_n - S_{n-1}\\).", step=2, part="b"),
                       err(sp.expand(S - (pp * n**2 - qq * n)), "algebraic", "algebra", "Substitute \\(n-1\\) for every \\(n\\), with brackets.", step=2, part="b")],
        skill="Use the relationship between partial sums and terms.",
        checkpoints=[cp(S.subs(n, n - 1), "S₍ₙ₋₁₎ written correctly", step=2, part="b", vars_=("n",))],
        params={"form": "parts", "p": pp, "q": qq, "w": w},
    )


# ----------------------------------------------------------------------- 1F ---
def t_1F(r: Rng, d: int) -> Generated:
    a, dd = r.randint(1, 12), r.randint(2, 7)
    if d == 1:
        N = r.randint(15, 40)
        S = sp.Rational(N, 2) * (2 * a + (N - 1) * dd)
        return Generated(
            f"Find the sum of the first {N} terms of the arithmetic series \\({a} + {a + dd} + {a + 2 * dd} + \\cdots\\)",
            A_num(S), 2, 1,
            [f"\\(a = {a}\\), \\(d = {dd}\\), \\(n = {N}\\).", f"\\(S_n = \\dfrac{{n}}{{2}}\\left(2a + (n-1)d\\right) = \\dfrac{{{N}}}{{2}}\\left({2 * a} + {N - 1}\\times {dd}\\right) = {S}\\)."],
            "\\(S_n = \\frac{n}{2}(2a + (n-1)d)\\), or \\(\\frac{n}{2}(a + \\ell)\\) when the last term is known.",
            "Quote the formula, then substitute: the substitution line is usually worth a mark.",
            quicker=f"Find the last term \\(\\ell = {a + (N - 1) * dd}\\) and use \\(\\frac{{n}}{{2}}(a + \\ell)\\).",
            common_errors=[err(sp.Rational(N, 2) * (2 * a + N * dd), "formula selection", SER, "You used \\(nd\\) instead of \\((n-1)d\\) inside the formula.", step=2),
                           err(a + (N - 1) * dd, "interpretation", SER, "That is the last term, not the sum.", step=2),
                           err(N * (2 * a + (N - 1) * dd), "formula selection", SER, "You forgot to halve: \\(S_n = \\frac{n}{2}(\\ldots)\\).", step=2)],
            skill="Sum an arithmetic series.",
            params={"form": "Sn", "a": a, "d": dd, "N": N},
        )
    if d == 2:
        N = r.randint(8, 25)
        S = sp.Rational(N, 2) * (2 * a + (N - 1) * dd)
        quad = dd * n**2 + (2 * a - dd) * n - 2 * S
        return Generated(
            f"How many terms of the arithmetic series \\({a} + {a + dd} + {a + 2 * dd} + \\cdots\\) must be added to give a sum of \\({S}\\)?",
            A_num(N), 3, 2,
            [f"\\(\\dfrac{{n}}{{2}}\\left({2 * a} + (n-1)\\times{dd}\\right) = {S}\\)",
             f"\\({L(quad)} = 0\\)",
             f"Solving gives \\(n = {N}\\); the other root is negative, so it is rejected."],
            "Unknown \\(n\\) in \\(S_n\\) gives a quadratic; only positive integer solutions are valid.",
            "State why the second root is rejected: markers look for it.",
            quicker="Factorise using the fact that one root must be a positive integer, or use the quadratic formula on the calculator.",
            common_errors=[err(N - 1, "careless error", SER, "Check by substituting back: your value of \\(n\\) does not give the sum.", step=3)],
            skill="Find the number of terms of an AP from its sum.",
            checkpoints=[cp(quad, "the quadratic in n", step=2, vars_=("n",), marks=2)],
            params={"form": "findn", "a": a, "d": dd, "S": int(S)},
        )
    kk = pick(r, [3, 4, 6, 7, 9, 11])
    A = r.randint(20, 120)
    B = A + r.randint(150, 400)
    first = -(-A // kk) * kk
    last = (B // kk) * kk
    cnt = (last - first) // kk + 1
    Sm = cnt * (first + last) // 2
    total = (A + B) * (B - A + 1) // 2
    text = multipart(
        f"Consider the whole numbers from \\({A}\\) to \\({B}\\) inclusive.",
        [("a", f"How many of them are multiples of \\({kk}\\)?", 1),
         ("b", f"Find the sum of these multiples of \\({kk}\\).", 2),
         ("c", f"Find the sum of the whole numbers from \\({A}\\) to \\({B}\\) that are not multiples of \\({kk}\\).", 2)])
    steps = [f"(a) The multiples run \\({first}, {first + kk}, \\ldots, {last}\\): an AP with \\(a = {first}\\), \\(d = {kk}\\).",
             f"\\({last} = {first} + (n - 1)\\times {kk}\\) gives \\(n = {cnt}\\).",
             f"(b) \\(S = \\dfrac{{{cnt}}}{{2}}({first} + {last}) = {Sm}\\).",
             f"(c) All the numbers: \\(\\dfrac{{{B - A + 1}}}{{2}}({A} + {B}) = {total}\\).",
             f"Not multiples: \\({total} - {Sm} = {total - Sm}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(cnt)), P("b", 2, A_num(Sm)), P("c", 2, A_num(total - Sm))), 5, 3, steps,
        "Multiples of a number in a range form an AP; 'not multiples' is the total minus that AP's sum.",
        "Find the first and last multiples in the range by division before using any formula.",
        quicker="For (c), subtracting from the total is much faster than summing the non-multiples directly.",
        common_errors=[err(cnt - 1, "careless error", SER, "Off by one: count both the first and last multiple.", step=2, part="a"),
                       err(cnt + 1, "careless error", SER, "Off by one: check your first and last multiples are inside the range.", step=2, part="a"),
                       err(sp.Rational((B - A) * (A + B), 2) - Sm, "careless error", SER, f"There are {B - A + 1} numbers from {A} to {B} inclusive, not {B - A}.", step=4, part="c")],
        skill="Model a counting problem with an arithmetic series.",
        params={"form": "parts", "k": kk, "A": A, "B": B},
    )


# ----------------------------------------------------------------------- 1G ---
def t_1G(r: Rng, d: int) -> Generated:
    if d == 1:
        a = pick(r, [1, 2, 3, 5])
        ratio = pick(r, [2, 3, -2, 4])
        N = r.randint(5, 9)
        S = sp.nsimplify(a * (sp.Integer(ratio)**N - 1) / (ratio - 1))
        return Generated(
            f"Find the sum of the first {N} terms of the geometric series \\({series([a, a * ratio, a * ratio**2])} + \\cdots\\)",
            A_num(S), 2, 1,
            [f"\\(a = {a}\\), \\(r = {ratio}\\), \\(n = {N}\\).", f"\\(S_n = \\dfrac{{a(r^n - 1)}}{{r - 1}} = \\dfrac{{{a}\\left(({ratio})^{{{N}}} - 1\\right)}}{{{ratio} - 1}} = {L(S)}\\)."],
            "\\(S_n = \\frac{a(r^n-1)}{r-1}\\) (convenient for \\(r>1\\)) or \\(\\frac{a(1-r^n)}{1-r}\\) (for \\(|r|<1\\)): they are the same formula.",
            "Choose the form that keeps the denominator positive to reduce sign errors.",
            quicker="For a handful of terms, writing them out and adding is a quick check.",
            common_errors=[err(sp.nsimplify(a * (sp.Integer(ratio) ** (N - 1) - 1) / (ratio - 1)), "formula selection", SER, "You used \\(r^{n-1}\\) in the sum formula; the sum uses \\(r^n\\).", step=2),
                           err(a * ratio ** (N - 1), "interpretation", SER, "That is the last term, not the sum.", step=2)],
            skill="Sum a geometric series.",
            params={"form": "Sn", "a": a, "r": ratio, "N": N},
        )
    if d == 2:
        if r.random() < 0.5:
            a = pick(r, [2, 3, 4, 6, 8])
            ratio = pick(r, [sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(-1, 2), sp.Rational(2, 3)])
            N = r.randint(5, 8)
            S = sp.nsimplify(a * (1 - ratio**N) / (1 - ratio))
            return Generated(
                f"Find the exact sum of the first {N} terms of the geometric series \\({series([a, a * ratio, a * ratio**2])} + \\cdots\\)",
                A_num(S), 2, 2,
                [f"\\(a = {a}\\), \\(r = {L(ratio)}\\), \\(n = {N}\\).", f"\\(S_n = \\dfrac{{a(1 - r^n)}}{{1 - r}} = \\dfrac{{{a}\\left(1 - \\left({L(ratio)}\\right)^{{{N}}}\\right)}}{{1 - \\left({L(ratio)}\\right)}} = {L(S)}\\)."],
                "For \\(|r| < 1\\) the form \\(\\frac{a(1-r^n)}{1-r}\\) keeps both numerator and denominator positive.",
                "Keep the answer as an exact fraction — no decimals.",
                quicker="Compare with the limiting sum \\(\\frac{a}{1-r}\\): the partial sum must be a little less (for \\(r > 0\\)).",
                common_errors=[err(sp.nsimplify(a * (1 - ratio ** (N - 1)) / (1 - ratio)), "formula selection", SER, "The sum formula uses \\(r^n\\), not \\(r^{n-1}\\).", step=2),
                               err(sp.nsimplify(a / (1 - ratio)), "interpretation", SER, "That is the limiting sum; the question asks for a fixed number of terms.", step=2)],
                skill="Sum a geometric series with a fractional ratio.",
                params={"form": "Sn", "a": a, "r": ratio, "N": N},
            )
        a = pick(r, [1, 2, 3, 5])
        ratio = pick(r, [2, 3])
        N = r.randint(6, 12)
        S = a * (ratio**N - 1) // (ratio - 1)
        return Generated(
            f"The geometric series \\({a} + {a * ratio} + {a * ratio**2} + \\cdots\\) has a sum of \\({S}\\). How many terms have been added?",
            A_num(N), 3, 2,
            [f"\\(\\dfrac{{{a}({ratio}^n - 1)}}{{{ratio} - 1}} = {S}\\)", f"\\({ratio}^n - 1 = {S * (ratio - 1) // a}\\), so \\({ratio}^n = {ratio**N}\\).",
             f"\\(n = {N}\\) (by inspection or \\(n = \\frac{{\\ln {ratio**N}}}{{\\ln {ratio}}}\\))."],
            "Making \\(r^n\\) the subject of the sum formula turns the problem into an index equation.",
            "Rearrange to \\(r^n = \\ldots\\) before taking logarithms.",
            quicker=f"Powers of {ratio} are quick to list: find which power equals \\({ratio**N}\\).",
            common_errors=[err(N - 1, "careless error", SER, "Off by one: substitute back to check the sum.", step=3),
                           err(N + 1, "formula selection", SER, "Check the formula: \\(S_n\\) uses \\(r^n\\), not \\(r^{n-1}\\).", step=1)],
            skill="Find the number of terms of a GP from its sum.",
            checkpoints=[cp(ratio**N, f"rⁿ = {ratio**N}", step=2, marks=2)] if ratio**N > 10 else [],
            params={"form": "findn", "a": a, "r": ratio, "S": S},
        )
    a = pick(r, [2, 3, 5, 10])
    ratio = pick(r, [2, 3, sp.Rational(3, 2)])
    bound = pick(r, [1000, 5000, 20000, 100000])
    nn = 1
    while a * (ratio**nn - 1) / (ratio - 1) <= bound:
        nn += 1
    Sn = a * (ratio**n - 1) / (ratio - 1)
    text = multipart(
        f"A geometric series has first term \\({a}\\) and common ratio \\({L(ratio)}\\).",
        [("a", "Write an expression for \\(S_n\\), the sum of the first \\(n\\) terms.", 1),
         ("b", f"Find the smallest number of terms for which the sum exceeds \\({bound}\\).", 3)])
    rhs = sp.nsimplify(bound * (ratio - 1) / a + 1)
    steps = [f"(a) \\(S_n = \\dfrac{{{a}\\left(({L(ratio)})^n - 1\\right)}}{{{L(ratio)} - 1}} = {L(sp.simplify(Sn))}\\).",
             f"(b) \\(S_n > {bound}\\) gives \\(\\left({L(ratio)}\\right)^n > {L(rhs)}\\).",
             f"\\(n > \\dfrac{{\\ln {L(rhs)}}}{{\\ln {L(ratio)}}} \\approx {math.log(float(rhs)) / math.log(float(ratio)):.3f}\\).",
             f"So the smallest number of terms is \\(n = {nn}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_expr(sp.simplify(Sn), ("n",))), P("b", 3, A_num(nn))), 4, 3, steps,
        "An inequality in \\(S_n\\) becomes an inequality in \\(r^n\\), solved with logarithms.",
        "Isolate \\(r^n\\) completely before taking logs; then round \\(n\\) up.",
        quicker="Check with the calculator: compute \\(S_n\\) for your \\(n\\) and for \\(n-1\\).",
        common_errors=[err(nn - 1, "careless error", "inequality direction", "Round up: the sum must exceed the bound.", step=4, part="b"),
                       err(a * ratio ** (n - 1), "interpretation", SER, "That is \\(T_n\\), not \\(S_n\\).", step=1, part="a")],
        skill="Use logarithms with the sum of a GP.",
        checkpoints=[cp(rhs, "the inequality for rⁿ", step=2, part="b")] if not rhs.is_integer or rhs > 10 else [],
        params={"form": "parts", "a": a, "r": ratio, "bound": bound, "n": nn},
    )


# ----------------------------------------------------------------------- 1H ---
def t_1H(r: Rng, d: int) -> Generated:
    a = pick(r, [3, 4, 6, 8, 9, 12, 18])
    ratio = pick(r, [sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(-1, 2), sp.Rational(2, 3), sp.Rational(-1, 3), sp.Rational(3, 4)])
    Sinf = a / (1 - ratio)
    if d == 1:
        return Generated(
            f"Find the limiting sum of the geometric series \\({series([a, a * ratio, a * ratio**2])} + \\cdots\\)",
            A_num(Sinf), 2, 1,
            [f"\\(r = {L(ratio)}\\) and \\(|r| < 1\\), so the limiting sum exists.", f"\\(S_\\infty = \\dfrac{{a}}{{1 - r}} = \\dfrac{{{a}}}{{1 - \\left({L(ratio)}\\right)}} = {L(Sinf)}\\)."],
            "A GP has a limiting sum \\(\\frac{a}{1-r}\\) only when \\(|r| < 1\\), because then \\(r^n \\to 0\\).",
            "Always state the condition \\(|r|<1\\) before using the formula.",
            quicker="Sanity check: for \\(0 < r < 1\\) the limiting sum is a little more than the sum of the first few terms.",
            common_errors=[err(a / (1 + ratio), "careless error", "sign error", "Sign error in \\(1 - r\\) with a negative ratio.", step=2),
                           err(a * ratio / (1 - ratio), "interpretation", SER, "You used the second term as \\(a\\).", step=2)],
            skill="Find the limiting sum of a geometric series.",
            params={"form": "Sinf", "a": a, "r": ratio},
        )
    if d == 2:
        if r.random() < 0.5:
            return Generated(
                f"A geometric series has first term \\({a}\\) and limiting sum \\({L(Sinf)}\\). Find the common ratio.",
                A_num(ratio), 2, 2,
                [f"\\(\\dfrac{{{a}}}{{1 - r}} = {L(Sinf)}\\)", f"\\(1 - r = {L(sp.Rational(a) / Sinf)}\\), so \\(r = {L(ratio)}\\), which satisfies \\(|r|<1\\)."],
                "Rearranging \\(S_\\infty = \\frac{a}{1-r}\\) gives \\(r = 1 - \\frac{a}{S_\\infty}\\).",
                "Check that your ratio satisfies \\(|r| < 1\\); otherwise no limiting sum exists.",
                quicker="\\(r = 1 - \\frac{a}{S_\\infty}\\) directly.",
                common_errors=[err(1 - ratio, "algebraic", "algebra", "You found \\(1 - r\\); solve for \\(r\\) itself.", step=2),
                               err(ratio - 1, "careless error", "sign error", "Sign error rearranging \\(1 - r = \\ldots\\).", step=2)],
                skill="Find the ratio from a limiting sum.",
                params={"form": "findr", "a": a, "S": Sinf},
            )
        m = pick(r, [2, 3, 4, 5])
        c = r.randint(-3, 3)
        g = m * x - c if c else m * x
        lo, hi = sp.Rational(c - 1, m), sp.Rational(c + 1, m)
        return Generated(
            f"For which values of \\(x\\) does the geometric series \\(1 + ({L(g)}) + ({L(g)})^2 + \\cdots\\) have a limiting sum?",
            A_iv([(lo, hi, False, False)]), 2, 2,
            [f"The ratio is \\(r = {L(g)}\\); a limiting sum needs \\(|r| < 1\\).", f"\\(-1 < {L(g)} < 1\\), so \\({L(lo)} < x < {L(hi)}\\)."],
            "A geometric series has a limiting sum exactly when \\(-1 < r < 1\\).",
            "Write the double inequality and do the same operation to all three parts.",
            quicker="Solve \\(|r| < 1\\) as a double inequality in one line.",
            skill="Find when a geometric series has a limiting sum.",
            params={"form": "interval", "m": m, "c": c},
        )
    m = pick(r, [2, 3, 4, 5])
    a0 = pick(r, [1, 2, 3])
    x1 = sp.Rational(1, 2 * m)
    S1 = a0 / (1 - m * x1)
    S2 = pick(r, [a0 * 3, a0 * 4, a0 * 5, sp.Rational(3 * a0, 2), sp.Rational(5 * a0, 4)])
    x2 = sp.Rational(1, m) * (1 - sp.Rational(a0) / S2)
    text = multipart(
        f"Consider the geometric series \\({a0} + {L(a0 * m * x)} + {L(a0 * m**2 * x**2)} + \\cdots\\)",
        [("a", "For which values of \\(x\\) does the series have a limiting sum?", 2),
         ("b", f"Find the limiting sum when \\(x = {L(x1)}\\).", 1),
         ("c", f"Find \\(x\\) if the limiting sum is \\({L(S2)}\\).", 2)])
    steps = [f"(a) \\(r = {m}x\\); a limiting sum needs \\(|{m}x| < 1\\), i.e. \\({L(sp.Rational(-1, m))} < x < {L(sp.Rational(1, m))}\\).",
             f"(b) \\(r = {m}\\times{L(x1)} = \\tfrac{{1}}{{2}}\\), so \\(S_\\infty = \\dfrac{{{a0}}}{{1 - \\frac{{1}}{{2}}}} = {L(S1)}\\).",
             f"(c) \\(\\dfrac{{{a0}}}{{1 - {m}x}} = {L(S2)}\\), so \\(1 - {m}x = {L(a0 / S2)}\\) and \\(x = {L(x2)}\\), which lies in the interval from (a)."]
    return Generated(
        text, A_parts(P("a", 2, A_iv([(sp.Rational(-1, m), sp.Rational(1, m), False, False)])), P("b", 1, A_num(S1)), P("c", 2, A_num(x2))), 5, 3, steps,
        "The ratio depends on \\(x\\): the limiting sum exists only for \\(|r| < 1\\), and any answer must lie in that interval.",
        "In (c) check your \\(x\\) against the interval from (a) and say so.",
        quicker="Write \\(S_\\infty = \\frac{a}{1-r}\\) with \\(r\\) in terms of \\(x\\) once, then reuse it for (b) and (c).",
        common_errors=[err(-x2, "careless error", "sign error", "Sign error when solving for \\(x\\).", step=3, part="c"),
                       err(a0 / (1 + m * x1), "careless error", "sign error", "The formula is \\(\\frac{a}{1 - r}\\).", step=2, part="b")],
        skill="Limiting sums with a variable ratio.",
        params={"form": "parts", "m": m, "a": a0, "S2": S2},
    )


# ----------------------------------------------------------------------- 1I ---
def t_1I(r: Rng, d: int) -> Generated:
    if d == 1:
        dig = r.randint(1, 98)
        while dig % 11 == 0 or dig % 9 == 0:
            dig = r.randint(1, 98)
        frac = sp.Rational(dig, 99)
        return Generated(
            f"Express \\(0.\\overline{{{dig:02d}}}\\) as a fraction in simplest form using a geometric series.",
            A_num(frac), 2, 1,
            [f"\\(0.\\overline{{{dig:02d}}} = \\dfrac{{{dig}}}{{100}} + \\dfrac{{{dig}}}{{100^2}} + \\cdots\\), a GP with \\(a = \\frac{{{dig}}}{{100}}\\), \\(r = \\frac{{1}}{{100}}\\).",
             f"\\(S_\\infty = \\dfrac{{{dig}/100}}{{1 - 1/100}} = \\dfrac{{{dig}}}{{99}} = {L(frac)}\\)."],
            "A recurring decimal is the limiting sum of a GP whose ratio is a power of \\(\\frac{1}{10}\\).",
            "The question says 'using a geometric series': you must show the series, not just the trick.",
            quicker="A two-digit repeating block over 99 gives the fraction immediately — use it to check.",
            common_errors=[err(sp.Rational(dig, 100), "incomplete reasoning", SER, "That is only the first term of the series.", step=1),
                           err(sp.Rational(dig, 90), "formula selection", SER, "The ratio is \\(\\frac{1}{100}\\) for a two-digit block, so the denominator is 99.", step=2)],
            skill="Write a recurring decimal as a limiting sum.",
            params={"form": "two", "dig": dig},
        )
    if d == 2:
        pre, rep = r.randint(1, 9), r.randint(1, 9)
        while rep == pre:
            rep = r.randint(1, 9)
        frac = sp.Rational(pre, 10) + sp.Rational(rep, 90)
        return Generated(
            f"Express \\(0.{pre}\\overline{{{rep}}}\\) as a fraction in simplest form.",
            A_num(frac), 3, 2,
            [f"\\(0.{pre}\\overline{{{rep}}} = \\dfrac{{{pre}}}{{10}} + \\left(\\dfrac{{{rep}}}{{100}} + \\dfrac{{{rep}}}{{1000}} + \\cdots\\right)\\)",
             f"The bracket is a GP with \\(a = \\frac{{{rep}}}{{100}}\\), \\(r = \\frac{{1}}{{10}}\\): sum \\(= \\dfrac{{{rep}/100}}{{9/10}} = \\dfrac{{{rep}}}{{90}}\\).",
             f"Total \\(= \\dfrac{{{pre}}}{{10}} + \\dfrac{{{rep}}}{{90}} = {L(frac)}\\)."],
            "Separate the non-recurring part, then sum the recurring part as a GP.",
            "Simplify the final fraction fully.",
            quicker=f"\\(\\dfrac{{{pre}{rep} - {pre}}}{{90}}\\) is the shortcut for one non-recurring and one recurring digit — use it as a check.",
            common_errors=[err(sp.Rational(10 * pre + rep, 99), "conceptual", SER, "Only the last digit recurs; the first digit is a separate term.", step=1),
                           err(sp.Rational(pre, 10) + sp.Rational(rep, 99), "formula selection", SER, "The recurring part starts in the hundredths, so its sum is \\(\\frac{d}{90}\\).", step=2)],
            skill="Write a mixed recurring decimal as a fraction.",
            checkpoints=[cp(sp.Rational(rep, 90), "the recurring part as a fraction", step=2, marks=2)],
            params={"form": "mixed", "pre": pre, "rep": rep},
        )
    while True:
        blk = r.randint(101, 998)
        if blk % 111 and blk % 37 and blk % 27:
            break
    frac = sp.Rational(blk, 999)
    text = multipart(
        f"The recurring decimal \\(0.\\overline{{{blk}}}\\) can be written as a geometric series.",
        [("a", "Find the first term of the series.", 1), ("b", "Find the common ratio.", 1),
         ("c", "Hence express the decimal as a fraction in simplest form.", 2)])
    steps = [f"(a) \\(0.\\overline{{{blk}}} = \\dfrac{{{blk}}}{{1000}} + \\dfrac{{{blk}}}{{1000^2}} + \\cdots\\), so \\(a = \\dfrac{{{blk}}}{{1000}}\\).",
             "(b) \\(r = \\dfrac{1}{1000}\\).",
             f"(c) \\(S_\\infty = \\dfrac{{{blk}/1000}}{{1 - 1/1000}} = \\dfrac{{{blk}}}{{999}} = {L(frac)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(sp.Rational(blk, 1000))), P("b", 1, A_num(sp.Rational(1, 1000))), P("c", 2, A_num(frac))), 4, 3, steps,
        "A three-digit repeating block gives a GP with ratio \\(\\frac{1}{1000}\\).",
        "Simplify the fraction by finding the highest common factor of the numerator and 999.",
        quicker="A repeating block of \\(m\\) digits over \\(m\\) nines gives the fraction directly.",
        common_errors=[err(sp.Rational(1, 100), "careless error", SER, "Three repeating digits shift three places: \\(r = \\frac{1}{1000}\\).", step=2, part="b"),
                       err(sp.Rational(blk, 1000), "incomplete reasoning", SER, "That is only the first term; find the limiting sum.", step=3, part="c")],
        skill="Recurring decimals as limiting sums.",
        params={"form": "parts", "blk": blk},
    )
