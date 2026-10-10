"""Syllabus-aligned parametrised Mathematics Advanced question templates.

Every instance is labelled GENERATED. Answers and worked solutions are computed with SymPy,
so marking is deterministic. Templates are keyed by learning-plan code (e.g. "1B") so that a
LEARNING subtopic never runs out of fresh practice.

Parameters are chosen with a seeded RNG; that is *content generation*, not the question
selection logic (which lives in app.selection)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

import sympy as sp

x, n, t, k = sp.symbols("x n t k")
L = sp.latex


@dataclass
class Generated:
    text: str
    answer: dict
    marks: int
    difficulty: int
    steps: list[str]
    concept: str
    technique: str
    quicker: str | None = None
    common_errors: list[dict] = field(default_factory=list)
    directive_verb: str = "Find"
    question_type: str = "working"

    def solution(self) -> dict:
        return {
            "steps": self.steps,
            "concept": self.concept,
            "quicker": self.quicker,
            "technique": self.technique,
            "common_errors": self.common_errors,
        }


def _minutes(marks: int) -> float:
    # HSC Mathematics Advanced: 100 marks in 180 minutes => ~1.8 min/mark, plus reading.
    return round(1.8 * marks + 0.5, 1)


def ex(e) -> str:
    """SymPy expression as a string the marker can parse back."""
    return sp.sstr(sp.nsimplify(e) if isinstance(e, float) else e)


def err(answer, category: str, diagnosis: str) -> dict:
    return {"answer": ex(answer), "category": category, "diagnosis": diagnosis}


# ----------------------------------------------------------------- Chapter 1 ---
def t_1A(r: random.Random, d: int) -> Generated:
    a, b, c = r.randint(1, 4), r.randint(-6, 6), r.randint(-9, 9)
    T = a * n**2 + b * n + c
    m = r.randint(5, 12)
    val = T.subs(n, m)
    if d == 1:
        return Generated(
            f"A sequence is defined by \\(T_n = {L(T)}\\). Find \\(T_{{{m}}}\\).",
            {"type": "num", "value": ex(val), "tol": 0}, 1, 1,
            [f"Substitute \\(n = {m}\\): \\(T_{{{m}}} = {L(T.subs(n, sp.Symbol(str(m))))} = {val}\\)."],
            "The formula for \\(T_n\\) gives each term directly from its position \\(n\\).",
            "Show the substitution line: it earns the method mark even if the arithmetic slips.",
            common_errors=[err(T.subs(n, m - 1), "interpretation", f"You found \\(T_{{{m-1}}}\\): the term number is {m}, not the previous term.")],
        )
    # which term has a given value (linear formula so the answer is an integer)
    a1, c1 = r.randint(2, 7), r.randint(-10, 10)
    T1 = a1 * n + c1
    m = r.randint(12, 40)
    v = T1.subs(n, m)
    return Generated(
        f"A sequence has \\(T_n = {L(T1)}\\). Which term of the sequence is equal to \\({v}\\)? Is \\({v + 1}\\) a term of the sequence? Give the term number of \\({v}\\) as your answer.",
        {"type": "num", "value": str(m), "tol": 0}, 2, 2,
        [f"Solve \\({L(T1)} = {v}\\).", f"\\({a1}n = {v - c1}\\), so \\(n = {m}\\).",
         f"For \\({v+1}\\): \\({a1}n = {v + 1 - c1}\\) gives \\(n = {sp.Rational(v + 1 - c1, a1)}\\), not a positive integer" + (" (so it is not a term)." if (v + 1 - c1) % a1 else ".")],
        "A number is a term of a sequence exactly when solving \\(T_n = \\text{value}\\) gives a positive integer \\(n\\).",
        "Always state the conclusion in words: 'so it is the 23rd term'.",
    )


def t_1B(r: random.Random, d: int) -> Generated:
    a, dd = r.randint(-15, 20), r.choice([i for i in range(-7, 8) if i != 0])
    Tn = sp.expand(a + (n - 1) * dd)
    if d == 1:
        m = r.randint(15, 60)
        terms = ", ".join(str(a + i * dd) for i in range(3))
        return Generated(
            f"Find the {m}th term of the arithmetic sequence \\({terms}, \\ldots\\)",
            {"type": "num", "value": str(a + (m - 1) * dd), "tol": 0}, 2, 1,
            [f"\\(a = {a}\\), \\(d = {a + dd} - ({a}) = {dd}\\).", f"\\(T_n = a + (n-1)d\\), so \\(T_{{{m}}} = {a} + {m - 1}\\times({dd}) = {a + (m - 1) * dd}\\)."],
            "In an AP each term is the previous term plus the common difference \\(d\\); \\(T_n = a + (n-1)d\\).",
            "Write \\(a\\) and \\(d\\) explicitly first; most AP errors come from a wrong \\(d\\).",
            quicker=f"Count steps: from term 1 to term {m} is {m - 1} steps of \\(d\\).",
            common_errors=[err(a + m * dd, "formula selection", "You used \\(a + nd\\) instead of \\(a + (n-1)d\\): the first term already counts as term 1."),
                           err(a - (m - 1) * dd, "arithmetic", "Your common difference has the wrong sign: \\(d = T_2 - T_1\\).")],
        )
    p, q = r.randint(3, 8), r.randint(10, 20)
    Tp, Tq = a + (p - 1) * dd, a + (q - 1) * dd
    m = r.randint(25, 50)
    return Generated(
        f"In an arithmetic sequence, \\(T_{{{p}}} = {Tp}\\) and \\(T_{{{q}}} = {Tq}\\). Find \\(T_{{{m}}}\\).",
        {"type": "num", "value": str(a + (m - 1) * dd), "tol": 0}, 3, 2 if d == 2 else 3,
        [f"\\(a + {p - 1}d = {Tp}\\) and \\(a + {q - 1}d = {Tq}\\).",
         f"Subtract: \\({q - p}d = {Tq - Tp}\\), so \\(d = {dd}\\).",
         f"Then \\(a = {Tp} - {p - 1}\\times({dd}) = {a}\\).",
         f"\\(T_{{{m}}} = {a} + {m - 1}\\times({dd}) = {a + (m - 1) * dd}\\)."],
        "Two terms of an AP give two linear equations in \\(a\\) and \\(d\\); subtracting eliminates \\(a\\).",
        "Label the simultaneous equations (1) and (2) and say which you subtract.",
        quicker=f"From term {q} to term {m} is {m - q} steps: \\(T_{{{m}}} = {Tq} + {m - q}\\times({dd})\\).",
    )


def t_1C(r: random.Random, d: int) -> Generated:
    a = r.choice([1, 2, 3, 4, 5, -2, -3])
    ratio = r.choice([2, 3, -2, sp.Rational(1, 2), sp.Rational(-1, 2), sp.Rational(2, 3)])
    if d <= 2:
        m = r.randint(6, 10)
        terms = ", ".join(L(a * ratio**i) for i in range(3))
        val = a * ratio ** (m - 1)
        return Generated(
            f"Find the {m}th term of the geometric sequence \\({terms}, \\ldots\\)",
            {"type": "num", "value": ex(val), "tol": 0}, 2, d,
            [f"\\(a = {L(a)}\\), \\(r = \\dfrac{{{L(a * ratio)}}}{{{L(a)}}} = {L(ratio)}\\).", f"\\(T_{{{m}}} = ar^{{{m - 1}}} = {L(a)}\\times\\left({L(ratio)}\\right)^{{{m - 1}}} = {L(val)}\\)."],
            "In a GP each term is the previous term multiplied by the common ratio \\(r\\); \\(T_n = ar^{n-1}\\).",
            "Keep negative or fractional ratios in brackets when raising to a power.",
            common_errors=[err(a * ratio**m, "formula selection", "You used \\(ar^n\\) rather than \\(ar^{n-1}\\)."),
                           err(-val, "sign", "Sign error: a negative ratio raised to an odd/even power changes the sign.")],
        )
    # first term to exceed a bound (needs logs or trial)
    a2, r2 = r.choice([2, 3, 5]), r.choice([2, 3])
    bound = r.choice([1000, 5000, 20000, 100000])
    nn = 1
    while a2 * r2 ** (nn - 1) <= bound:
        nn += 1
    return Generated(
        f"The geometric sequence \\({a2}, {a2 * r2}, {a2 * r2**2}, \\ldots\\) is given. Find the first term number \\(n\\) for which \\(T_n > {bound}\\).",
        {"type": "num", "value": str(nn), "tol": 0}, 3, 3,
        [f"\\(T_n = {a2}\\times {r2}^{{n-1}} > {bound}\\)", f"\\({r2}^{{n-1}} > {sp.Rational(bound, a2)}\\)",
         f"\\(n - 1 > \\dfrac{{\\ln {L(sp.Rational(bound, a2))}}}{{\\ln {r2}}} \\approx {float(sp.log(sp.Rational(bound, a2)) / sp.log(r2)):.3f}\\)",
         f"So the smallest integer is \\(n = {nn}\\). Check: \\(T_{{{nn - 1}}} = {a2 * r2 ** (nn - 2)}\\), \\(T_{{{nn}}} = {a2 * r2 ** (nn - 1)}\\)."],
        "Inequalities involving \\(r^{n-1}\\) are solved by taking logarithms; \\(n\\) must then be rounded up to a whole term number.",
        "Always check the term before and after your answer: it catches off-by-one errors.",
        common_errors=[err(nn - 1, "interpretation", "You rounded down: the term must exceed the bound, so take the next whole number.")],
    )


def t_1D(r: random.Random, d: int) -> Generated:
    if d == 1 or r.random() < 0.5:
        p = r.choice([2, 3, 4, 5])
        q = r.choice([2, 3, 4, 6, 8])
        m = p * q * r.choice([1, 4, 9])
        geo_mean = sp.sqrt(p * m)
        if not geo_mean.is_integer:
            m, geo_mean = p * 4, 2 * p
        return Generated(
            f"The numbers \\({p}\\), \\(x\\) and \\({m}\\) are consecutive terms of a geometric sequence, with \\(x > 0\\). Find \\(x\\).",
            {"type": "num", "value": ex(geo_mean), "tol": 0}, 2, 1 if d == 1 else 2,
            [f"In a GP, \\(\\dfrac{{x}}{{{p}}} = \\dfrac{{{m}}}{{x}}\\).", f"\\(x^2 = {p * m}\\), so \\(x = \\pm{L(geo_mean)}\\).", f"Since \\(x > 0\\), \\(x = {L(geo_mean)}\\)."],
            "Three consecutive GP terms satisfy \\(\\frac{T_2}{T_1} = \\frac{T_3}{T_2}\\), i.e. the middle term is the geometric mean.",
            "Use the given restriction (here \\(x>0\\)) explicitly to reject a solution.",
            common_errors=[err(sp.Rational(p + m, 2), "formula selection", "You used the arithmetic mean \\(\\frac{a+b}{2}\\) (AP condition), not the geometric mean.")],
        )
    kk = r.randint(2, 6)
    # x, x + kk, 3x - kk ... AP condition: 2(x+kk) = x + 3x - kk  =>  2x = 3kk
    xx = sp.Rational(3 * kk, 2)
    return Generated(
        f"The numbers \\(x\\), \\(x + {kk}\\) and \\(3x - {kk}\\) are consecutive terms of an arithmetic sequence. Find \\(x\\).",
        {"type": "num", "value": ex(xx), "tol": 0}, 2, 2,
        [f"In an AP, \\(T_2 - T_1 = T_3 - T_2\\): \\((x + {kk}) - x = (3x - {kk}) - (x + {kk})\\).", f"\\({kk} = 2x - {2 * kk}\\), so \\(x = {L(xx)}\\)."],
        "Consecutive AP terms have equal differences, so the middle term is the average of its neighbours.",
        "Write the equal-differences equation before simplifying.",
    )


def t_1E(r: random.Random, d: int) -> Generated:
    a, b = r.randint(1, 6), r.randint(-5, 8)
    N = r.randint(6, 20)
    s = sum(a * i + b for i in range(1, N + 1))
    if d >= 2:
        lo = r.randint(3, 6)
        s2 = sum(2 ** i for i in range(lo, lo + 5))
        return Generated(
            f"Evaluate \\(\\displaystyle\\sum_{{k={lo}}}^{{{lo + 4}}} 2^k\\).",
            {"type": "num", "value": str(s2), "tol": 0}, 2, 2,
            [f"Write out the terms: \\({' + '.join(str(2**i) for i in range(lo, lo + 5))}\\).", f"Sum \\(= {s2}\\)."],
            "Sigma notation lists the terms obtained by substituting each integer value of the index.",
            "Count the terms: from \\(k=a\\) to \\(k=b\\) there are \\(b-a+1\\) terms.",
            quicker=f"It is a GP with first term \\(2^{{{lo}}}\\), ratio 2 and 5 terms: \\(2^{{{lo}}}(2^5-1)\\).",
            common_errors=[err(s2 - 2 ** (lo + 4), "careless error", "You stopped one term early: the upper limit is included.")],
        )
    return Generated(
        f"Evaluate \\(\\displaystyle\\sum_{{k=1}}^{{{N}}} ({a}k {'+' if b >= 0 else '-'} {abs(b)})\\).",
        {"type": "num", "value": str(s), "tol": 0}, 2, 1,
        [f"The terms form an AP with first term \\({a + b}\\) and last term \\({a * N + b}\\), {N} terms.", f"\\(S = \\dfrac{{{N}}}{{2}}({a + b} + {a * N + b}) = {s}\\)."],
        "A sum of a linear expression in \\(k\\) is an arithmetic series.",
        "Identify the first term, last term and number of terms before using a formula.",
    )


def t_1F(r: random.Random, d: int) -> Generated:
    a, dd = r.randint(1, 12), r.randint(2, 7)
    if d == 1:
        N = r.randint(15, 40)
        S = sp.Rational(N, 2) * (2 * a + (N - 1) * dd)
        return Generated(
            f"Find the sum of the first {N} terms of the arithmetic series \\({a} + {a + dd} + {a + 2 * dd} + \\cdots\\)",
            {"type": "num", "value": ex(S), "tol": 0}, 2, 1,
            [f"\\(a = {a}\\), \\(d = {dd}\\), \\(n = {N}\\).", f"\\(S_n = \\dfrac{{n}}{{2}}\\left(2a + (n-1)d\\right) = \\dfrac{{{N}}}{{2}}\\left({2 * a} + {N - 1}\\times {dd}\\right) = {S}\\)."],
            "\\(S_n = \\frac{n}{2}(2a + (n-1)d)\\), or \\(\\frac{n}{2}(a + \\ell)\\) when the last term is known.",
            "Quote the formula, then substitute: the substitution line is usually worth a mark.",
            common_errors=[err(sp.Rational(N, 2) * (2 * a + N * dd), "formula selection", "You used \\(nd\\) instead of \\((n-1)d\\) inside the formula.")],
        )
    # find n given S_n
    N = r.randint(8, 25)
    S = sp.Rational(N, 2) * (2 * a + (N - 1) * dd)
    return Generated(
        f"How many terms of the arithmetic series \\({a} + {a + dd} + {a + 2 * dd} + \\cdots\\) must be added to give a sum of \\({S}\\)?",
        {"type": "num", "value": str(N), "tol": 0}, 3, d,
        [f"\\(\\dfrac{{n}}{{2}}\\left({2 * a} + (n-1){dd}\\right) = {S}\\)",
         f"\\({dd}n^2 + {2 * a - dd}n - {2 * S} = 0\\)",
         f"Solving gives \\(n = {N}\\) (the other root is negative or not an integer, so it is rejected)."],
        "Unknown \\(n\\) in \\(S_n\\) gives a quadratic; only positive integer solutions are valid.",
        "State why the second root is rejected: markers look for it.",
    )


def t_1G(r: random.Random, d: int) -> Generated:
    a = r.choice([1, 2, 3, 5])
    ratio = r.choice([2, 3, -2, sp.Rational(1, 2), sp.Rational(1, 3)])
    N = r.randint(5, 10)
    S = sp.nsimplify(a * (ratio**N - 1) / (ratio - 1))
    return Generated(
        f"Find the exact sum of the first {N} terms of the geometric series \\({L(a)} + {L(a * ratio)} + {L(a * ratio**2)} + \\cdots\\)",
        {"type": "num", "value": ex(S), "tol": 0}, 2, d,
        [f"\\(a = {L(a)}\\), \\(r = {L(ratio)}\\), \\(n = {N}\\).", f"\\(S_n = \\dfrac{{a(r^n - 1)}}{{r - 1}} = \\dfrac{{{L(a)}\\left(\\left({L(ratio)}\\right)^{{{N}}} - 1\\right)}}{{{L(ratio)} - 1}} = {L(S)}\\)."],
        "\\(S_n = \\frac{a(r^n-1)}{r-1}\\) (convenient for \\(r>1\\)) or \\(\\frac{a(1-r^n)}{1-r}\\) (for \\(|r|<1\\)): they are the same formula.",
        "Choose the form that keeps the denominator positive to reduce sign errors.",
        common_errors=[err(sp.nsimplify(a * (ratio ** (N - 1) - 1) / (ratio - 1)), "formula selection", "You used \\(r^{n-1}\\) in the sum formula; the sum uses \\(r^n\\).")],
    )


def t_1H(r: random.Random, d: int) -> Generated:
    a = r.choice([3, 4, 6, 8, 9, 12, 18])
    ratio = r.choice([sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(-1, 2), sp.Rational(2, 3), sp.Rational(-1, 3), sp.Rational(3, 4)])
    Sinf = a / (1 - ratio)
    if d == 1:
        return Generated(
            f"Find the limiting sum of the geometric series \\({L(a)} + {L(a * ratio)} + {L(a * ratio**2)} + \\cdots\\)",
            {"type": "num", "value": ex(Sinf), "tol": 0}, 2, 1,
            [f"\\(r = {L(ratio)}\\) and \\(|r| < 1\\), so the limiting sum exists.", f"\\(S_\\infty = \\dfrac{{a}}{{1 - r}} = \\dfrac{{{a}}}{{1 - ({L(ratio)})}} = {L(Sinf)}\\)."],
            "A GP has a limiting sum \\(\\frac{a}{1-r}\\) only when \\(|r| < 1\\), because then \\(r^n \\to 0\\).",
            "Always state the condition \\(|r|<1\\) before using the formula.",
            common_errors=[err(a / (1 + ratio), "sign", "Sign error in \\(1 - r\\) with a negative ratio.")],
        )
    return Generated(
        f"A geometric series has first term \\({a}\\) and limiting sum \\({L(Sinf)}\\). Find the common ratio.",
        {"type": "num", "value": ex(ratio), "tol": 0}, 2, 2,
        [f"\\(\\dfrac{{{a}}}{{1 - r}} = {L(Sinf)}\\)", f"\\(1 - r = {L(sp.Rational(a) / Sinf)}\\), so \\(r = {L(ratio)}\\), which satisfies \\(|r|<1\\)."],
        "Rearranging \\(S_\\infty = \\frac{a}{1-r}\\) gives \\(r = 1 - \\frac{a}{S_\\infty}\\).",
        "Check that your ratio satisfies \\(|r| < 1\\); otherwise no limiting sum exists.",
    )


def t_1I(r: random.Random, d: int) -> Generated:
    if d == 1:
        dig = r.randint(1, 98)
        while dig % 11 == 0 or dig % 9 == 0:
            dig = r.randint(1, 98)
        frac = sp.Rational(dig, 99)
        return Generated(
            f"Express \\(0.\\overline{{{dig:02d}}}\\) as a fraction in simplest form using a geometric series.",
            {"type": "num", "value": ex(frac), "tol": 0}, 2, 1,
            [f"\\(0.\\overline{{{dig:02d}}} = \\dfrac{{{dig}}}{{100}} + \\dfrac{{{dig}}}{{100^2}} + \\cdots\\), a GP with \\(a = \\frac{{{dig}}}{{100}}\\), \\(r = \\frac{{1}}{{100}}\\).",
             f"\\(S_\\infty = \\dfrac{{{dig}/100}}{{1 - 1/100}} = \\dfrac{{{dig}}}{{99}} = {L(frac)}\\)."],
            "A recurring decimal is the limiting sum of a GP whose ratio is a power of \\(\\frac{1}{10}\\).",
            "The question says 'using a geometric series': you must show the series, not just the trick.",
        )
    pre, rep = r.randint(1, 9), r.randint(1, 9)
    while rep == pre:
        rep = r.randint(1, 9)
    frac = sp.Rational(pre, 10) + sp.Rational(rep, 90)
    return Generated(
        f"Express \\(0.{pre}\\overline{{{rep}}}\\) as a fraction in simplest form.",
        {"type": "num", "value": ex(frac), "tol": 0}, 3, d,
        [f"\\(0.{pre}\\overline{{{rep}}} = \\dfrac{{{pre}}}{{10}} + \\left(\\dfrac{{{rep}}}{{100}} + \\dfrac{{{rep}}}{{1000}} + \\cdots\\right)\\)",
         f"The bracket is a GP with \\(a = \\frac{{{rep}}}{{100}}\\), \\(r = \\frac{{1}}{{10}}\\): sum \\(= \\dfrac{{{rep}/100}}{{9/10}} = \\dfrac{{{rep}}}{{90}}\\).",
         f"Total \\(= \\dfrac{{{pre}}}{{10}} + \\dfrac{{{rep}}}{{90}} = {L(frac)}\\)."],
        "Separate the non-recurring part, then sum the recurring part as a GP.",
        "Simplify the final fraction fully.",
    )


# ----------------------------------------------------------------- Chapter 2 ---
def _cubic_with_stationary(r: random.Random):
    p = r.randint(-4, 3)
    q = p + 2 * r.randint(1, 3)
    c = r.randint(-5, 5)
    f = sp.expand(sp.integrate(3 * (x - p) * (x - q), x) + c)
    return f, p, q


def t_2A(r: random.Random, d: int) -> Generated:
    f, p, q = _cubic_with_stationary(r)
    return Generated(
        f"For \\(f(x) = {L(f)}\\), find the values of \\(x\\) for which \\(f\\) is decreasing. Give your answer as an interval (e.g. \\(a < x < b\\)); enter the endpoints as a list \\(a, b\\).",
        {"type": "set", "values": [str(p), str(q)]}, 2, d,
        [f"\\(f'(x) = {L(sp.factor(sp.diff(f, x)))}\\).", f"\\(f'(x) < 0\\) between the roots, so \\(f\\) is decreasing for \\({p} < x < {q}\\)."],
        "A function is decreasing where \\(f'(x) < 0\\); for an upright quadratic derivative that is between its zeros.",
        "Sketch the sign of \\(f'(x)\\) on a number line to justify the interval.",
    )


def t_2B(r: random.Random, d: int) -> Generated:
    f, p, q = _cubic_with_stationary(r)
    fp, fq = f.subs(x, p), f.subs(x, q)
    if d == 1:
        return Generated(
            f"Find the \\(x\\)-coordinates of the stationary points of \\(y = {L(f)}\\). Enter them as a list.",
            {"type": "set", "values": [str(p), str(q)]}, 2, 1,
            [f"\\(\\dfrac{{dy}}{{dx}} = {L(sp.diff(f, x))} = {L(sp.factor(sp.diff(f, x)))}\\).", f"Stationary when \\(\\dfrac{{dy}}{{dx}} = 0\\): \\(x = {p}\\) or \\(x = {q}\\)."],
            "Stationary points occur where the derivative is zero.",
            "Factorise the derivative fully before solving.",
        )
    return Generated(
        f"Find the coordinates of the local maximum turning point of \\(y = {L(f)}\\) and justify its nature. Enter the coordinates as a list \\(x, y\\).",
        {"type": "set", "values": [str(p), ex(fp)], "ordered": True}, 4, 3 if d == 3 else 2,
        [f"\\(y' = {L(sp.factor(sp.diff(f, x)))}\\), so stationary points at \\(x = {p}, {q}\\).",
         f"\\(y'' = {L(sp.diff(f, x, 2))}\\). At \\(x = {p}\\): \\(y'' = {sp.diff(f, x, 2).subs(x, p)} < 0\\) (maximum). At \\(x = {q}\\): \\(y'' = {sp.diff(f, x, 2).subs(x, q)} > 0\\) (minimum).",
         f"Local maximum at \\(({p}, {L(fp)})\\)."],
        "The second derivative test: \\(f''<0\\) at a stationary point means concave down, so a maximum.",
        "Nature must be justified (table of gradients or second derivative); an unjustified 'maximum' loses the mark.",
        common_errors=[{"answer": f"{q}, {ex(fq)}", "category": "conceptual", "diagnosis": "That is the local minimum: check the sign of \\(y''\\)."}],
    )


def t_2C(r: random.Random, d: int) -> Generated:
    a, b, c, e = r.randint(1, 4), r.randint(-5, 5), r.randint(-6, 6), r.randint(2, 5)
    f = a * x**e + b * x**3 + c * x
    m = r.randint(-2, 3)
    val = sp.diff(f, x, 2).subs(x, m)
    return Generated(
        f"Given \\(f(x) = {L(f)}\\), find \\(f''({m})\\).",
        {"type": "num", "value": ex(val), "tol": 0}, 2, d,
        [f"\\(f'(x) = {L(sp.diff(f, x))}\\)", f"\\(f''(x) = {L(sp.diff(f, x, 2))}\\)", f"\\(f''({m}) = {val}\\)"],
        "The second derivative is the derivative of the first derivative.",
        "Differentiate in two clear lines; don't try to do both steps mentally.",
    )


def t_2D(r: random.Random, d: int) -> Generated:
    a = r.choice([1, 2, -1])
    h = r.randint(-3, 3)
    b = -3 * a * h
    c, e = r.randint(-6, 6), r.randint(-5, 5)
    f = a * x**3 + b * x**2 + c * x + e
    return Generated(
        f"Find the \\(x\\)-coordinate of the point of inflection of \\(y = {L(f)}\\), and explain why it is a point of inflection.",
        {"type": "num", "value": str(h), "tol": 0}, 2, d,
        [f"\\(y'' = {L(sp.diff(f, x, 2))}\\), which is zero at \\(x = {h}\\).", "\\(y''\\) is linear and changes sign at this point, so the concavity changes: it is a point of inflection."],
        "A point of inflection needs \\(y'' = 0\\) and a change of concavity (sign change of \\(y''\\)).",
        "\\(y''=0\\) alone is not enough: always test the sign change.",
    )


def t_2F(r: random.Random, d: int) -> Generated:
    p, q = r.randint(-3, 0), r.randint(2, 5)
    h = r.randint(p + 1, q - 1) if q - p > 1 else p
    c = r.randint(-4, 6)
    f = -(x - h) ** 2 + c
    ends = {p: f.subs(x, p), q: f.subs(x, q)}
    gmin = min(ends.values())
    return Generated(
        f"Find the global minimum value of \\(f(x) = {L(sp.expand(f))}\\) on the interval \\({p} \\le x \\le {q}\\).",
        {"type": "num", "value": ex(gmin), "tol": 0}, 3, d,
        [f"\\(f'(x) = {L(sp.diff(f, x))} = 0\\) at \\(x = {h}\\), which is a maximum (the parabola is concave down).",
         f"Check endpoints: \\(f({p}) = {ends[p]}\\), \\(f({q}) = {ends[q]}\\).", f"Global minimum \\(= {gmin}\\)."],
        "On a closed interval the global extrema occur at stationary points or at the endpoints.",
        "Always evaluate the endpoints: global questions are designed to catch students who only check stationary points.",
        common_errors=[err(c, "interpretation", "That is the stationary value (a maximum); the global minimum occurs at an endpoint.")],
    )


def t_2H(r: random.Random, d: int) -> Generated:
    P = r.choice([40, 60, 80, 100, 120])
    area = sp.Rational(P, 4) ** 2
    return Generated(
        f"A rectangle has perimeter \\({P}\\) cm. Show, using calculus, that the maximum area is \\(A = ?\\) and find it (in cm²).",
        {"type": "num", "value": ex(area), "tol": 0, "units": "cm^2"}, 3, d,
        [f"Let the sides be \\(x\\) and \\({P // 2} - x\\). \\(A = x({P // 2} - x)\\).",
         f"\\(A' = {P // 2} - 2x = 0\\) gives \\(x = {sp.Rational(P, 4)}\\); \\(A'' = -2 < 0\\), so a maximum.",
         f"\\(A_{{\\max}} = {sp.Rational(P, 4)}^2 = {area}\\) cm²."],
        "Optimisation: express the quantity in one variable using the constraint, differentiate, and justify the maximum.",
        "Define your variable clearly and justify max/min: 'show that' questions are marked on reasoning.",
    )


def t_2I(r: random.Random, d: int) -> Generated:
    a, b, c = r.randint(1, 6), r.randint(-5, 5), r.randint(1, 9)
    f = a * x**2 + b * x + c
    F = sp.integrate(f, x)
    return Generated(
        f"Find the primitive of \\({L(f)}\\).",
        {"type": "antiderivative", "value": ex(F), "var": "x"}, 1, 1,
        [f"Increase each index by one and divide: \\(\\int ({L(f)})\\,dx = {L(F)} + C\\)."],
        "A primitive \\(F\\) satisfies \\(F'(x) = f(x)\\); every primitive differs by a constant.",
        "Always include \\(+C\\) for an indefinite primitive.",
    )


# ----------------------------------------------------------------- Chapter 3 ---
def t_3A(r: random.Random, d: int) -> Generated:
    a, b = r.randint(0, 2), r.randint(3, 5)
    cc, kk = r.randint(1, 3), r.randint(0, 4)
    f = cc * x**2 + kk
    val = sp.integrate(f, (x, a, b))
    return Generated(
        f"Evaluate \\(\\displaystyle\\int_{{{a}}}^{{{b}}} ({L(f)})\\,dx\\).",
        {"type": "num", "value": ex(val), "tol": 0}, 2, d,
        [f"\\(\\left[{L(sp.integrate(f, x))}\\right]_{{{a}}}^{{{b}}}\\)", f"\\(= ({L(sp.integrate(f, x).subs(x, b))}) - ({L(sp.integrate(f, x).subs(x, a))}) = {L(val)}\\)."],
        "The fundamental theorem: \\(\\int_a^b f(x)\\,dx = F(b) - F(a)\\) where \\(F' = f\\).",
        "Write the square-bracket line before substituting.",
        common_errors=[err(sp.integrate(f, x).subs(x, a) - sp.integrate(f, x).subs(x, b), "sign", "You subtracted in the wrong order: upper limit minus lower limit.")],
    )


t_3B = t_3A
t_3C = t_3A


def t_3E(r: random.Random, d: int) -> Generated:
    a, b, m = r.randint(2, 5), r.randint(-4, 6), r.randint(2, 5)
    f = (a * x + b) ** m
    F = (a * x + b) ** (m + 1) / (a * (m + 1))
    return Generated(
        f"Find \\(\\displaystyle\\int ({L(a * x + b)})^{{{m}}}\\,dx\\).",
        {"type": "antiderivative", "value": ex(F), "var": "x"}, 2, d,
        [f"\\(\\int (ax+b)^n dx = \\dfrac{{(ax+b)^{{n+1}}}}{{a(n+1)}} + C\\)", f"\\(= \\dfrac{{({L(a * x + b)})^{{{m + 1}}}}}{{{a * (m + 1)}}} + C\\)"],
        "For a linear inner function, divide by the coefficient of \\(x\\) as well as the new index.",
        "Check by differentiating your answer.",
        common_errors=[err((a * x + b) ** (m + 1) / (m + 1), "conceptual", "You forgot to divide by the coefficient of \\(x\\) (the reverse chain rule factor).")],
    )


def t_3F(r: random.Random, d: int) -> Generated:
    kk = r.randint(2, 6)
    f = x**2 - kk * x
    area = sp.Rational(kk**3, 6)
    return Generated(
        f"Find the area enclosed between the curve \\(y = {L(f)}\\) and the \\(x\\)-axis.",
        {"type": "num", "value": ex(area), "tol": 0, "units": "units^2"}, 3, d,
        [f"The curve cuts the \\(x\\)-axis at \\(x = 0\\) and \\(x = {kk}\\), and lies below the axis between them.",
         f"\\(\\displaystyle\\int_0^{{{kk}}} ({L(f)})\\,dx = {L(-area)}\\)", f"Area \\(= {L(area)}\\) square units."],
        "Area is always positive: an integral below the axis is negative, so take its absolute value.",
        "Sketch first to see where the region lies relative to the axis.",
        common_errors=[err(-area, "interpretation", "An area cannot be negative: the region is below the axis, so take the absolute value.")],
    )


def t_3G(r: random.Random, d: int) -> Generated:
    h = r.choice([1, 2, sp.Rational(1, 2)])
    ys = [r.randint(1, 12) for _ in range(5)]
    est = sp.Rational(1, 2) * h * (ys[0] + 2 * sum(ys[1:-1]) + ys[-1])
    xs = [i * h for i in range(5)]
    table = " & ".join(L(v) for v in xs) + " \\\\ \\hline " + " & ".join(str(v) for v in ys)
    return Generated(
        f"Use the trapezoidal rule with the five function values below to estimate \\(\\displaystyle\\int_{{0}}^{{{L(4 * h)}}} f(x)\\,dx\\).\n\n\\[\\begin{{array}}{{c|ccccc}} x & {table.split(' \\\\ ')[0]} \\\\ \\hline f(x) & {' & '.join(str(v) for v in ys)}\\end{{array}}\\]",
        {"type": "num", "value": ex(est), "tol": 0}, 2, d,
        [f"\\(h = {L(h)}\\).", f"\\(\\dfrac{{h}}{{2}}\\left[y_0 + 2(y_1 + y_2 + y_3) + y_4\\right] = \\dfrac{{{L(h)}}}{{2}}\\left[{ys[0]} + 2({ys[1]} + {ys[2]} + {ys[3]}) + {ys[4]}\\right] = {L(est)}\\)."],
        "The trapezoidal rule approximates the area by trapezia: ends count once, interior values twice.",
        "Write the formula with the values substituted before calculating.",
    )


def t_3H(r: random.Random, d: int) -> Generated:
    c, m = r.randint(1, 6), r.randint(2, 5)
    F = (x**2 + c) ** (m + 1) / (m + 1)
    return Generated(
        f"Find \\(\\displaystyle\\int 2x(x^2 + {c})^{{{m}}}\\,dx\\).",
        {"type": "antiderivative", "value": ex(F), "var": "x"}, 2, d,
        [f"The integrand has the form \\(f'(x)[f(x)]^n\\) with \\(f(x) = x^2 + {c}\\).", f"\\(\\int f'(x)[f(x)]^n\\,dx = \\dfrac{{[f(x)]^{{n+1}}}}{{n+1}} + C = \\dfrac{{(x^2 + {c})^{{{m + 1}}}}}{{{m + 1}}} + C\\)."],
        "The reverse chain rule: spot an inner function whose derivative is already a factor.",
        "Differentiate your answer to check it.",
    )


# ------------------------------------------------------------- Chapters 4–6 ---
def t_4B(r: random.Random, d: int) -> Generated:
    a = r.choice([2, 3, -2, 4, -1])
    f = x * sp.exp(a * x)
    fd = sp.diff(f, x)
    return Generated(
        f"Differentiate \\(y = {L(f)}\\).",
        {"type": "expr", "value": ex(fd), "vars": ["x"]}, 2, d,
        ["Product rule with \\(u = x\\), \\(v = e^{" + str(a) + "x}\\).", f"\\(y' = e^{{{a}x}} + {a}xe^{{{a}x}} = {L(sp.factor(fd))}\\)."],
        "\\(\\frac{d}{dx}e^{ax} = ae^{ax}\\); products need the product rule.",
        "Factorise your derivative: later parts usually need it.",
        common_errors=[err(sp.exp(a * x), "conceptual", "You only differentiated one factor: use the product rule \\(u'v + uv'\\).")],
    )


t_4C = t_4B


def t_4D(r: random.Random, d: int) -> Generated:
    a = r.choice([1, 2, 3])
    val = (sp.exp(a) - 1) / a
    return Generated(
        f"Find the exact value of \\(\\displaystyle\\int_0^1 e^{{{a}x}}\\,dx\\).",
        {"type": "num", "value": ex(val), "tol": 0}, 2, d,
        [f"\\(\\int e^{{{a}x}}\\,dx = \\dfrac{{e^{{{a}x}}}}{{{a}}}\\).", f"\\(\\left[\\dfrac{{e^{{{a}x}}}}{{{a}}}\\right]_0^1 = {L(val)}\\)."],
        "\\(\\int e^{ax}dx = \\frac{1}{a}e^{ax} + C\\).",
        "'Exact value' means leave \\(e\\) in the answer — no decimals.",
        common_errors=[err(sp.exp(a) / a, "careless error", "You forgot to subtract the value at the lower limit (\\(e^0 = 1\\)).")],
    )


t_4E = t_4D


def t_4A(r: random.Random, d: int) -> Generated:
    a, b = r.randint(2, 5), r.randint(1, 4)
    f = sp.exp(a * x + b)
    return Generated(
        f"Find the gradient of the tangent to \\(y = {L(f)}\\) at the point where \\(x = 0\\). Give an exact answer.",
        {"type": "num", "value": ex(a * sp.exp(b)), "tol": 0}, 2, d,
        [f"\\(y' = {a}e^{{{a}x + {b}}}\\)", f"At \\(x = 0\\): \\(y' = {a}e^{{{b}}}\\)."],
        "The derivative of \\(e^{f(x)}\\) is \\(f'(x)e^{f(x)}\\).",
        "Leave answers in exact form when asked.",
    )


def t_4F(r: random.Random, d: int) -> Generated:
    a = r.choice([2, 3, 5, 10])
    return Generated(
        f"Differentiate \\(y = {a}^x\\).",
        {"type": "expr", "value": f"{a}**x*log({a})", "vars": ["x"]}, 1, d,
        [f"\\({a}^x = e^{{x\\ln {a}}}\\), so \\(y' = \\ln {a}\\cdot e^{{x\\ln {a}}} = {a}^x \\ln {a}\\)."],
        "\\(\\frac{d}{dx}a^x = a^x \\ln a\\), because \\(a^x = e^{x \\ln a}\\).",
        "Rewrite other bases as base \\(e\\) if you forget the rule.",
        common_errors=[err(x * a ** (x - 1), "conceptual", "The power rule applies to \\(x^n\\), not \\(a^x\\).")],
    )


def t_5B(r: random.Random, d: int) -> Generated:
    a, b = r.randint(2, 7), r.randint(1, 9)
    f = sp.log(a * x + b)
    return Generated(
        f"Differentiate \\(y = \\ln({L(a * x + b)})\\).",
        {"type": "expr", "value": ex(sp.diff(f, x)), "vars": ["x"]}, 1, d,
        [f"\\(\\frac{{d}}{{dx}}\\ln f(x) = \\dfrac{{f'(x)}}{{f(x)}}\\), so \\(y' = \\dfrac{{{a}}}{{{L(a * x + b)}}}\\)."],
        "\\(\\frac{d}{dx}\\ln f(x) = \\frac{f'(x)}{f(x)}\\).",
        "Don't forget the inner derivative in the numerator.",
        common_errors=[err(1 / (a * x + b), "conceptual", "Missing the chain-rule factor: the numerator is the derivative of the inside.")],
    )


t_5A = t_5B
t_5C = t_5B


def t_5D(r: random.Random, d: int) -> Generated:
    a, b = r.randint(2, 5), r.randint(1, 5)
    val = sp.log(sp.Rational(a + b, b)) / a
    return Generated(
        f"Find the exact value of \\(\\displaystyle\\int_0^1 \\frac{{1}}{{{L(a * x + b)}}}\\,dx\\).",
        {"type": "num", "value": ex(val), "tol": 0}, 3, d,
        [f"\\(\\int \\dfrac{{dx}}{{{L(a * x + b)}}} = \\dfrac{{1}}{{{a}}}\\ln({L(a * x + b)})\\)", f"\\(= \\dfrac{{1}}{{{a}}}(\\ln {a + b} - \\ln {b}) = \\dfrac{{1}}{{{a}}}\\ln\\dfrac{{{a + b}}}{{{b}}}\\)."],
        "\\(\\int \\frac{1}{ax+b}dx = \\frac{1}{a}\\ln|ax+b| + C\\).",
        "Combine logarithms with log laws for the final exact form.",
    )


t_5E = t_5D


def t_5F(r: random.Random, d: int) -> Generated:
    a = r.choice([2, 3, 10])
    return Generated(
        f"Differentiate \\(y = \\log_{{{a}}} x\\).",
        {"type": "expr", "value": f"1/(x*log({a}))", "vars": ["x"]}, 1, d,
        [f"\\(\\log_{{{a}}} x = \\dfrac{{\\ln x}}{{\\ln {a}}}\\), so \\(y' = \\dfrac{{1}}{{x\\ln {a}}}\\)."],
        "Change of base turns any logarithm into a constant multiple of \\(\\ln x\\).",
        "Write the change-of-base line: it shows the method.",
    )


def t_6A(r: random.Random, d: int) -> Generated:
    A, kk = r.randint(2, 5), r.choice([2, 3, 4, sp.Rational(1, 2)])
    per = 2 * sp.pi / kk
    return Generated(
        f"State the period of \\(y = {A}\\sin({L(kk * x)})\\).",
        {"type": "expr", "value": ex(per), "vars": []}, 1, d,
        [f"Period \\(= \\dfrac{{2\\pi}}{{n}} = \\dfrac{{2\\pi}}{{{L(kk)}}} = {L(per)}\\)."],
        "For \\(y = a\\sin(nx)\\), the amplitude is \\(|a|\\) and the period is \\(\\frac{2\\pi}{n}\\).",
        "Keep answers in terms of \\(\\pi\\).",
        common_errors=[err(2 * sp.pi * kk, "formula selection", "You multiplied by \\(n\\) instead of dividing.")],
    )


def t_6B(r: random.Random, d: int) -> Generated:
    kk = r.randint(2, 5)
    f = x * sp.sin(kk * x)
    return Generated(
        f"Differentiate \\(y = {L(f)}\\).",
        {"type": "expr", "value": ex(sp.diff(f, x)), "vars": ["x"]}, 2, d,
        [f"Product rule: \\(y' = \\sin {kk}x + x\\cdot {kk}\\cos {kk}x\\)."],
        "\\(\\frac{d}{dx}\\sin(kx) = k\\cos(kx)\\).",
        "Name \\(u\\) and \\(v\\) when using the product rule.",
    )


t_6C = t_6B


def t_6D(r: random.Random, d: int) -> Generated:
    kk = r.randint(2, 6)
    val = sp.integrate(sp.cos(kk * x), (x, 0, sp.pi / (2 * kk)))
    return Generated(
        f"Evaluate \\(\\displaystyle\\int_0^{{\\frac{{\\pi}}{{{2 * kk}}}}} \\cos {kk}x\\,dx\\).",
        {"type": "num", "value": ex(val), "tol": 0}, 2, d,
        [f"\\(\\left[\\dfrac{{\\sin {kk}x}}{{{kk}}}\\right]_0^{{\\pi/{2 * kk}}} = \\dfrac{{1}}{{{kk}}}(\\sin\\tfrac{{\\pi}}{{2}} - 0) = {L(val)}\\)."],
        "\\(\\int \\cos(kx)dx = \\frac{1}{k}\\sin(kx) + C\\).",
        "Calculator in radians!",
    )


t_6E = t_6D


# ----------------------------------------------------------------- Chapter 7 ---
def t_7A(r: random.Random, d: int) -> Generated:
    a, b = r.randint(1, 6), r.randint(1, 9)
    X = t**3 - a * t**2 + b * t
    c = r.randint(1, 4)
    acc = sp.diff(X, t, 2).subs(t, c)
    return Generated(
        f"A particle moves along a line so that its displacement is \\(x = {L(X)}\\) metres at time \\(t\\) seconds. Find its acceleration when \\(t = {c}\\) (in m/s²).",
        {"type": "num", "value": ex(acc), "tol": 0, "units": "m/s^2"}, 2, d,
        [f"\\(v = \\dot{{x}} = {L(sp.diff(X, t))}\\)", f"\\(a = \\ddot{{x}} = {L(sp.diff(X, t, 2))}\\)", f"At \\(t = {c}\\): \\(a = {acc}\\) m/s²."],
        "Velocity is the derivative of displacement; acceleration is the derivative of velocity.",
        "Include units in motion answers.",
        common_errors=[err(sp.diff(X, t).subs(t, c), "interpretation", "That is the velocity at that time, not the acceleration.")],
    )


def t_7B(r: random.Random, d: int) -> Generated:
    a, b, x0 = r.randint(1, 4), r.randint(1, 6), r.randint(-3, 5)
    v = 3 * a * t**2 + b
    X = sp.integrate(v, t) + x0
    T = r.randint(1, 3)
    return Generated(
        f"A particle has velocity \\(v = {L(v)}\\) m/s and is initially at \\(x = {x0}\\) m. Find its displacement when \\(t = {T}\\).",
        {"type": "num", "value": ex(X.subs(t, T)), "tol": 0, "units": "m"}, 3, d,
        [f"\\(x = \\int v\\,dt = {L(sp.integrate(v, t))} + C\\).", f"\\(t = 0, x = {x0}\\) gives \\(C = {x0}\\).", f"\\(x({T}) = {X.subs(t, T)}\\) m."],
        "Integrating velocity gives displacement up to a constant found from initial conditions.",
        "Never drop the constant of integration in motion problems.",
        common_errors=[err(sp.integrate(v, t).subs(t, T), "incomplete reasoning", "You left out the constant: the particle did not start at the origin.")],
    )


t_7C = t_7A
t_7D = t_7B


def t_7E(r: random.Random, d: int) -> Generated:
    N0 = r.choice([200, 500, 1000, 1500])
    T2 = r.choice([3, 4, 5, 6, 8])
    kk = sp.log(2) / T2
    T = r.choice([10, 12, 15, 20])
    NT = N0 * 2 ** sp.Rational(T, T2)
    return Generated(
        f"A population grows according to \\(N = {N0}e^{{kt}}\\), where \\(t\\) is in hours. It doubles every {T2} hours. Find the population after {T} hours, to the nearest whole number.",
        {"type": "num", "value": str(int(sp.floor(NT + sp.Rational(1, 2)))), "tol": 1}, 3, d,
        [f"\\({2 * N0} = {N0}e^{{{T2}k}}\\) gives \\(k = \\dfrac{{\\ln 2}}{{{T2}}}\\).", f"\\(N({T}) = {N0}e^{{{T}\\ln 2/{T2}}} = {N0}\\times 2^{{{L(sp.Rational(T, T2))}}} \\approx {float(NT):.1f}\\)."],
        "Exponential growth \\(N = N_0e^{kt}\\); doubling time gives \\(k = \\frac{\\ln 2}{T}\\).",
        "Keep \\(k\\) exact until the final step to avoid rounding error.",
    )


# ----------------------------------------------------------------- Chapter 8 ---
def t_8A(r: random.Random, d: int) -> Generated:
    first, inc, rows = r.randint(15, 30), r.randint(2, 4), r.randint(15, 30)
    total = sp.Rational(rows, 2) * (2 * first + (rows - 1) * inc)
    return Generated(
        f"A theatre has {first} seats in the front row and each row has {inc} more seats than the row in front. There are {rows} rows. How many seats are there in total?",
        {"type": "num", "value": ex(total), "tol": 0}, 2, d,
        [f"AP: \\(a = {first}\\), \\(d = {inc}\\), \\(n = {rows}\\).", f"\\(S_{{{rows}}} = \\dfrac{{{rows}}}{{2}}(2\\times{first} + {rows - 1}\\times{inc}) = {total}\\)."],
        "Recognise the model: a constant increase is an arithmetic sequence.",
        "Define \\(a\\), \\(d\\) and \\(n\\) in words before calculating.",
    )


def t_8B(r: random.Random, d: int) -> Generated:
    a, ratio, bound = r.choice([2, 5, 10]), r.choice([sp.Rational(11, 10), sp.Rational(6, 5), sp.Rational(3, 2)]), r.choice([100, 500, 1000])
    nn = 1
    while a * ratio ** (nn - 1) <= bound:
        nn += 1
    return Generated(
        f"A geometric sequence has first term {a} and ratio {L(ratio)}. Use logarithms to find the first term of the sequence that exceeds {bound}; give its term number.",
        {"type": "num", "value": str(nn), "tol": 0}, 3, d,
        [f"\\({a}({L(ratio)})^{{n-1}} > {bound}\\)", f"\\(n - 1 > \\dfrac{{\\ln({L(sp.Rational(bound, a))})}}{{\\ln({L(ratio)})}} \\approx {float(sp.log(sp.Rational(bound, a)) / sp.log(ratio)):.3f}\\)", f"\\(n = {nn}\\)."],
        "Logarithms bring the unknown index down: \\(\\ln(r^{n-1}) = (n-1)\\ln r\\).",
        "If \\(r<1\\), dividing by \\(\\ln r\\) reverses the inequality.",
    )


def t_8C(r: random.Random, d: int) -> Generated:
    P = r.choice([2000, 5000, 8000, 10000, 15000])
    rate = r.choice([3, 4, 4.5, 5, 6])
    yrs = r.randint(3, 10)
    comp = r.choice([("annually", 1), ("monthly", 12), ("quarterly", 4)])
    A = P * (1 + rate / 100 / comp[1]) ** (yrs * comp[1])
    return Generated(
        f"${P} is invested at {rate}% p.a. compounded {comp[0]} for {yrs} years. Find the final amount, correct to the nearest cent.",
        {"type": "num", "value": f"{A:.2f}", "tol": 0.01, "units": "$"}, 2, d,
        [f"\\(A = P(1 + r)^n\\) with \\(r = \\dfrac{{{rate}\\%}}{{{comp[1]}}}\\) per period and \\(n = {yrs * comp[1]}\\) periods.", f"\\(A = {P}\\left(1 + \\dfrac{{{rate / 100}}}{{{comp[1]}}}\\right)^{{{yrs * comp[1]}}} \\approx \\${A:,.2f}\\)."],
        "Compound interest grows geometrically; the rate and number of periods must match the compounding period.",
        "Convert the annual rate to the period rate before substituting.",
        common_errors=[err(round(P * (1 + rate / 100) ** yrs, 2), "formula selection", "You compounded annually: convert to the compounding period.")],
    )


def t_8D(r: random.Random, d: int) -> Generated:
    M = r.choice([100, 200, 250, 500])
    rate = r.choice([0.06, 0.05, 0.04])
    yrs = r.choice([5, 10, 20])
    i_ = rate / 12
    nper = yrs * 12
    FV = M * ((1 + i_) ** nper - 1) / i_
    return Generated(
        f"${M} is deposited at the end of each month into an account earning {rate * 100:g}% p.a. interest compounded monthly. Find the value of the account after {yrs} years, to the nearest dollar.",
        {"type": "num", "value": f"{FV:.0f}", "tol": 1, "units": "$"}, 3, d,
        [f"Monthly rate \\(r = {rate}/12\\), \\(n = {nper}\\) deposits.", "The balance is a GP sum: \\(A = M\\dfrac{(1+r)^n - 1}{r}\\).", f"\\(A \\approx \\${FV:,.0f}\\)."],
        "Regular end-of-period deposits form a geometric series of compounded amounts.",
        "In HSC questions, develop the series for the first few deposits before summing.",
    )


def t_8E(r: random.Random, d: int) -> Generated:
    P = r.choice([20000, 30000, 50000])
    rate = r.choice([0.06, 0.072, 0.09])
    yrs = r.choice([3, 4, 5])
    i_ = rate / 12
    nper = yrs * 12
    Mrep = P * i_ * (1 + i_) ** nper / ((1 + i_) ** nper - 1)
    return Generated(
        f"A loan of ${P} is repaid in equal monthly instalments over {yrs} years. Interest is {rate * 100:g}% p.a. compounded monthly. Find the monthly instalment, to the nearest cent.",
        {"type": "num", "value": f"{Mrep:.2f}", "tol": 0.01, "units": "$"}, 4, 3,
        [f"After \\(n\\) months the balance is \\(A_n = P(1+r)^n - M\\dfrac{{(1+r)^n - 1}}{{r}}\\) with \\(r = {i_:.4f}\\).", f"Set \\(A_{{{nper}}} = 0\\): \\(M = \\dfrac{{Pr(1+r)^n}}{{(1+r)^n - 1}} \\approx \\${Mrep:,.2f}\\)."],
        "A loan balance is the compounded principal minus the compounded repayments (a GP sum).",
        "Derive \\(A_1, A_2, A_3\\) first in HSC questions; the general form follows from the pattern.",
    )


t_8F = t_8D


# ------------------------------------------------------------- Chapters 9–10 ---
def t_9B(r: random.Random, d: int) -> Generated:
    xs = sorted(r.sample(range(0, 6), 4))
    weights = [r.randint(1, 4) for _ in xs]
    tot = sum(weights)
    ps = [sp.Rational(w, tot) for w in weights]
    E = sum(a * p for a, p in zip(xs, ps))
    table = " & ".join(str(v) for v in xs)
    ptab = " & ".join(L(p) for p in ps)
    return Generated(
        f"A discrete random variable \\(X\\) has the distribution\n\n\\[\\begin{{array}}{{c|cccc}} x & {table} \\\\ \\hline P(X=x) & {ptab}\\end{{array}}\\]\n\nFind \\(E(X)\\).",
        {"type": "num", "value": ex(E), "tol": 0}, 2, d,
        ["\\(E(X) = \\sum x\\,P(X=x)\\)", f"\\(= {' + '.join(f'{a}\\times{L(p)}' for a, p in zip(xs, ps))} = {L(E)}\\)."],
        "The expected value is the probability-weighted mean of the outcomes.",
        "Check the probabilities sum to 1 first.",
    )


def t_9C(r: random.Random, d: int) -> Generated:
    xs = [0, 1, 2]
    ps = r.choice([[sp.Rational(1, 4), sp.Rational(1, 2), sp.Rational(1, 4)], [sp.Rational(1, 5), sp.Rational(2, 5), sp.Rational(2, 5)], [sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(1, 6)]])
    E = sum(a * p for a, p in zip(xs, ps))
    V = sum(a**2 * p for a, p in zip(xs, ps)) - E**2
    return Generated(
        f"\\(X\\) takes values 0, 1, 2 with probabilities \\({L(ps[0])}, {L(ps[1])}, {L(ps[2])}\\) respectively. Find \\(\\operatorname{{Var}}(X)\\).",
        {"type": "num", "value": ex(V), "tol": 0}, 3, d,
        [f"\\(E(X) = {L(E)}\\)", f"\\(E(X^2) = {L(sum(a**2 * p for a, p in zip(xs, ps)))}\\)", f"\\(\\operatorname{{Var}}(X) = E(X^2) - [E(X)]^2 = {L(V)}\\)."],
        "\\(\\operatorname{Var}(X) = E(X^2) - [E(X)]^2\\).",
        "Square the mean, not the probabilities.",
        common_errors=[err(sum(a**2 * p for a, p in zip(xs, ps)), "incomplete reasoning", "That is \\(E(X^2)\\); subtract \\([E(X)]^2\\).")],
    )


t_9A = t_9B


def t_10B(r: random.Random, d: int) -> Generated:
    a = r.choice([2, 3, 4, 5])
    kk_ = sp.Rational(2, a**2)
    return Generated(
        f"The function \\(f(x) = kx\\) for \\(0 \\le x \\le {a}\\) (and 0 otherwise) is a probability density function. Find \\(k\\).",
        {"type": "num", "value": ex(kk_), "tol": 0}, 2, d,
        [f"\\(\\displaystyle\\int_0^{{{a}}} kx\\,dx = 1\\)", f"\\(k\\cdot\\dfrac{{{a}^2}}{{2}} = 1\\), so \\(k = {L(kk_)}\\)."],
        "A probability density function is non-negative and has total area 1.",
        "State both conditions when asked to 'show' something is a pdf.",
    )


t_10A = t_10B
t_10C = t_10B


def t_10D(r: random.Random, d: int) -> Generated:
    mu, sigma = r.choice([50, 60, 70, 100]), r.choice([5, 8, 10, 15])
    z = r.choice([-2, -1, 1, 2, sp.Rational(3, 2), sp.Rational(-1, 2)])
    xv = mu + z * sigma
    return Generated(
        f"A test has mean {mu} and standard deviation {sigma}. Find the \\(z\\)-score of a result of \\({L(xv)}\\).",
        {"type": "num", "value": ex(z), "tol": 0}, 1, 1,
        [f"\\(z = \\dfrac{{x - \\mu}}{{\\sigma}} = \\dfrac{{{L(xv)} - {mu}}}{{{sigma}}} = {L(z)}\\)."],
        "A \\(z\\)-score counts standard deviations from the mean.",
        "Keep the sign: below the mean gives a negative \\(z\\)-score.",
        common_errors=[err(-z, "sign", "Sign error: subtract the mean from the score, not the reverse.")],
    )


def t_10E(r: random.Random, d: int) -> Generated:
    mu, sigma = r.choice([160, 170, 50, 75]), r.choice([4, 5, 6, 10])
    lo, hi = mu - 2 * sigma, mu + sigma
    pct = sp.Rational(815, 10)  # 47.5 + 34
    return Generated(
        f"Heights are normally distributed with mean {mu} and standard deviation {sigma}. Using the empirical rule (68–95–99.7), estimate the percentage of heights between {lo} and {hi}.",
        {"type": "num", "value": "81.5", "tol": 0.05, "units": "%"}, 2, d,
        [f"\\({lo}\\) is \\(z = -2\\) and \\({hi}\\) is \\(z = 1\\).", "Between \\(z=-2\\) and 0: 47.5%. Between 0 and \\(z = 1\\): 34%.", f"Total \\(\\approx {float(pct)}\\%\\)."],
        "The empirical rule: about 68%, 95% and 99.7% lie within 1, 2 and 3 standard deviations of the mean.",
        "Draw the bell curve and shade the region before adding percentages.",
    )


t_10F = t_10E


# ---------------------------------------------------------------- Year 11 -------
def t_Y11_FUNC(r: random.Random, d: int) -> Generated:
    p, q = r.randint(-6, 6), r.randint(-6, 6)
    while p == q:
        q = r.randint(-6, 6)
    a = r.choice([1, 2, 3])
    f = sp.expand(a * (x - p) * (x - q))
    return Generated(
        f"Solve \\({L(f)} = 0\\). Enter the solutions as a list.",
        {"type": "set", "values": [str(p), str(q)]}, 2, 1,
        [f"\\({L(f)} = {L(sp.factor(f))} = 0\\)", f"\\(x = {p}\\) or \\(x = {q}\\)."],
        "A product is zero when one of its factors is zero.",
        "Take out the common factor first.",
    )


def t_Y11_EXPLOG(r: random.Random, d: int) -> Generated:
    b = r.choice([2, 3, 5])
    m1, m2 = r.randint(2, 5), r.randint(1, 3)
    val = m1 + m2
    return Generated(
        f"Evaluate \\(\\log_{{{b}}} {b**m1 * b**m2 // b**m2 * 1} + \\log_{{{b}}} {b**m2}\\) without a calculator.",
        {"type": "num", "value": str(val), "tol": 0}, 1, 1,
        [f"\\(\\log_{{{b}}} {b**m1} = {m1}\\) and \\(\\log_{{{b}}} {b**m2} = {m2}\\).", f"Sum \\(= {val}\\)."],
        "\\(\\log_b b^n = n\\); and \\(\\log_b x + \\log_b y = \\log_b xy\\).",
        "Write each number as a power of the base.",
    )


def t_Y11_TRIG(r: random.Random, d: int) -> Generated:
    choices = [("\\sin\\frac{\\pi}{3}", "sqrt(3)/2"), ("\\cos\\frac{\\pi}{4}", "sqrt(2)/2"), ("\\tan\\frac{\\pi}{6}", "sqrt(3)/3"),
               ("\\cos\\frac{2\\pi}{3}", "-1/2"), ("\\sin\\frac{5\\pi}{4}", "-sqrt(2)/2"), ("\\tan\\frac{3\\pi}{4}", "-1")]
    expr, val = r.choice(choices)
    return Generated(
        f"Find the exact value of \\({expr}\\).",
        {"type": "num", "value": val, "tol": 0}, 1, 1,
        ["Use the related acute angle and the ASTC rule for the sign.", f"\\({expr} = {L(sp.sympify(val))}\\)."],
        "Exact values come from the 30°–60°–90° and 45°–45°–90° triangles; the quadrant fixes the sign.",
        "Draw the unit circle quadrant to check the sign.",
    )


def t_Y11_CALC(r: random.Random, d: int) -> Generated:
    a, b, c = r.randint(1, 5), r.randint(-6, 6), r.randint(2, 6)
    f = a * x**c + b * x
    m = r.randint(-2, 2)
    return Generated(
        f"Find the gradient of the tangent to \\(y = {L(f)}\\) at \\(x = {m}\\).",
        {"type": "num", "value": ex(sp.diff(f, x).subs(x, m)), "tol": 0}, 2, 1,
        [f"\\(y' = {L(sp.diff(f, x))}\\)", f"At \\(x = {m}\\): \\(y' = {sp.diff(f, x).subs(x, m)}\\)."],
        "The derivative gives the gradient of the tangent.",
        "Substitute only after differentiating.",
    )


def t_Y11_PROB(r: random.Random, d: int) -> Generated:
    p1, p2 = r.choice([sp.Rational(1, 2), sp.Rational(1, 3), sp.Rational(2, 5)]), r.choice([sp.Rational(1, 4), sp.Rational(3, 4), sp.Rational(1, 6)])
    ans = 1 - (1 - p1) * (1 - p2)
    return Generated(
        f"Events \\(A\\) and \\(B\\) are independent with \\(P(A) = {L(p1)}\\) and \\(P(B) = {L(p2)}\\). Find \\(P(A \\cup B)\\).",
        {"type": "num", "value": ex(ans), "tol": 0}, 2, 1,
        [f"\\(P(A\\cap B) = P(A)P(B) = {L(p1 * p2)}\\)", f"\\(P(A\\cup B) = P(A) + P(B) - P(A\\cap B) = {L(ans)}\\)."],
        "For independent events \\(P(A\\cap B) = P(A)P(B)\\); the addition rule removes the overlap.",
        "Write the addition rule before substituting.",
        common_errors=[err(p1 + p2, "conceptual", "You added without subtracting the overlap \\(P(A\\cap B)\\).")],
    )


def t_Y11_TRANS(r: random.Random, d: int) -> Generated:
    h, kk_ = r.randint(-5, 5), r.randint(-5, 5)
    g = (x - h) ** 2 + kk_
    return Generated(
        f"The parabola \\(y = x^2\\) is translated so that its vertex is at \\(({h}, {kk_})\\). Write the equation of the new parabola (enter the right-hand side).",
        {"type": "expr", "value": ex(g), "vars": ["x"]}, 1, 1,
        [f"Replace \\(x\\) by \\(x - ({h})\\) and add {kk_}: \\(y = {L(g)}\\)."],
        "\\(y = f(x - h) + k\\) translates the graph \\(h\\) right and \\(k\\) up.",
        "Check by substituting the vertex.",
    )


TEMPLATES: dict[str, Callable[[random.Random, int], Generated]] = {
    name[2:].replace("_", "-") if name.startswith("t_Y11") else name[2:]: fn
    for name, fn in list(globals().items())
    if name.startswith("t_") and callable(fn)
}
# Learning-plan codes for Year 11 items are "Y11-FUNC" etc.
TEMPLATES = {("Y11-" + kk[4:] if kk.startswith("Y11-") else kk): fn for kk, fn in TEMPLATES.items()}


def generate(code: str, seed: int, difficulty: int) -> Generated | None:
    fn = TEMPLATES.get(code)
    if fn is None:
        return None
    rng = random.Random(f"{code}:{seed}:{difficulty}")
    return fn(rng, difficulty)


def minutes_for(marks: int) -> float:
    return _minutes(marks)
