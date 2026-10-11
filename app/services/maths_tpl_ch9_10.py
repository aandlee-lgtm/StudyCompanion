"""Chapters 9 and 10 — Discrete and continuous probability distributions (owner: maths).

Discrete answers are exact fractions or terminating decimals. Normal-distribution questions quote the
standard normal probabilities they need (\\(P(Z \\le z)\\) to 4 decimal places, as read from a table)
so every answer is a deterministic combination of the quoted values; a small tolerance accepts the
same result from a calculator. ``params`` let the test-suite recompute every answer independently."""
from __future__ import annotations

import itertools
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import mpmath as mp
import sympy as sp

from app.services.maths_tpl_base import (
    A_approx, A_expr, A_num, A_parts, A_round, A_set, Generated, L, P, Rng, co, cp, err, ex, multipart, pick, pn, rnd, x,
)

PI = "probability interpretation"
EV = "expected value and variance"
ND = "normal distribution"
IR = "integration rules"
Q = sp.Rational
PTOL = 0.0006  # accepts a calculator value in place of the 4-decimal-place table values


# ------------------------------------------------------------------ helpers ---
def dstr(q) -> str:
    """An exact rational as a terminating decimal string when it is one ('0.35'), else 'p/q'."""
    q = sp.Rational(q)
    den = int(q.q)
    while den % 2 == 0:
        den //= 2
    while den % 5 == 0:
        den //= 5
    if den != 1:
        return f"{q.p}/{q.q}"
    s = format((Decimal(int(q.p)) / Decimal(int(q.q))).normalize(), "f")
    return "0" if s in ("-0", "") else s


def dl(q) -> str:
    """LaTeX for an exact value: a decimal when it terminates, else a fraction."""
    s = dstr(q)
    return L(sp.Rational(q)) if "/" in s else s


def pdl(q) -> str:
    """dl() bracketed when negative, for substitution lines."""
    return f"\\left({dl(q)}\\right)" if sp.Rational(q) < 0 else dl(q)


def phi4(z) -> sp.Rational:
    """P(Z <= z) rounded half-up to 4 decimal places, as a standard normal table gives it."""
    with mp.workdps(40):
        v = mp.ncdf(mp.mpf(str(sp.Rational(z).p)) / int(sp.Rational(z).q))
        d = Decimal(mp.nstr(v, 30)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return sp.Rational(str(d))


def zt(z) -> str:
    """A z-value to 2 decimal places, as written in a table."""
    return f"{float(sp.Rational(z)):.2f}"


def given(*zs) -> str:
    vals = sorted(set(sp.Rational(z) for z in zs))
    return "Use " + " and ".join(f"\\(P(Z \\le {zt(z)}) = {dstr(phi4(z))}\\)" for z in vals) + "."


def dtable(xs, cells, var: str = "x", X: str = "X") -> str:
    head = " & ".join(L(sp.sympify(v)) for v in xs)
    return (f"\\[\\begin{{array}}{{c|{'c' * len(xs)}}} {var} & {head} \\\\ \\hline P({X} = {var}) & "
            f"{' & '.join(cells)} \\end{{array}}\\]")


def wsum(xs, ps, sq: bool = False, frac: bool = False) -> str:
    """'0\\times 0.1 + 1\\times 0.3 + …' with brackets for negative values (fractions with frac=True)."""
    out = []
    for v, p in zip(xs, ps):
        base = f"{pn(v)}^2" if sq else pn(v)
        out.append(f"{base}\\times {L(p) if frac else dl(p)}")
    return " + ".join(out)


def kcell(c, power: int = 1) -> str:
    sym = "k" if power == 1 else "k^2"
    return sym if c == 1 else f"{c}{sym}"


def weights(r: Rng, m: int, total: int) -> list[int]:
    """m positive integers summing to total."""
    cuts = sorted(r.sample(range(1, total), m - 1))
    return [b - a for a, b in zip([0] + cuts, cuts + [total])]


def E_(xs, ps):
    return sum(sp.Rational(v) * p for v, p in zip(xs, ps))


def E2_(xs, ps):
    return sum(sp.Rational(v) ** 2 * p for v, p in zip(xs, ps))


# ======================================================================= 9A ===
def _k_quadratic(r: Rng):
    """Cells c_i k (sum C) and one q k^2 with root k = 1/m: q = m(m - C)."""
    opts = [(m_, C) for m_ in range(3, 9) for C in range(2, m_) if m_ * (m_ - C) <= 12]
    m_, C = pick(r, opts)
    q = m_ * (m_ - C)
    parts = weights(r, min(3, C), C) if C >= 2 else [C]
    return m_, q, parts


def t_9A(r: Rng, d: int) -> Generated:
    if d == 1:
        start = pick(r, [0, 1, 2])
        if r.random() < 0.5:
            nv = r.randint(3, 5)
            xs = list(range(start, start + nv))
            cs = [r.randint(1, 4) for _ in xs]
            S_ = sum(cs)
            k_ = sp.Rational(1, S_)
            return Generated(
                "The discrete random variable \\(X\\) has the probability distribution\n\n"
                f"{dtable(xs, [kcell(c) for c in cs])}\n\nFind the value of \\(k\\).",
                A_num(k_), 1, 1,
                [f"The probabilities sum to 1: \\({' + '.join(kcell(c) for c in cs)} = 1\\).",
                 f"\\({S_}k = 1\\), so \\(k = {L(k_)}\\)."],
                "In any probability distribution every probability is between 0 and 1, and together they sum to 1.",
                "Add the entries in the probability row, set the sum equal to 1 and solve.",
                quicker=f"Check: with \\(k = {L(k_)}\\) the entries are {', '.join(f'\\({L(c * k_)}\\)' for c in cs)}, which add to 1.",
                common_errors=[err(S_, "algebraic", "algebra", f"From \\({S_}k = 1\\), divide by {S_}: \\(k = \\frac{{1}}{{{S_}}}\\).", step=2),
                               err(sp.Rational(1, len(xs)), "conceptual", PI, "The outcomes are not equally likely; use the condition that the probabilities sum to 1.", step=1)],
                skill="Use the sum of probabilities to find an unknown in a distribution.",
                params={"form": "k", "xs": xs, "cs": cs},
            )
        nv = r.randint(4, 5)
        xs = list(range(start, start + nv))
        ws = weights(r, nv, 20)
        ps = [sp.Rational(w, 20) for w in ws]
        j = r.randint(1, nv - 2)
        kind = pick(r, ["ge", "lt"])
        if kind == "ge":
            ans = sum(ps[j:])
            q_txt, wrong, wtxt = f"P(X \\ge {xs[j]})", sum(ps[j + 1:]), f"\\(X \\ge {xs[j]}\\) includes \\(X = {xs[j]}\\)."
        else:
            ans = sum(ps[:j + 1])
            q_txt, wrong, wtxt = f"P(X < {xs[j + 1]})", sum(ps[:j + 2]), f"\\(X < {xs[j + 1]}\\) does not include \\(X = {xs[j + 1]}\\)."
        return Generated(
            "The discrete random variable \\(X\\) has the probability distribution\n\n"
            f"{dtable(xs, [dl(p) for p in ps])}\n\nFind \\({q_txt}\\).",
            A_num(dstr(ans)), 1, 1,
            [f"List the values of \\(X\\) that satisfy the condition, then add their probabilities: \\({q_txt} = {dl(ans)}\\)."],
            "The probability of an event is the sum of the probabilities of the outcomes in it.",
            "Decide carefully whether the boundary value is included (\\(\\ge\\), \\(\\le\\)) or not (\\(>\\), \\(<\\)).",
            quicker="Use the complement when it has fewer terms: \\(P(A) = 1 - P(\\text{not } A)\\).",
            common_errors=[err(dstr(wrong), "interpretation", PI, wtxt, step=1),
                           err(dstr(1 - ans), "interpretation", PI, "That is the probability of the complement.", step=1)],
            skill="Read probabilities of events from a distribution table.",
            params={"form": "event", "xs": xs, "ws": ws, "j": j, "kind": kind},
        )
    if d == 2:
        m_, q, cs = _k_quadratic(r)
        start = pick(r, [0, 1])
        cells = [kcell(c) for c in cs]
        pos = r.randint(0, len(cs))
        cells.insert(pos, kcell(q, 2))
        xs = list(range(start, start + len(cells)))
        k_ = sp.Rational(1, m_)
        probs = [c * k_ for c in cs]
        probs.insert(pos, q * k_**2)
        j = r.randint(1, len(xs) - 1)
        ans = sum(probs[j:])
        C = sum(cs)
        other = sp.Rational(-m_, q)
        text = multipart(
            "The discrete random variable \\(X\\) has the probability distribution\n\n" + dtable(xs, cells),
            [("a", "Find the value of \\(k\\).", 2), ("b", f"Find \\(P(X \\ge {xs[j]})\\).", 1)])
        steps = [f"(a) The probabilities sum to 1: \\({q}k^2 + {C}k - 1 = 0\\).",
                 f"\\(({m_}k - 1)({co(m_ - C, 'k')} + 1) = 0\\), so \\(k = {L(k_)}\\) or \\(k = {L(other)}\\).",
                 f"A probability cannot be negative, so \\(k = {L(k_)}\\).",
                 f"(b) The probabilities are {', '.join(f'\\({L(p)}\\)' for p in probs)}; \\(P(X \\ge {xs[j]}) = {L(ans)}\\)."]
        return Generated(
            text, A_parts(P("a", 2, A_num(k_)), P("b", 1, A_num(ans))), 3, 2, steps,
            "The probabilities in a distribution sum to 1 and each lies between 0 and 1 — the second condition decides between the roots.",
            "Form the equation, solve the quadratic, then reject any root that gives a negative probability.",
            quicker="Substitute your \\(k\\) back: the row must add to exactly 1 with every entry between 0 and 1.",
            common_errors=[err(other, "incomplete reasoning", "domain/range", "A probability cannot be negative: reject that root.", step=3, part="a"),
                           err(sum(probs[j + 1:]), "interpretation", PI, f"\\(X \\ge {xs[j]}\\) includes \\(X = {xs[j]}\\).", step=4, part="b")],
            skill="Find an unknown in a distribution from the sum-to-one condition, rejecting impossible values.",
            params={"form": "kq", "xs": xs, "cs": cs, "q": q, "pos": pos, "j": j},
        )
    if r.random() < 0.5:
        R, B = r.randint(3, 7), r.randint(3, 7)
        T = R + B
        p0 = sp.Rational(B * (B - 1), T * (T - 1))
        p1 = sp.Rational(2 * R * B, T * (T - 1))
        p2 = sp.Rational(R * (R - 1), T * (T - 1))
        text = multipart(
            f"A bag contains {R} red and {B} blue marbles. Two marbles are drawn at random without replacement. "
            "Let \\(X\\) be the number of red marbles drawn.",
            [("a", "Find \\(P(X = 0)\\).", 1), ("b", "Find \\(P(X = 1)\\).", 2), ("c", "Find \\(P(X \\ge 1)\\).", 1),
             ("d", "Given that at least one red marble is drawn, find the probability that both are red.", 1)])
        steps = [f"(a) Both blue: \\(\\dfrac{{{B}}}{{{T}}}\\times\\dfrac{{{B - 1}}}{{{T - 1}}} = {L(p0)}\\).",
                 f"(b) Red then blue, or blue then red: \\(\\dfrac{{{R}}}{{{T}}}\\times\\dfrac{{{B}}}{{{T - 1}}} + \\dfrac{{{B}}}{{{T}}}\\times\\dfrac{{{R}}}{{{T - 1}}} = {L(p1)}\\).",
                 f"(c) \\(P(X \\ge 1) = 1 - P(X = 0) = {L(1 - p0)}\\).",
                 f"(d) \\(P(X = 2 \\mid X \\ge 1) = \\dfrac{{P(X = 2)}}{{P(X \\ge 1)}} = \\dfrac{{{L(p2)}}}{{{L(1 - p0)}}} = {L(p2 / (1 - p0))}\\)."]
        return Generated(
            text, A_parts(P("a", 1, A_num(p0)), P("b", 2, A_num(p1)), P("c", 1, A_num(1 - p0)), P("d", 1, A_num(p2 / (1 - p0)))), 5, 3, steps,
            "Without replacement the second draw depends on the first; a tree diagram gives the distribution of \\(X\\).",
            "Draw the tree; for 'exactly one' add both orders; for 'given that' divide by the probability of the condition.",
            quicker=f"Check \\(P(X = 0) + P(X = 1) + P(X = 2) = 1\\), with \\(P(X = 2) = {L(p2)}\\).",
            common_errors=[err(sp.Rational(B, T) ** 2, "conceptual", PI, "The marbles are not replaced: the second fraction has one fewer marble.", step=1, part="a"),
                           err(p1 / 2, "incomplete reasoning", PI, "There are two orders (red–blue and blue–red).", step=2, part="b"),
                           err(p2, "interpretation", PI, "That is \\(P(X = 2)\\); 'given that' means divide by \\(P(X \\ge 1)\\).", step=4, part="d")],
            skill="Build a probability distribution from a multi-stage experiment.",
            params={"form": "bag", "R": R, "B": B},
        )
    nd = pick(r, [4, 6, 8])
    m_ = r.randint(2, nd - 1)
    a2 = r.randint(2, nd)
    pa = sp.Rational(2 * a2 - 1, nd**2)
    pge = 1 - sp.Rational((m_ - 1) ** 2, nd**2)
    pcond = sp.Rational(2 * nd - 1, nd**2) / pge
    text = multipart(
        f"Two fair {nd}-sided dice, each numbered 1 to {nd}, are rolled. Let \\(X\\) be the larger of the two numbers (or the common number if they are equal).",
        [("a", f"Find \\(P(X = {a2})\\).", 1),
         ("b", f"Show that \\(P(X \\le k) = \\dfrac{{k^2}}{{{nd ** 2}}}\\) and hence find an expression for \\(P(X = k)\\) in terms of \\(k\\).", 2),
         ("c", f"Find \\(P(X \\ge {m_})\\).", 1),
         ("d", f"Given that \\(X \\ge {m_}\\), find the probability that \\(X = {nd}\\).", 1)])
    kk = sp.Symbol("k")
    steps = [f"(a) Outcomes with larger number {a2}: \\(({a2}, 1), \\ldots, ({a2}, {a2})\\) and \\((1, {a2}), \\ldots, ({a2 - 1}, {a2})\\): \\({2 * a2 - 1}\\) of the \\({nd ** 2}\\), so \\({L(pa)}\\).",
             f"(b) \\(X \\le k\\) means both dice show at most \\(k\\): \\(\\left(\\dfrac{{k}}{{{nd}}}\\right)^2 = \\dfrac{{k^2}}{{{nd ** 2}}}\\).",
             f"\\(P(X = k) = P(X \\le k) - P(X \\le k - 1) = \\dfrac{{k^2 - (k - 1)^2}}{{{nd ** 2}}} = \\dfrac{{2k - 1}}{{{nd ** 2}}}\\).",
             f"(c) \\(P(X \\ge {m_}) = 1 - P(X \\le {m_ - 1}) = 1 - \\dfrac{{{(m_ - 1) ** 2}}}{{{nd ** 2}}} = {L(pge)}\\).",
             f"(d) \\(\\dfrac{{P(X = {nd})}}{{P(X \\ge {m_})}} = \\dfrac{{{L(sp.Rational(2 * nd - 1, nd ** 2))}}}{{{L(pge)}}} = {L(pcond)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(pa)), P("b", 2, A_expr((2 * kk - 1) / nd**2, ("k",))), P("c", 1, A_num(pge)), P("d", 1, A_num(pcond))), 5, 3, steps,
        "A cumulative probability \\(P(X \\le k)\\) is often easier to count; differences of cumulative probabilities give the distribution.",
        "Count outcomes in the \\(n\\times n\\) grid of equally likely pairs; check your formula against a value you counted.",
        quicker=f"Check (b) with \\(k = {a2}\\): \\(\\frac{{2k - 1}}{{{nd ** 2}}} = {L(pa)}\\), agreeing with (a).",
        common_errors=[err(sp.Rational(2 * a2, nd**2), "careless error", PI, f"The pair \\(({a2}, {a2})\\) has been counted twice.", step=1, part="a"),
                       err(sp.Rational(1, nd), "conceptual", PI, "The values of \\(X\\) are not equally likely: larger values arise from more pairs.", step=1, part="a"),
                       err(sp.Rational(2 * nd - 1, nd**2), "interpretation", PI, "That is \\(P(X = n)\\); 'given that' means divide by the probability of the condition.", step=5, part="d")],
        skill="Derive a probability distribution by counting outcomes.",
        params={"form": "max", "nd": nd, "m": m_, "a": a2},
    )


# ======================================================================= 9B ===
def _table20(r: Rng, nv: int, lo: int = 0):
    xs = sorted(r.sample(range(lo, lo + 9), nv))
    ws = weights(r, nv, 20)
    return xs, ws, [sp.Rational(w, 20) for w in ws]


def t_9B(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.6:
            xs, ws, ps = _table20(r, r.randint(3, 4))
            E = E_(xs, ps)
            return Generated(
                f"The discrete random variable \\(X\\) has the probability distribution\n\n{dtable(xs, [dl(p) for p in ps])}\n\nFind \\(E(X)\\).",
                A_num(dstr(E)), 2, 1,
                ["\\(E(X) = \\sum x\\,P(X = x)\\).", f"\\(E(X) = {wsum(xs, ps)} = {dl(E)}\\)."],
                "The expected value is the long-run average: each value weighted by its probability.",
                "Multiply each value by its probability and add; check the probabilities sum to 1 first.",
                quicker=f"\\(E(X)\\) must lie between the smallest and largest values ({xs[0]} and {xs[-1]}), nearer the more likely ones.",
                common_errors=[err(dstr(sp.Rational(sum(xs), len(xs))), "conceptual", EV, "That is the plain average of the values; weight each value by its probability.", step=2),
                               err(dstr(E2_(xs, ps)), "formula selection", EV, "That is \\(E(X^2)\\): use \\(x\\), not \\(x^2\\).", step=2)],
                skill="Calculate the expected value of a discrete random variable.",
                params={"form": "table", "xs": xs, "ws": ws},
            )
        mu = sp.Rational(r.randint(12, 60), pick(r, [1, 2, 10]))
        a_, b_ = pick(r, [2, 3, 4, 5, -2, -3]), r.randint(-9, 9)
        while b_ == 0:
            b_ = r.randint(-9, 9)
        ans = a_ * mu + b_
        bterm = f"{'+' if b_ > 0 else '-'} {abs(b_)}"
        return Generated(
            f"A random variable \\(X\\) has \\(E(X) = {dl(mu)}\\). Find \\(E({a_}X {bterm})\\).",
            A_num(dstr(ans)), 1, 1,
            [f"\\(E(aX + b) = aE(X) + b = {a_}\\times {dl(mu)} {bterm} = {dl(ans)}\\)."],
            "Expectation is linear: scaling and shifting the variable scales and shifts the mean.",
            "Apply \\(E(aX + b) = aE(X) + b\\) directly.",
            quicker="Every value is multiplied by \\(a\\) and then shifted by \\(b\\), so the average is too.",
            common_errors=[err(dstr(a_ * mu), "careless error", EV, "Add the constant: \\(E(aX + b) = aE(X) + b\\).", step=1),
                           err(dstr(mu + b_), "formula selection", EV, "Multiply the mean by \\(a\\) as well.", step=1)],
            skill="Use the linearity of expectation.",
            params={"form": "lin", "mu": str(mu), "a": a_, "b": b_},
        )
    if d == 2:
        if r.random() < 0.5:
            nd = 6
            W1, W2 = pick(r, [10, 12, 15, 18, 20, 24, 30]), pick(r, [2, 3, 4, 5, 6])
            c = pick(r, [3, 4, 5, 6, 8])
            n_g = pick(r, [20, 50, 100])
            prize = sp.Rational(W1, 6) + sp.Rational(2 * W2, 6)
            gain = prize - c
            text = multipart(
                f"In a game a player pays ${c} and rolls a fair six-sided die. A 6 wins ${W1}, a 4 or a 5 wins ${W2}, and any other number wins nothing.",
                [("a", "Find the expected prize per game.", 1),
                 ("b", "Find the player's expected gain per game (prize minus cost).", 1),
                 ("c", f"Find the player's expected total gain over {n_g} games.", 1)])
            steps = [f"(a) \\(E(\\text{{prize}}) = {W1}\\times\\dfrac{{1}}{{6}} + {W2}\\times\\dfrac{{2}}{{6}} = {dl(prize)}\\) dollars.",
                     f"(b) Expected gain \\(= {dl(prize)} - {c} = {dl(gain)}\\) dollars.",
                     f"(c) Over {n_g} games: \\({n_g}\\times {pdl(gain)} = {dl(n_g * gain)}\\) dollars."]
            return Generated(
                text, A_parts(P("a", 1, A_num(dstr(prize))), P("b", 1, A_num(dstr(gain))), P("c", 1, A_num(dstr(n_g * gain)))), 3, 2, steps,
                "The expected gain is the long-run average result per game; a negative value means the player loses on average.",
                "Define the random variable (prize or gain) in words before writing its distribution.",
                quicker="Expected gain = expected prize − cost, because every game costs the same.",
                common_errors=[err(dstr(sp.Rational(W1 + W2, 2)), "conceptual", EV, "The prizes are not equally likely; weight each by its probability.", step=1, part="a"),
                               err(dstr(-gain), "careless error", "sign error", "Gain is prize minus cost, not cost minus prize.", step=2, part="b"),
                               err(dstr(n_g * prize), "interpretation", EV, "Subtract the cost of each game.", step=3, part="c")],
                skill="Use expected value to analyse a game of chance.",
                params={"form": "game", "W1": W1, "W2": W2, "c": c, "n": n_g},
            )
        while True:
            xs = sorted(r.sample(range(0, 6), 4))
            ws = weights(r, 4, 10)
            i, j = sorted(r.sample(range(4), 2))
            if xs[i] != xs[j]:
                break
        ps = [sp.Rational(w, 10) for w in ws]
        a_, b_ = ps[i], ps[j]
        E = E_(xs, ps)
        cells = [dl(p) for p in ps]
        cells[i], cells[j] = "a", "b"
        rest = sum(ps) - a_ - b_
        restE = E - xs[i] * a_ - xs[j] * b_
        return Generated(
            f"The discrete random variable \\(X\\) has the probability distribution\n\n{dtable(xs, cells)}\n\n"
            f"Given that \\(E(X) = {dl(E)}\\), find \\(a\\) and \\(b\\). Give your answer as \\(a, b\\).",
            A_set([dstr(a_), dstr(b_)], ordered=True), 3, 2,
            [f"Sum of probabilities: \\(a + b + {dl(rest)} = 1\\), so \\(a + b = {dl(1 - rest)}\\).",
             f"Expected value: \\({' + '.join(t_ for t_ in [co(xs[i], 'a') if xs[i] else '', co(xs[j], 'b'), dl(restE) if restE else ''] if t_)} = {dl(E)}\\).",
             f"Solving simultaneously: \\(a = {dl(a_)}\\), \\(b = {dl(b_)}\\)."],
            "Two unknowns need two equations: the probabilities sum to 1, and the given mean.",
            "Write both equations before solving; then check every probability is between 0 and 1.",
            quicker="Substitute your values back into both equations.",
            common_errors=[err(f"{dstr(b_)}, {dstr(a_)}", "careless error", "algebra", "The values are swapped: check which column each letter is in.", step=3)]
            if a_ != b_ else [err(f"{dstr(1 - rest)}, 0", "algebraic", "algebra", "Use both equations: the mean condition fixes how the total splits between \\(a\\) and \\(b\\).", step=2)],
            skill="Find unknown probabilities from the sum and the mean.",
            params={"form": "ab", "xs": xs, "ws": ws, "i": i, "j": j},
        )
    R, B = r.randint(3, 6), r.randint(3, 6)
    T = R + B
    A1, A2 = pick(r, [10, 12, 15, 20, 24, 30]), pick(r, [2, 3, 4, 5])
    p2 = sp.Rational(R * (R - 1), T * (T - 1))
    p1 = sp.Rational(2 * R * B, T * (T - 1))
    prize = A1 * p2 + A2 * p1
    c = int(prize) + pick(r, [1, 2, 3])
    n_g = pick(r, [50, 100, 200])
    text = multipart(
        f"A bag holds {R} red and {B} green balls. A player pays ${c}, then draws two balls at random without replacement. "
        f"Two red balls win ${A1}, exactly one red ball wins ${A2}, and no red balls win nothing.",
        [("a", "Find the probability of drawing two red balls.", 1),
         ("b", "Find the probability of drawing exactly one red ball.", 1),
         ("c", "Find the expected prize per game.", 1),
         ("d", "What should the game cost for it to be fair (expected gain zero)?", 1),
         ("e", f"At ${c} per game, find the expected total gain of the game's organiser over {n_g} games.", 1)])
    steps = [f"(a) \\(\\dfrac{{{R}}}{{{T}}}\\times\\dfrac{{{R - 1}}}{{{T - 1}}} = {L(p2)}\\).",
             f"(b) \\(2\\times\\dfrac{{{R}}}{{{T}}}\\times\\dfrac{{{B}}}{{{T - 1}}} = {L(p1)}\\).",
             f"(c) \\(E(\\text{{prize}}) = {A1}\\times {L(p2)} + {A2}\\times {L(p1)} = {L(prize)}\\) dollars.",
             f"(d) A fair cost equals the expected prize: \\({L(prize)}\\) dollars.",
             f"(e) The organiser gains \\({c} - {L(prize)} = {L(c - prize)}\\) dollars per game on average; over {n_g} games \\({L(n_g * (c - prize))}\\) dollars."]
    return Generated(
        text, A_parts(P("a", 1, A_num(p2)), P("b", 1, A_num(p1)), P("c", 1, A_num(prize)), P("d", 1, A_num(prize)), P("e", 1, A_num(n_g * (c - prize)))), 5, 3, steps,
        "A game is fair when the expected gain is zero, i.e. the cost equals the expected prize.",
        "Build the distribution of the prize first (tree diagram), then take its expected value.",
        quicker="The organiser's gain is the player's loss: the two expected gains are negatives of each other.",
        common_errors=[err(sp.Rational(R, T) ** 2, "conceptual", PI, "Without replacement the second probability changes.", step=1, part="a"),
                       err(p1 / 2, "incomplete reasoning", PI, "Exactly one red can happen in two orders.", step=2, part="b"),
                       err(n_g * (prize - c), "careless error", "sign error", "That is the player's gain; the organiser gains the cost minus the prize.", step=5, part="e")],
        skill="Analyse a game with expected value and decide what makes it fair.",
        params={"form": "bag", "R": R, "B": B, "A1": A1, "A2": A2, "c": c, "n": n_g},
    )


# ======================================================================= 9C ===
def t_9C(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            mu = sp.Rational(r.randint(2, 40), pick(r, [1, 10]))
            var = sp.Rational(r.randint(1, 40), pick(r, [1, 10, 100]))
            s2 = var + mu**2
            return Generated(
                f"For a random variable \\(X\\), \\(E(X) = {dl(mu)}\\) and \\(E(X^2) = {dl(s2)}\\). Find \\(\\operatorname{{Var}}(X)\\).",
                A_num(dstr(var)), 1, 1,
                [f"\\(\\operatorname{{Var}}(X) = E(X^2) - [E(X)]^2 = {dl(s2)} - {dl(mu)}^2 = {dl(var)}\\)."],
                "Variance measures spread: the mean of the squares minus the square of the mean.",
                "Square the mean, then subtract it from \\(E(X^2)\\).",
                quicker="A variance can never be negative — a negative result means a slip.",
                common_errors=[err(dstr(s2 - mu), "formula selection", EV, "Square the mean: \\(\\operatorname{Var}(X) = E(X^2) - [E(X)]^2\\).", step=1),
                               err(dstr(s2 + mu**2), "careless error", "sign error", "Subtract \\([E(X)]^2\\); don't add it.", step=1)],
                skill="Calculate a variance from \\(E(X)\\) and \\(E(X^2)\\).",
                params={"form": "fromE", "mu": str(mu), "s2": str(s2)},
            )
        var = r.randint(2, 20)
        a_, b_ = pick(r, [2, 3, 4, 5, -2, -3]), r.randint(1, 9) * pick(r, [1, -1])
        bterm = f"{'+' if b_ > 0 else '-'} {abs(b_)}"
        ans = a_**2 * var
        return Generated(
            f"A random variable \\(X\\) has \\(\\operatorname{{Var}}(X) = {var}\\). Find \\(\\operatorname{{Var}}({a_}X {bterm})\\).",
            A_num(ans), 1, 1,
            [f"\\(\\operatorname{{Var}}(aX + b) = a^2\\operatorname{{Var}}(X) = {pn(a_)}^2\\times {var} = {ans}\\)."],
            "Shifting a variable doesn't change its spread; scaling by \\(a\\) scales the variance by \\(a^2\\).",
            "Ignore \\(b\\); square \\(a\\).",
            quicker="Standard deviation scales by \\(|a|\\), so the variance scales by \\(a^2\\).",
            common_errors=[err(a_ * var, "formula selection", EV, "Square the multiplier: \\(\\operatorname{Var}(aX + b) = a^2\\operatorname{Var}(X)\\).", step=1),
                           err(a_**2 * var + b_, "conceptual", EV, "Adding a constant shifts every value equally and doesn't change the spread.", step=1)],
            skill="Use \\(\\operatorname{Var}(aX + b) = a^2\\operatorname{Var}(X)\\).",
            params={"form": "lin", "var": var, "a": a_, "b": b_},
        )
    if d == 2:
        xs, ws, ps = _table20(r, r.randint(3, 4))
        E, E2 = E_(xs, ps), E2_(xs, ps)
        V = E2 - E**2
        sd_form = r.random() < 0.4
        ans = A_round(sp.sqrt(V), 2) if sd_form else A_num(dstr(V))
        what = "the standard deviation of \\(X\\), correct to 2 decimal places" if sd_form else "\\(\\operatorname{Var}(X)\\)"
        steps = [f"\\(E(X) = {wsum(xs, ps)} = {dl(E)}\\).",
                 f"\\(E(X^2) = {wsum(xs, ps, sq=True)} = {dl(E2)}\\).",
                 f"\\(\\operatorname{{Var}}(X) = E(X^2) - [E(X)]^2 = {dl(E2)} - {dl(E)}^2 = {dl(V)}\\)."]
        if sd_form:
            steps.append(f"\\(\\sigma = \\sqrt{{{dl(V)}}} \\approx {rnd(sp.sqrt(V), 2)}\\).")
        ces = [err(rnd(sp.sqrt(E2), 2) if sd_form else dstr(E2), "incomplete reasoning", EV, "Subtract \\([E(X)]^2\\) from \\(E(X^2)\\).", step=3),
               err(rnd(sp.sqrt(E2 - E), 2) if sd_form else dstr(E2 - E), "formula selection", EV, "Square the mean before subtracting.", step=3)]
        if sd_form:
            ces.append(err(rnd(V, 2), "incomplete reasoning", EV, "That is the variance; the standard deviation is its square root.", step=4))
        return Generated(
            f"The discrete random variable \\(X\\) has the probability distribution\n\n{dtable(xs, [dl(p) for p in ps])}\n\nFind {what}.",
            ans, 3, 2, steps,
            "\\(\\operatorname{Var}(X) = E(X^2) - [E(X)]^2\\); the standard deviation is its square root, in the same units as \\(X\\).",
            "Tabulate \\(x\\,P(X = x)\\) and \\(x^2 P(X = x)\\) in two rows, then combine.",
            quicker="\\(\\sigma\\) should be roughly the typical distance of the values from the mean.",
            common_errors=ces,
            skill="Calculate the variance and standard deviation of a discrete distribution.",
            checkpoints=[cp(dstr(E), "E(X)", step=1), cp(dstr(E2), "E(X^2)", step=2)],
            params={"form": "table", "xs": xs, "ws": ws, "sd": sd_form},
        )
    nv = r.randint(3, 4)
    xs = sorted(r.sample(range(0, 7), nv))
    cs = [r.randint(1, 4) for _ in xs]
    k_ = sp.Rational(1, sum(cs))
    ps = [c * k_ for c in cs]
    E, E2 = E_(xs, ps), E2_(xs, ps)
    V = E2 - E**2
    a_, b_ = pick(r, [2, 3, 4, -2]), r.randint(1, 6) * pick(r, [1, -1])
    bterm = f"{'+' if b_ > 0 else '-'} {abs(b_)}"
    sdY = abs(a_) * sp.sqrt(V)
    text = multipart(
        f"The discrete random variable \\(X\\) has the probability distribution\n\n{dtable(xs, [kcell(c) for c in cs])}",
        [("a", "Find the value of \\(k\\).", 1), ("b", "Find \\(E(X)\\).", 1), ("c", "Find \\(\\operatorname{Var}(X)\\).", 2),
         ("d", f"Let \\(Y = {a_}X {bterm}\\). Find the standard deviation of \\(Y\\), correct to 2 decimal places.", 1)])
    steps = [f"(a) \\({sum(cs)}k = 1\\), so \\(k = {L(k_)}\\).",
             f"(b) \\(E(X) = {wsum(xs, ps, frac=True)} = {L(E)}\\).",
             f"(c) \\(E(X^2) = {wsum(xs, ps, sq=True, frac=True)} = {L(E2)}\\).",
             f"\\(\\operatorname{{Var}}(X) = {L(E2)} - \\left({L(E)}\\right)^2 = {L(V)}\\).",
             f"(d) \\(\\sigma_Y = |{a_}|\\sqrt{{\\operatorname{{Var}}(X)}} = {abs(a_)}\\sqrt{{{L(V)}}} \\approx {rnd(sdY, 2)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(k_)), P("b", 1, A_num(E)), P("c", 2, A_num(V)), P("d", 1, A_round(sdY, 2))), 5, 3, steps,
        "The mean, variance and standard deviation summarise a distribution; a linear change \\(aX + b\\) scales the spread by \\(|a|\\).",
        "Keep exact fractions until the final rounding.",
        quicker="Check: \\(\\operatorname{Var}(X) \\ge 0\\) and \\(E(X)\\) lies within the range of values.",
        common_errors=[err(sum(cs), "algebraic", "algebra", "Solve for \\(k\\): divide 1 by the sum of the coefficients.", step=1, part="a"),
                       err(E2, "incomplete reasoning", EV, "That is \\(E(X^2)\\); subtract the square of the mean.", step=4, part="c"),
                       err(E2 - E, "formula selection", EV, "Square the mean before subtracting.", step=4, part="c"),
                       err(rnd(a_**2 * V, 2), "formula selection", EV, "That is the variance of \\(Y\\); take its square root.", step=5, part="d"),
                       err(rnd(abs(a_) * sp.sqrt(V) + abs(b_), 2), "conceptual", EV, "Adding a constant doesn't change the spread.", step=5, part="d")],
        skill="Find the mean, variance and standard deviation of a discrete distribution and of a linear function of it.",
        checkpoints=[cp(E2, "E(X^2)", step=3, part="c")],
        params={"form": "full", "xs": xs, "cs": cs, "a": a_, "b": b_},
    )


# ======================================================================= 10A ===
CONTEXTS = [("time spent on homework", "t", "minutes"), ("length of a phone call", "t", "minutes"),
            ("mass of a parcel", "m", "kg"), ("height of a seedling", "h", "cm"), ("waiting time at a clinic", "t", "minutes")]


def _grouped(r: Rng):
    what, v, unit = pick(r, CONTEXTS)
    w = pick(r, [5, 10])
    s0 = pick(r, [0, 10, 20, 30]) if w == 10 else pick(r, [0, 5, 10, 15, 20])
    fs = [r.randint(2, 15) for _ in range(5)]
    bounds = [s0 + i * w for i in range(6)]
    return what, v, unit, w, bounds, fs


def gtable(v: str, unit: str, bounds, fs) -> str:
    rows = " \\\\ ".join(f"{a} \\le {v} < {b} & {f}" for a, b, f in zip(bounds, bounds[1:], fs))
    return f"\\[\\begin{{array}}{{c|c}} \\text{{Class ({unit})}} & \\text{{Frequency}} \\\\ \\hline {rows} \\end{{array}}\\]"


def t_10A(r: Rng, d: int) -> Generated:
    what, v, unit, w, bounds, fs = _grouped(r)
    n_ = sum(fs)
    cum = [sum(fs[:i + 1]) for i in range(5)]
    centres = [sp.Rational(a + b, 2) for a, b in zip(bounds, bounds[1:])]
    mean = sum(f * c for f, c in zip(fs, centres)) / n_
    stem = f"The {what} ({unit}) was recorded for {n_} cases and grouped as follows.\n\n{gtable(v, unit, bounds, fs)}"
    if d == 1:
        j = r.randint(1, 3)
        if r.random() < 0.5:
            return Generated(
                f"{stem}\n\nFind the cumulative frequency of the class \\({bounds[j]} \\le {v} < {bounds[j + 1]}\\).",
                A_num(cum[j]), 1, 1,
                [f"Add the frequencies of this class and every class below it: \\({' + '.join(str(f) for f in fs[:j + 1])} = {cum[j]}\\)."],
                "A cumulative frequency counts all the data up to the upper boundary of a class.",
                "Keep a running total down the frequency column.",
                quicker=f"The last cumulative frequency must equal the total, {n_}.",
                common_errors=[err(fs[j], "interpretation", "notation", "That is the class frequency; a cumulative frequency includes every class below too.", step=1),
                               err(cum[j - 1], "careless error", "notation", "Include the class itself in the running total.", step=1)],
                skill="Find cumulative frequencies from a grouped table.",
                params={"form": "cf", "fs": fs, "j": j},
            )
        p = sp.Rational(cum[j], n_)
        return Generated(
            f"{stem}\n\nUse the table to estimate the probability that a randomly chosen case has \\({v} < {bounds[j + 1]}\\).",
            A_num(p), 1, 1,
            [f"Cases below {bounds[j + 1]}: \\({' + '.join(str(f) for f in fs[:j + 1])} = {cum[j]}\\) out of {n_}, so \\(P \\approx {L(p)}\\)."],
            "Relative frequency estimates probability: favourable cases divided by the total.",
            "Use the cumulative frequency up to the boundary, then divide by the total.",
            quicker="A probability estimate must lie between 0 and 1.",
            common_errors=[err(sp.Rational(fs[j], n_), "interpretation", PI, "Include every class below the boundary, not just the last one.", step=1),
                           err(cum[j], "incomplete reasoning", PI, "Divide by the total number of cases to get a relative frequency.", step=1)],
            skill="Estimate a probability from relative frequencies.",
            params={"form": "rel", "fs": fs, "j": j},
        )
    if d == 2:
        j = r.randint(1, 4)
        pge = sp.Rational(n_ - cum[j - 1], n_)
        text = multipart(stem, [("a", "Use the class centres to estimate the mean, correct to 1 decimal place.", 2),
                                ("b", f"Estimate the probability that a randomly chosen case has \\({v} \\ge {bounds[j]}\\).", 1)])
        steps = [f"(a) Class centres: {', '.join(dl(c) for c in centres)}.",
                 f"\\(\\bar{{{v}}} \\approx \\dfrac{{\\sum f c}}{{\\sum f}} = \\dfrac{{{dl(sum(f * c for f, c in zip(fs, centres)))}}}{{{n_}}} \\approx {rnd(mean, 1)}\\).",
                 f"(b) Cases with \\({v} \\ge {bounds[j]}\\): \\({' + '.join(str(f) for f in fs[j:])} = {n_ - cum[j - 1]}\\), so \\(P \\approx {L(pge)}\\)."]
        return Generated(
            text, A_parts(P("a", 2, A_round(mean, 1)), P("b", 1, A_num(pge))), 3, 2, steps,
            "For grouped data each value is represented by its class centre, so the mean is only an estimate.",
            "Add a column of class centres and a column of \\(f\\times c\\).",
            quicker="The estimated mean must lie inside the range of the data and near the tallest classes.",
            common_errors=[err(rnd(sum(f * a for f, a in zip(fs, bounds)) / sp.Rational(n_), 1), "conceptual", "modelling", "Use the class centres, not the lower boundaries.", step=1, part="a"),
                           err(rnd(sum(f * c for f, c in zip(fs, centres)) / 5, 1), "arithmetic", "modelling", "Divide by the total frequency, not by the number of classes.", step=2, part="a"),
                           err(sp.Rational(cum[j - 1], n_), "interpretation", PI, "That is the probability of the complement.", step=3, part="b")],
            skill="Estimate the mean and probabilities from grouped data.",
            checkpoints=[cp(sum(f * c for f, c in zip(fs, centres)), "sum of f times c", step=2, part="a")],
            params={"form": "mean", "fs": fs, "bounds": bounds, "j": j},
        )
    half = sp.Rational(n_, 2)
    mc = next(i for i in range(5) if cum[i] >= half)
    below = cum[mc - 1] if mc else 0
    med = bounds[mc] + (half - below) / fs[mc] * w
    j = r.randint(1, 3)
    text = multipart(stem, [("a", "Use the class centres to estimate the mean, correct to 1 decimal place.", 2),
                            ("b", f"Find the cumulative frequency at \\({v} = {bounds[j + 1]}\\).", 1),
                            ("c", "Assuming the data are spread evenly within each class (a cumulative frequency polygon), estimate the median, correct to 1 decimal place.", 2)])
    steps = [f"(a) Class centres {', '.join(dl(c) for c in centres)}: \\(\\bar{{{v}}} \\approx \\dfrac{{{dl(sum(f * c for f, c in zip(fs, centres)))}}}{{{n_}}} \\approx {rnd(mean, 1)}\\).",
             f"(b) Cumulative frequencies at the upper boundaries: {', '.join(str(c) for c in cum)}; at \\({v} = {bounds[j + 1]}\\) it is {cum[j]}.",
             f"(c) The median has cumulative frequency \\(\\frac{{{n_}}}{{2}} = {dl(half)}\\), which lies in the class \\({bounds[mc]} \\le {v} < {bounds[mc + 1]}\\).",
             f"Interpolate: \\({bounds[mc]} + \\dfrac{{{dl(half)} - {below}}}{{{fs[mc]}}}\\times {w} \\approx {rnd(med, 1)}\\)."]
    return Generated(
        text, A_parts(P("a", 2, A_round(mean, 1)), P("b", 1, A_num(cum[j])), P("c", 2, A_round(med, 1))), 5, 3, steps,
        "Grouped data lose the individual values: the mean uses class centres and the median is read from the cumulative frequency polygon.",
        "Find the class containing the \\(\\frac{n}{2}\\)th value first, then interpolate within it.",
        quicker="The median must lie inside the class where the cumulative frequency first reaches \\(\\frac{n}{2}\\).",
        common_errors=[err(rnd(sum(f * c for f, c in zip(fs, centres)) / 5, 1), "arithmetic", "modelling", "Divide by the total frequency.", step=1, part="a"),
                       err(fs[j], "interpretation", "notation", "That is a class frequency, not a cumulative one.", step=2, part="b"),
                       err(dl(centres[mc]) if (centres[mc] - med) != 0 else bounds[mc], "incomplete reasoning", "modelling", "Interpolate within the median class rather than quoting its centre.", step=4, part="c")],
        skill="Estimate the mean and median of grouped data.",
        params={"form": "median", "fs": fs, "bounds": bounds, "j": j},
    )


# ======================================================================= 10B ===
def _xpow(n_: int) -> str:
    return "x" if n_ == 1 else f"x^{{{n_}}}"


def t_10B(r: Rng, d: int) -> Generated:
    if d == 1:
        form = pick(r, ["k", "P", "exp"])
        if form == "k":
            n_, a_ = pick(r, [1, 2, 3]), r.randint(1, 4)
            k_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
            return Generated(
                f"The function \\(f(x) = k{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\) (and \\(f(x) = 0\\) otherwise) is a probability density function. Find \\(k\\).",
                A_num(k_), 2, 1,
                [f"The total area under a probability density function is 1: \\(\\displaystyle\\int_0^{{{a_}}} k{_xpow(n_)}\\,dx = 1\\).",
                 f"\\(k\\left[\\dfrac{{x^{{{n_ + 1}}}}}{{{n_ + 1}}}\\right]_0^{{{a_}}} = \\dfrac{{{a_ ** (n_ + 1)}k}}{{{n_ + 1}}} = 1\\), so \\(k = {L(k_)}\\)."],
                "A probability density function is never negative and the total area under it is 1.",
                "Integrate over the whole domain and set the result equal to 1.",
                quicker=f"Check: \\(f({a_}) = {L(k_ * a_ ** n_)}\\) is the height of the curve at the end; the area under it is less than that height times {a_}.",
                common_errors=[err(sp.Rational(1, a_ ** (n_ + 1)), "formula selection", IR, f"Integrating \\({_xpow(n_)}\\) gives \\(\\frac{{x^{{{n_ + 1}}}}}{{{n_ + 1}}}\\); don't drop the divisor.", step=2),
                               err(sp.Rational(1, a_ ** n_), "conceptual", PI, "The condition is that the AREA is 1, not the height \\(f(" + str(a_) + ")\\).", step=1)],
                skill="Find the constant in a probability density function.",
                params={"form": "k", "n": n_, "a": a_},
            )
        if form == "P":
            n_, a_ = pick(r, [1, 2]), r.randint(2, 5)
            b_ = r.randint(1, a_ - 1)
            c_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
            ans = sp.Rational(b_, a_) ** (n_ + 1)
            return Generated(
                f"A continuous random variable \\(X\\) has probability density function \\(f(x) = {L(c_)}{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\) (and 0 otherwise). Find \\(P(X \\le {b_})\\).",
                A_num(ans), 2, 1,
                [f"\\(P(X \\le {b_}) = \\displaystyle\\int_0^{{{b_}}} {L(c_)}{_xpow(n_)}\\,dx\\).",
                 f"\\(= {L(c_)}\\left[\\dfrac{{x^{{{n_ + 1}}}}}{{{n_ + 1}}}\\right]_0^{{{b_}}} = {L(ans)}\\)."],
                "For a continuous random variable, probability is the area under the density curve.",
                "Integrate the pdf between the limits of the event.",
                quicker="The answer must be between 0 and 1; a value outside means a slip.",
                common_errors=[err(c_ * b_**n_, "conceptual", PI, "That is the height \\(f(" + str(b_) + ")\\); a probability is an area.", step=1),
                               err(1 - ans, "interpretation", PI, "That is \\(P(X > " + str(b_) + ")\\).", step=1)],
                skill="Find a probability from a probability density function.",
                params={"form": "P", "n": n_, "a": a_, "b": b_},
            )
        lam, b_ = pick(r, [2, 3, sp.Rational(1, 2), sp.Rational(1, 4)]), r.randint(1, 4)
        ans = sp.exp(-lam * b_)
        return Generated(
            f"The lifetime \\(X\\) years of a component has probability density function \\(f(x) = {L(lam)}e^{{{L(-lam * x)}}}\\) for \\(x \\ge 0\\). "
            f"Find the exact probability that a component lasts more than {b_} years.",
            {"type": "num", "value": f"exp({ -lam * b_})"}, 2, 1,
            [f"\\(P(X > {b_}) = \\displaystyle\\int_{{{b_}}}^{{\\infty}} {L(lam)}e^{{{L(-lam * x)}}}\\,dx = \\left[-e^{{{L(-lam * x)}}}\\right]_{{{b_}}}^{{\\infty}}\\).",
             f"\\(= 0 - \\left(-e^{{{L(-lam * b_)}}}\\right) = e^{{{L(-lam * b_)}}}\\)."],
            "Probability is area under the density curve, here over an unbounded interval.",
            "Use the complement or integrate to infinity; \\(e^{-\\lambda x} \\to 0\\) as \\(x \\to \\infty\\).",
            quicker=f"\\(P(X > {b_}) = 1 - P(X \\le {b_})\\), and \\(P(X \\le x) = 1 - e^{{{L(-lam * x)}}}\\).",
            common_errors=[err(f"1 - exp({-lam * b_})", "interpretation", PI, "That is \\(P(X \\le " + str(b_) + ")\\).", step=2),
                           err(f"{lam}*exp({-lam * b_})", "conceptual", PI, "That is the height of the density at " + str(b_) + "; a probability is an area.", step=1)],
            skill="Find a probability from an exponential density.",
            params={"form": "exp", "lam": str(lam), "b": b_},
        )
    if d == 2:
        if r.random() < 0.5:
            a_ = pick(r, [2, 3, 4, 6])
            b_ = r.randint(1, a_ - 1)
            k_ = sp.Rational(6, a_**3)
            Pb = k_ * (sp.Rational(a_ * b_**2, 2) - sp.Rational(b_**3, 3))
            text = multipart(
                f"A continuous random variable \\(X\\) has probability density function \\(f(x) = kx({a_} - x)\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
                [("a", "Find the value of \\(k\\).", 2), ("b", f"Find \\(P(X \\le {b_})\\).", 1)])
            steps = [f"(a) \\(\\displaystyle\\int_0^{{{a_}}} k({a_}x - x^2)\\,dx = k\\left[\\dfrac{{{a_}x^2}}{{2}} - \\dfrac{{x^3}}{{3}}\\right]_0^{{{a_}}} = {L(sp.Rational(a_**3, 6))}k\\).",
                     f"Setting the area equal to 1: \\(k = {L(k_)}\\).",
                     f"(b) \\(P(X \\le {b_}) = {L(k_)}\\left[\\dfrac{{{a_}x^2}}{{2}} - \\dfrac{{x^3}}{{3}}\\right]_0^{{{b_}}} = {L(Pb)}\\)."]
            return Generated(
                text, A_parts(P("a", 2, A_num(k_)), P("b", 1, A_num(Pb))), 3, 2, steps,
                "The total area under a pdf is 1; probabilities are areas between limits.",
                "Expand before integrating, and keep \\(k\\) outside the integral.",
                quicker=f"The graph is symmetric about \\(x = {L(sp.Rational(a_, 2))}\\), so \\(P(X \\le {L(sp.Rational(a_, 2))}) = \\frac{{1}}{{2}}\\) — compare your (b) with that.",
                common_errors=[err(sp.Rational(a_**3, 6), "algebraic", "algebra", "Solve \\(\\frac{a^3}{6}k = 1\\) for \\(k\\): take the reciprocal.", step=2, part="a"),
                               err(k_ * b_ * (a_ - b_), "conceptual", PI, "That is the height \\(f(" + str(b_) + ")\\); a probability is an area.", step=3, part="b")],
                skill="Find the constant in a polynomial pdf and use it.",
                params={"form": "quad", "a": a_, "b": b_},
            )
        n_, a_ = pick(r, [1, 2, 3]), r.randint(2, 5)
        b1 = r.randint(0, a_ - 1)
        b2 = r.randint(b1 + 1, a_)
        c_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
        F = (x / a_) ** (n_ + 1)
        ans = F.subs(x, b2) - F.subs(x, b1)
        text = multipart(
            f"A continuous random variable \\(X\\) has probability density function \\(f(x) = {L(c_)}{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
            [("a", f"Find the cumulative distribution function \\(F(x) = P(X \\le x)\\) for \\(0 \\le x \\le {a_}\\).", 2),
             ("b", f"Hence find \\(P({b1} \\le X \\le {b2})\\).", 1)])
        steps = [f"(a) \\(F(x) = \\displaystyle\\int_0^{{x}} {L(c_)}t^{{{n_}}}\\,dt = {L(c_)}\\left[\\dfrac{{t^{{{n_ + 1}}}}}{{{n_ + 1}}}\\right]_0^{{x}}\\).",
                 f"\\(F(x) = {L(sp.expand(F))}\\).",
                 f"(b) \\(P({b1} \\le X \\le {b2}) = F({b2}) - F({b1}) = {L(F.subs(x, b2))} - {L(F.subs(x, b1))} = {L(ans)}\\)."]
        return Generated(
            text, A_parts(P("a", 2, A_expr(sp.expand(F))), P("b", 1, A_num(ans))), 3, 2, steps,
            "The cumulative distribution function accumulates area from the left: \\(F(x) = \\int f\\), and \\(F' = f\\).",
            "Integrate from the left end of the domain to \\(x\\); check \\(F\\) reaches 1 at the right end.",
            quicker=f"Check \\(F({a_}) = 1\\) and \\(F(0) = 0\\).",
            common_errors=[err(sp.expand(c_ * x ** (n_ + 1)), "formula selection", IR, "Divide by the new power when integrating.", step=1, part="a"),
                           err(c_ * b2**n_ - c_ * b1**n_, "conceptual", PI, "Use \\(F\\), the area function, not the density \\(f\\).", step=3, part="b")],
            skill="Find and use a cumulative distribution function.",
            params={"form": "cdf", "n": n_, "a": a_, "b1": b1, "b2": b2},
        )
    if r.random() < 0.5:
        n_, a_ = pick(r, [1, 2]), r.randint(2, 6)
        k_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
        F = (x / a_) ** (n_ + 1)
        b1 = r.randint(0, a_ - 1)
        b2 = r.randint(b1 + 1, a_)
        pr = F.subs(x, b2) - F.subs(x, b1)
        med = a_ * sp.Rational(1, 2) ** sp.Rational(1, n_ + 1)
        text = multipart(
            f"A continuous random variable \\(X\\) has probability density function \\(f(x) = k{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
            [("a", "Find the value of \\(k\\).", 1),
             ("b", f"Find the cumulative distribution function \\(F(x)\\) for \\(0 \\le x \\le {a_}\\).", 1),
             ("c", f"Find \\(P({b1} \\le X \\le {b2})\\).", 1),
             ("d", "Find the median of \\(X\\), correct to 2 decimal places.", 2)])
        steps = [f"(a) \\(\\displaystyle\\int_0^{{{a_}}} k{_xpow(n_)}\\,dx = \\dfrac{{{a_ ** (n_ + 1)}k}}{{{n_ + 1}}} = 1\\), so \\(k = {L(k_)}\\).",
                 f"(b) \\(F(x) = \\displaystyle\\int_0^{{x}} {L(k_)}t^{{{n_}}}\\,dt = {L(sp.expand(F))}\\).",
                 f"(c) \\(F({b2}) - F({b1}) = {L(pr)}\\).",
                 f"(d) The median \\(m\\) satisfies \\(F(m) = \\frac{{1}}{{2}}\\): \\({L(sp.expand(F.subs(x, sp.Symbol('m'))))} = \\frac{{1}}{{2}}\\).",
                 f"\\(m = {a_}\\times\\left(\\frac{{1}}{{2}}\\right)^{{\\frac{{1}}{{{n_ + 1}}}}} \\approx {rnd(med, 2)}\\)."]
        return Generated(
            text, A_parts(P("a", 1, A_num(k_)), P("b", 1, A_expr(sp.expand(F))), P("c", 1, A_num(pr)), P("d", 2, A_round(med, 2))), 5, 3, steps,
            "The pdf gives probabilities as areas; the cumulative distribution function \\(F\\) turns them into evaluations, and the median solves \\(F(m) = \\frac{1}{2}\\).",
            "Find \\(k\\) first, then \\(F\\), then use \\(F\\) for every probability and for the median.",
            quicker=f"The density increases, so the median lies above the midpoint {L(sp.Rational(a_, 2))}.",
            common_errors=[err(sp.Rational(1, a_ ** (n_ + 1)), "formula selection", IR, "Divide by the new power when integrating.", step=1, part="a"),
                           err(sp.Rational(a_, 2), "conceptual", PI, "The density is not symmetric, so the median is not the midpoint; solve \\(F(m) = \\frac{1}{2}\\).", step=4, part="d")],
            skill="Work with a pdf: constant, cumulative distribution function, probabilities and median.",
            params={"form": "pow", "n": n_, "a": a_, "b1": b1, "b2": b2},
        )
    lam = pick(r, [2, 3, 4, sp.Rational(1, 2), sp.Rational(1, 5), sp.Rational(1, 10)])
    b_ = r.randint(1, 5)
    med = sp.log(2) / lam
    med_s = f"ln(2)/({ex(lam)})"
    text = multipart(
        f"The time \\(X\\) hours between calls to a help line has probability density function \\(f(x) = ke^{{{L(-lam * x)}}}\\) for \\(x \\ge 0\\), and 0 for \\(x < 0\\).",
        [("a", "Find the value of \\(k\\).", 1),
         ("b", "Find the cumulative distribution function \\(F(x)\\) for \\(x \\ge 0\\).", 1),
         ("c", f"Find the exact probability that the time between calls is more than {b_} hours.", 1),
         ("d", "Find the exact median time between calls.", 2)])
    steps = [f"(a) \\(\\displaystyle\\int_0^{{\\infty}} ke^{{{L(-lam * x)}}}\\,dx = \\dfrac{{k}}{{{L(lam)}}} = 1\\), so \\(k = {L(lam)}\\).",
             f"(b) \\(F(x) = \\displaystyle\\int_0^{{x}} {L(lam)}e^{{{L(-lam * sp.Symbol('t'))}}}\\,dt = 1 - e^{{{L(-lam * x)}}}\\).",
             f"(c) \\(P(X > {b_}) = 1 - F({b_}) = e^{{{L(-lam * b_)}}}\\).",
             f"(d) \\(1 - e^{{{L(-lam * sp.Symbol('m'))}}} = \\frac{{1}}{{2}}\\), so \\(e^{{{L(-lam * sp.Symbol('m'))}}} = \\frac{{1}}{{2}}\\).",
             f"\\(m = \\dfrac{{\\ln 2}}{{{L(lam)}}} = {L(med)}\\) hours."]
    return Generated(
        text, A_parts(P("a", 1, A_num(lam)), P("b", 1, A_expr(1 - sp.exp(-lam * x))), P("c", 1, {"type": "num", "value": f"exp({-lam * b_})"}),
                      P("d", 2, {"type": "num", "value": med_s})), 5, 3, steps,
        "An exponential density models waiting times; its cumulative distribution function is \\(1 - e^{-\\lambda x}\\) and its median solves \\(F(m) = \\frac{1}{2}\\).",
        "Use the limit \\(e^{-\\lambda x} \\to 0\\) as \\(x \\to \\infty\\) for the total area.",
        quicker="\\(F(0) = 0\\) and \\(F(x) \\to 1\\): check your \\(F\\) does both.",
        common_errors=[err(sp.Rational(1) / lam, "algebraic", "algebra", "\\(\\frac{k}{\\lambda} = 1\\) gives \\(k = \\lambda\\).", step=1, part="a"),
                       err(f"1 - exp({-lam * b_})", "interpretation", PI, "That is \\(P(X \\le " + str(b_) + ")\\).", step=3, part="c"),
                       err(ex(1 / lam), "conceptual", EV, "That is the mean \\(\\frac{1}{\\lambda}\\); the median solves \\(F(m) = \\frac{1}{2}\\).", step=4, part="d")],
        skill="Work with an exponential probability density function.",
        params={"form": "exp", "lam": str(lam), "b": b_},
    )


# ======================================================================= 10C ===
def t_10C(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            a_ = r.randint(0, 10)
            b_ = a_ + pick(r, [2, 4, 5, 6, 8, 10])
            return Generated(
                f"\\(X\\) has probability density function \\(f(x) = {L(sp.Rational(1, b_ - a_))}\\) for \\({a_} \\le x \\le {b_}\\), and 0 otherwise. Find \\(E(X)\\).",
                A_num(dstr(sp.Rational(a_ + b_, 2))), 1, 1,
                [f"\\(E(X) = \\displaystyle\\int_{{{a_}}}^{{{b_}}} x\\times {L(sp.Rational(1, b_ - a_))}\\,dx = {L(sp.Rational(1, b_ - a_))}\\left[\\dfrac{{x^2}}{{2}}\\right]_{{{a_}}}^{{{b_}}} = {dl(sp.Rational(a_ + b_, 2))}\\)."],
                "The mean of a continuous distribution is \\(E(X) = \\int x f(x)\\,dx\\); for a constant density it is the midpoint.",
                "Multiply the density by \\(x\\) before integrating.",
                quicker="A constant density is symmetric, so the mean is the midpoint of the interval.",
                common_errors=[err(dstr(sp.Rational(b_ - a_, 2)), "interpretation", EV, "That is half the width; the mean is the midpoint of the interval.", step=1),
                               err(1, "conceptual", EV, "\\(\\int f(x)\\,dx = 1\\) is the total probability; the mean is \\(\\int x f(x)\\,dx\\).", step=1)],
                skill="Find the mean of a uniform continuous distribution.",
                params={"form": "uni", "a": a_, "b": b_},
            )
        a_ = r.randint(1, 9)
        c_ = sp.Rational(2, a_**2)
        return Generated(
            f"\\(X\\) has probability density function \\(f(x) = {L(c_)}x\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise. Find \\(E(X)\\).",
            A_num(sp.Rational(2 * a_, 3)), 2, 1,
            [f"\\(E(X) = \\displaystyle\\int_0^{{{a_}}} x\\times {L(c_)}x\\,dx = {L(c_)}\\left[\\dfrac{{x^3}}{{3}}\\right]_0^{{{a_}}}\\).",
             f"\\(= {L(c_)}\\times\\dfrac{{{a_ ** 3}}}{{3}} = {L(sp.Rational(2 * a_, 3))}\\)."],
            "\\(E(X) = \\int x f(x)\\,dx\\): the balance point of the area under the density.",
            "Multiply by \\(x\\), integrate over the whole domain.",
            quicker=f"The density increases, so the mean lies to the right of the midpoint {L(sp.Rational(a_, 2))}.",
            common_errors=[err(sp.Rational(a_, 2), "conceptual", EV, "The density is not symmetric; compute \\(\\int x f(x)\\,dx\\).", step=1),
                           err(1, "formula selection", EV, "That is \\(\\int f(x)\\,dx\\); multiply by \\(x\\) first.", step=1)],
            skill="Find the mean of a continuous random variable.",
            params={"form": "lin", "a": a_},
        )
    if d == 2:
        if r.random() < 0.5:
            n_, a_ = pick(r, [1, 2, 3]), r.randint(1, 6)
            c_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
            E = sp.Rational((n_ + 1) * a_, n_ + 2)
            E2 = sp.Rational((n_ + 1) * a_**2, n_ + 3)
            V = E2 - E**2
            text = multipart(
                f"\\(X\\) has probability density function \\(f(x) = {L(c_)}{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
                [("a", "Find \\(E(X)\\).", 1), ("b", "Find \\(\\operatorname{Var}(X)\\).", 2)])
            steps = [f"(a) \\(E(X) = \\displaystyle\\int_0^{{{a_}}} {L(c_)}x^{{{n_ + 1}}}\\,dx = {L(E)}\\).",
                     f"(b) \\(E(X^2) = \\displaystyle\\int_0^{{{a_}}} {L(c_)}x^{{{n_ + 2}}}\\,dx = {L(E2)}\\).",
                     f"\\(\\operatorname{{Var}}(X) = E(X^2) - [E(X)]^2 = {L(E2)} - \\left({L(E)}\\right)^2 = {L(V)}\\)."]
            return Generated(
                text, A_parts(P("a", 1, A_num(E)), P("b", 2, A_num(V))), 3, 2, steps,
                "For a continuous variable, \\(E(X) = \\int xf\\), \\(E(X^2) = \\int x^2 f\\) and \\(\\operatorname{Var}(X) = E(X^2) - [E(X)]^2\\).",
                "Raise the power of \\(x\\) by one for \\(E(X)\\) and by two for \\(E(X^2)\\).",
                quicker="The variance must be positive and smaller than the square of the domain's width.",
                common_errors=[err(E2, "incomplete reasoning", EV, "That is \\(E(X^2)\\); subtract \\([E(X)]^2\\).", step=3, part="b"),
                               err(E2 - E, "formula selection", EV, "Square the mean before subtracting.", step=3, part="b")],
                skill="Find the mean and variance of a continuous random variable.",
                checkpoints=[cp(E2, "E(X^2)", step=2, part="b")],
                params={"form": "pow", "n": n_, "a": a_},
            )
        a_ = r.randint(0, 6)
        b_ = a_ + pick(r, [2, 3, 4, 6, 12])
        E = sp.Rational(a_ + b_, 2)
        V = sp.Rational((b_ - a_) ** 2, 12)
        text = multipart(
            f"\\(X\\) has probability density function \\(f(x) = {L(sp.Rational(1, b_ - a_))}\\) for \\({a_} \\le x \\le {b_}\\), and 0 otherwise.",
            [("a", "Find \\(E(X)\\).", 1), ("b", "Find \\(\\operatorname{Var}(X)\\).", 2)])
        E2 = sp.Rational(b_**3 - a_**3, 3 * (b_ - a_))
        steps = [f"(a) By symmetry (or integrating \\(xf(x)\\)), \\(E(X) = {dl(E)}\\).",
                 f"(b) \\(E(X^2) = \\displaystyle\\int_{{{a_}}}^{{{b_}}} {L(sp.Rational(1, b_ - a_))}x^2\\,dx = {L(sp.Rational(1, b_ - a_))}\\left[\\dfrac{{x^3}}{{3}}\\right]_{{{a_}}}^{{{b_}}} = {L(E2)}\\).",
                 f"\\(\\operatorname{{Var}}(X) = {L(E2)} - {pdl(E)}^2 = {L(V)}\\)."]
        return Generated(
            text, A_parts(P("a", 1, A_num(dstr(E))), P("b", 2, A_num(V))), 3, 2, steps,
            "A uniform distribution has mean at the midpoint and variance \\(\\frac{(b - a)^2}{12}\\).",
            "Compute \\(E(X^2)\\) by integration, then subtract the squared mean.",
            quicker=f"Check against \\(\\frac{{(b - a)^2}}{{12}} = \\frac{{{(b_ - a_) ** 2}}}{{12}}\\).",
            common_errors=[err(E2, "incomplete reasoning", EV, "That is \\(E(X^2)\\); subtract \\([E(X)]^2\\).", step=3, part="b"),
                           err(sp.Rational(b_ - a_, 12), "formula selection", EV, "The width must be squared.", step=3, part="b")],
            skill="Find the mean and variance of a uniform distribution.",
            checkpoints=[cp(E2, "E(X^2)", step=2, part="b")],
            params={"form": "uni", "a": a_, "b": b_},
        )
    if r.random() < 0.5:
        n_, a_ = pick(r, [1, 2, 3]), r.randint(1, 6)
        k_ = sp.Rational(n_ + 1, a_ ** (n_ + 1))
        E = sp.Rational((n_ + 1) * a_, n_ + 2)
        E2 = sp.Rational((n_ + 1) * a_**2, n_ + 3)
        V = E2 - E**2
        pmu = (E / a_) ** (n_ + 1)
        text = multipart(
            f"\\(X\\) has probability density function \\(f(x) = k{_xpow(n_)}\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
            [("a", "Find \\(k\\).", 1), ("b", "Find \\(E(X)\\).", 1), ("c", "Find \\(\\operatorname{Var}(X)\\).", 2),
             ("d", "Find the probability that \\(X\\) is less than its mean.", 1)])
        steps = [f"(a) \\(\\dfrac{{{a_ ** (n_ + 1)}k}}{{{n_ + 1}}} = 1\\), so \\(k = {L(k_)}\\).",
                 f"(b) \\(E(X) = \\displaystyle\\int_0^{{{a_}}} {L(k_)}x^{{{n_ + 1}}}\\,dx = {L(E)}\\).",
                 f"(c) \\(E(X^2) = \\displaystyle\\int_0^{{{a_}}} {L(k_)}x^{{{n_ + 2}}}\\,dx = {L(E2)}\\).",
                 f"\\(\\operatorname{{Var}}(X) = {L(E2)} - \\left({L(E)}\\right)^2 = {L(V)}\\).",
                 f"(d) \\(P\\left(X < {L(E)}\\right) = \\displaystyle\\int_0^{{{L(E)}}} {L(k_)}{_xpow(n_)}\\,dx = {L(pmu)}\\)."]
        return Generated(
            text, A_parts(P("a", 1, A_num(k_)), P("b", 1, A_num(E)), P("c", 2, A_num(V)), P("d", 1, A_num(pmu))), 5, 3, steps,
            "A pdf's constant comes from total area 1; the mean and variance come from \\(\\int xf\\) and \\(\\int x^2 f\\).",
            "Work exactly with fractions; the mean in (b) is the upper limit in (d).",
            quicker="The density increases (the distribution is skewed to the left), so the mean lies below the median and (d) must be a little under \\(\\frac{1}{2}\\).",
            common_errors=[err(sp.Rational(1, a_ ** (n_ + 1)), "formula selection", IR, "Divide by the new power when integrating.", step=1, part="a"),
                           err(E2, "incomplete reasoning", EV, "That is \\(E(X^2)\\); subtract the squared mean.", step=4, part="c"),
                           err(sp.Rational(1, 2), "conceptual", PI, "The mean is not the median for a skewed density; integrate up to the mean.", step=5, part="d")],
            skill="Find the constant, mean and variance of a pdf and interpret the mean.",
            params={"form": "pow", "n": n_, "a": a_},
        )
    a_ = pick(r, [2, 3, 4, 6])
    b_ = pick(r, [sp.Rational(a_, 4), sp.Rational(a_, 3)])
    k_ = sp.Rational(6, a_**3)
    E = sp.Rational(a_, 2)
    E2 = sp.Rational(3 * a_**2, 10)
    V = E2 - E**2
    pb = k_ * (a_ * b_**2 / 2 - b_**3 / 3)
    text = multipart(
        f"\\(X\\) has probability density function \\(f(x) = kx({a_} - x)\\) for \\(0 \\le x \\le {a_}\\), and 0 otherwise.",
        [("a", "Find \\(k\\).", 1), ("b", "Use the symmetry of the graph of \\(y = f(x)\\) to find \\(E(X)\\).", 1),
         ("c", "Find \\(\\operatorname{Var}(X)\\).", 2), ("d", f"Find \\(P\\left(X < {L(b_)}\\right)\\).", 1)])
    steps = [f"(a) \\(k\\left[\\dfrac{{{a_}x^2}}{{2}} - \\dfrac{{x^3}}{{3}}\\right]_0^{{{a_}}} = {L(sp.Rational(a_**3, 6))}k = 1\\), so \\(k = {L(k_)}\\).",
             f"(b) The graph is a parabola symmetric about \\(x = {L(E)}\\), so the balance point is \\({L(E)}\\); integrating \\(xf(x)\\) agrees.",
             f"(c) \\(E(X^2) = {L(k_)}\\displaystyle\\int_0^{{{a_}}} ({a_}x^3 - x^4)\\,dx = {L(E2)}\\).",
             f"\\(\\operatorname{{Var}}(X) = {L(E2)} - \\left({L(E)}\\right)^2 = {L(V)}\\).",
             f"(d) \\({L(k_)}\\left[\\dfrac{{{a_}x^2}}{{2}} - \\dfrac{{x^3}}{{3}}\\right]_0^{{{L(b_)}}} = {L(pb)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(k_)), P("b", 1, A_num(E)), P("c", 2, A_num(V)), P("d", 1, A_num(pb))), 5, 3, steps,
        "Symmetry gives the mean of a symmetric density immediately; the variance still needs \\(E(X^2)\\).",
        "Expand \\(x^2 f(x)\\) before integrating.",
        quicker=f"For this shape \\(\\operatorname{{Var}}(X) = \\frac{{a^2}}{{20}} = {L(sp.Rational(a_**2, 20))}\\).",
        common_errors=[err(sp.Rational(a_**3, 6), "algebraic", "algebra", "Take the reciprocal to find \\(k\\).", step=1, part="a"),
                       err(E2, "incomplete reasoning", EV, "That is \\(E(X^2)\\); subtract the squared mean.", step=4, part="c"),
                       err(E2 - E, "formula selection", EV, "Square the mean before subtracting.", step=4, part="c")],
        skill="Mean and variance of a symmetric polynomial pdf.",
        params={"form": "quad", "a": a_, "b": str(b_)},
    )


# ======================================================================= 10D ===
def zpick(r: Rng, lo: int = 10, hi: int = 250) -> sp.Rational:
    return sp.Rational(r.randint(lo, hi), 100)


def A_p(v) -> dict:
    """A probability from table values: exact decimal, with a tolerance for calculator values."""
    return A_approx(dstr(v), PTOL)


EMP = {1: sp.Rational(68, 100), 2: sp.Rational(95, 100), 3: sp.Rational(997, 1000)}


def emp_between(k1: int, k2: int) -> sp.Rational:
    """P(-k1 < Z < k2) by the empirical rule (68-95-99.7)."""
    return EMP[k1] / 2 + EMP[k2] / 2


def t_10D(r: Rng, d: int) -> Generated:
    if d == 1:
        form = pick(r, ["upper", "neg", "emp"])
        if form == "emp":
            k1, k2 = pick(r, [(1, 2), (2, 1), (1, 3), (3, 1), (2, 3), (3, 2), (1, 1), (2, 2)])
            pc = emp_between(k1, k2) * 100
            return Generated(
                f"\\(Z\\) has the standard normal distribution. Use the empirical rule (about 68%, 95% and 99.7% of values lie within 1, 2 and 3 standard deviations of the mean) "
                f"to estimate the percentage of values with \\(-{k1} < Z < {k2}\\).",
                A_approx(dstr(pc), 0.05, "%"), 2, 1,
                [f"By symmetry, between \\(-{k1}\\) and 0 lies half of {dstr(EMP[k1] * 100)}%, i.e. {dstr(EMP[k1] * 50)}%; between 0 and {k2} lies {dstr(EMP[k2] * 50)}%.",
                 f"Total \\(\\approx {dstr(pc)}\\%\\)."],
                "The standard normal curve is symmetric about 0, so each 'within k standard deviations' percentage splits equally either side.",
                "Sketch the bell curve, shade the region and split it at 0.",
                quicker="The answer must lie between the two 'within' percentages for the two bounds.",
                common_errors=[err(dstr(EMP[max(k1, k2)] * 100), "incomplete reasoning", ND, "The interval is not symmetric: split it at 0 and halve each percentage.", step=1),
                               err(dstr((EMP[k1] + EMP[k2]) * 100), "conceptual", ND, "Each side of 0 holds only half of the 'within' percentage.", step=1)],
                skill="Use the empirical rule with the standard normal distribution.",
                params={"form": "emp", "k1": k1, "k2": k2},
            )
        z = zpick(r)
        ph = phi4(z)
        ans = 1 - ph
        q_txt = f"P(Z > {zt(z)})" if form == "upper" else f"P(Z < -{zt(z)})"
        return Generated(
            f"\\(Z\\) has the standard normal distribution. {given(z)} Find \\({q_txt}\\).",
            A_p(ans), 1, 1,
            [(f"\\(P(Z > {zt(z)}) = 1 - P(Z \\le {zt(z)}) = 1 - {dstr(ph)} = {dstr(ans)}\\)." if form == "upper" else
              f"By symmetry \\(P(Z < -{zt(z)}) = P(Z > {zt(z)}) = 1 - {dstr(ph)} = {dstr(ans)}\\).")],
            "Tables give the area to the LEFT of \\(z\\); use the complement and the symmetry of the curve for other areas.",
            "Sketch the curve and shade the area you need before using the table.",
            quicker="Areas in the tails beyond \\(\\pm z\\) are equal, and each is less than 0.5 for \\(z > 0\\).",
            common_errors=[err(dstr(ph), "interpretation", ND, "That is the area to the left of " + zt(z) + "; you need the other side.", step=1),
                           err(dstr(sp.Rational(1, 2) - ph if ph < sp.Rational(1, 2) else ph - sp.Rational(1, 2)), "conceptual", ND,
                               "Areas are measured from the far left, not from 0.", step=1)],
            skill="Find tail probabilities for the standard normal distribution.",
            params={"form": form, "z": str(z)},
        )
    if d == 2:
        form = pick(r, ["between", "straddle", "symm"])
        if form == "symm":
            z = zpick(r, 20, 250)
            ph = phi4(z)
            ans = 2 * ph - 1
            return Generated(
                f"\\(Z\\) has the standard normal distribution. {given(z)} Find \\(P(-{zt(z)} < Z < {zt(z)})\\).",
                A_p(ans), 2, 2,
                [f"The area above {zt(z)} is \\(1 - {dstr(ph)} = {dstr(1 - ph)}\\), and by symmetry so is the area below \\(-{zt(z)}\\).",
                 f"\\(P(-{zt(z)} < Z < {zt(z)}) = 1 - 2\\times {dstr(1 - ph)} = {dstr(ans)}\\)."],
                "Symmetry of the normal curve: \\(P(-z < Z < z) = 2P(Z < z) - 1\\).",
                "Subtract both tails from the total area 1.",
                quicker="Compare with the empirical rule: within 1 sd is about 0.68, within 2 sd about 0.95.",
                common_errors=[err(dstr(2 * ph), "incomplete reasoning", ND, "A probability can't exceed 1: subtract 1 (the two tails).", step=2),
                               err(dstr(ph - (1 - ph) / 2), "conceptual", ND, "Remove the whole lower tail, not half of it.", step=2)],
                skill="Use symmetry to find a central normal probability.",
                params={"form": "symm", "z": str(z)},
            )
        z1, z2 = zpick(r, 10, 200), zpick(r, 10, 250)
        if form == "between":
            z1, z2 = sorted([z1, z2])
            if z1 == z2:
                z2 += sp.Rational(1, 10)
            p1, p2 = phi4(z1), phi4(z2)
            ans = p2 - p1
            return Generated(
                f"\\(Z\\) has the standard normal distribution. {given(z1, z2)} Find \\(P({zt(z1)} < Z < {zt(z2)})\\).",
                A_p(ans), 2, 2,
                [f"\\(P({zt(z1)} < Z < {zt(z2)}) = P(Z < {zt(z2)}) - P(Z < {zt(z1)})\\).",
                 f"\\(= {dstr(p2)} - {dstr(p1)} = {dstr(ans)}\\)."],
                "The area between two values is the difference of the areas to their left.",
                "Larger \\(z\\) minus smaller \\(z\\) — the answer must be positive.",
                quicker="Sketch: the shaded strip lies wholly on one side of 0, so the answer is less than 0.5.",
                common_errors=[err(dstr(p2 + p1 - 1), "conceptual", "sign error", "Both values are above the mean; no symmetry step is needed.", step=1),
                               err(dstr(1 - p1), "incomplete reasoning", ND, "That is everything above " + zt(z1) + "; remove the part above " + zt(z2) + " too.", step=1)],
                skill="Find the probability between two positive z-values.",
                params={"form": "between", "z1": str(z1), "z2": str(z2)},
            )
        p1, p2 = phi4(z1), phi4(z2)
        ans = p2 - (1 - p1)
        return Generated(
            f"\\(Z\\) has the standard normal distribution. {given(z1, z2)} Find \\(P(-{zt(z1)} < Z < {zt(z2)})\\).",
            A_p(ans), 2, 2,
            [f"By symmetry \\(P(Z < -{zt(z1)}) = 1 - P(Z < {zt(z1)}) = {dstr(1 - p1)}\\).",
             f"\\(P(-{zt(z1)} < Z < {zt(z2)}) = {dstr(p2)} - {dstr(1 - p1)} = {dstr(ans)}\\)."],
            "Negative \\(z\\)-values come from symmetry: \\(P(Z < -a) = 1 - P(Z < a)\\).",
            "Sketch and shade; the region crosses 0, so the answer is more than either half on its own.",
            quicker="Check against the empirical rule for the nearest whole \\(z\\)-values.",
            common_errors=[err(dstr(p2 - p1), "careless error", "sign error", f"\\(P(Z < -{zt(z1)})\\) is not \\(P(Z < {zt(z1)})\\): use symmetry for the negative value.", step=1),
                           err(dstr(p2 + p1), "conceptual", ND, "A probability can't exceed 1; subtract the area below the lower value.", step=2)],
            skill="Find a normal probability across the mean.",
            params={"form": "straddle", "z1": str(z1), "z2": str(z2)},
        )
    za, zb = zpick(r, 30, 200), zpick(r, 30, 250)
    zc = zpick(r, 50, 250)
    pa, pb, pc = phi4(za), phi4(zb), phi4(zc)
    text = multipart(
        f"\\(Z\\) has the standard normal distribution. {given(za, zb, zc)}",
        [("a", f"Find \\(P(Z > {zt(zb)})\\).", 1), ("b", f"Find \\(P(-{zt(za)} < Z < {zt(zb)})\\).", 2),
         ("c", f"Find \\(P(|Z| > {zt(zc)})\\).", 1), ("d", f"Find \\(P(Z > {zt(zb)} \\mid Z > 0)\\).", 1)])
    steps = [f"(a) \\(1 - {dstr(pb)} = {dstr(1 - pb)}\\).",
             f"(b) \\(P(Z < -{zt(za)}) = 1 - {dstr(pa)} = {dstr(1 - pa)}\\) by symmetry,",
             f"so \\(P(-{zt(za)} < Z < {zt(zb)}) = {dstr(pb)} - {dstr(1 - pa)} = {dstr(pb - 1 + pa)}\\).",
             f"(c) Both tails: \\(2\\times(1 - {dstr(pc)}) = {dstr(2 * (1 - pc))}\\).",
             f"(d) \\(\\dfrac{{P(Z > {zt(zb)})}}{{P(Z > 0)}} = \\dfrac{{{dstr(1 - pb)}}}{{0.5}} = {dstr(2 * (1 - pb))}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_p(1 - pb)), P("b", 2, A_p(pb - 1 + pa)), P("c", 1, A_p(2 * (1 - pc))), P("d", 1, A_p(2 * (1 - pb)))), 5, 3, steps,
        "Every standard normal probability comes from the left-area table, the complement \\(1 - P\\) and the symmetry of the curve about 0.",
        "Sketch and shade for every part; write the table value you use.",
        quicker="(d): half the curve lies above 0, so the conditional probability is twice the unconditional one.",
        common_errors=[err(dstr(pb), "interpretation", ND, "That is the area to the left; you need the right tail.", step=1, part="a"),
                       err(dstr(pb - pa), "careless error", "sign error", "Use symmetry for the negative value: \\(P(Z < -a) = 1 - P(Z < a)\\).", step=2, part="b"),
                       err(dstr(1 - pc), "incomplete reasoning", ND, "\\(|Z| > c\\) has two tails.", step=4, part="c"),
                       err(dstr(1 - pb), "interpretation", PI, "Given \\(Z > 0\\), divide by \\(P(Z > 0) = 0.5\\).", step=5, part="d")],
        skill="Standard normal probabilities: tails, intervals, absolute values and conditional probability.",
        params={"form": "parts", "za": str(za), "zb": str(zb), "zc": str(zc)},
    )


# ======================================================================= 10E ===
# (context, unit, possible means, possible standard deviations); every sigma divides 100 so integer
# values give z-values with at most 2 decimal places.
SCENES = [("The marks in an examination", "marks", [55, 60, 62, 65, 68, 70, 72], [4, 5, 10]),
          ("The heights of a group of seedlings", "cm", [20, 24, 30, 36, 40], [2, 4, 5]),
          ("The masses of packets of rice", "g", [500, 750, 1000], [4, 5, 10, 20, 25]),
          ("The times taken to complete a puzzle", "seconds", [90, 120, 150, 180], [10, 20, 25]),
          ("The lengths of bolts from a machine", "mm", [40, 50, 60, 80, 100], [2, 4, 5])]


def _normal(r: Rng):
    scene, unit, mus, sigmas = pick(r, SCENES)
    return pick(r, mus), pick(r, sigmas), scene, unit


def _score(r: Rng, mu, sigma, lo=0.2, hi=2.5, sign=1):
    """An integer score whose z-value (2 dp) has |z| in [lo, hi]."""
    while True:
        xv = mu + sign * r.randint(1, int(hi * sigma))
        z = sp.Rational(xv - mu, sigma)
        if lo <= abs(z) <= hi:
            return xv, z


def t_10E(r: Rng, d: int) -> Generated:
    mu, sigma, scene, unit = _normal(r)
    intro = f"{scene} are normally distributed with mean {mu} {unit} and standard deviation {sigma} {unit}."
    if d == 1:
        form = pick(r, ["z", "x", "emp"])
        if form == "z":
            xv, z = _score(r, mu, sigma, sign=pick(r, [1, -1]))
            return Generated(
                f"{intro} Find the \\(z\\)-score of a value of {xv} {unit}.",
                A_num(dstr(z)), 1, 1,
                [f"\\(z = \\dfrac{{x - \\mu}}{{\\sigma}} = \\dfrac{{{xv} - {mu}}}{{{sigma}}} = {dstr(z)}\\)."],
                "A \\(z\\)-score counts how many standard deviations a value lies above (+) or below (−) the mean.",
                "Subtract the mean first, then divide by the standard deviation.",
                quicker="Values below the mean have negative \\(z\\)-scores.",
                common_errors=[err(dstr(-z), "careless error", "sign error", "Subtract the mean from the value, not the reverse.", step=1),
                               err(dstr(sp.Rational(xv, sigma) - mu), "algebraic", "algebra", "Subtract the mean before dividing: \\(z = \\frac{x - \\mu}{\\sigma}\\).", step=1)],
                skill="Calculate a z-score.",
                params={"form": "z", "mu": mu, "sigma": sigma, "x": xv},
            )
        if form == "x":
            z = sp.Rational(0)
            while z == 0:
                z = sp.Rational(r.randint(-250, 250), 100)
            xv = mu + z * sigma
            return Generated(
                f"{intro} Which value has a \\(z\\)-score of \\({dstr(z)}\\)?",
                A_num(dstr(xv)), 1, 1,
                [f"\\(x = \\mu + z\\sigma = {mu} + {pdl(z)}\\times {sigma} = {dstr(xv)}\\)."],
                "Rearranging \\(z = \\frac{x - \\mu}{\\sigma}\\) gives \\(x = \\mu + z\\sigma\\).",
                "Multiply \\(z\\) by the standard deviation, then add the mean.",
                quicker="A negative \\(z\\)-score gives a value below the mean.",
                common_errors=[err(dstr(mu - z * sigma), "careless error", "sign error", "Add \\(z\\sigma\\) to the mean (a negative \\(z\\) takes you below it).", step=1),
                               err(dstr(mu + z), "formula selection", ND, "Multiply \\(z\\) by the standard deviation.", step=1)],
                skill="Find the value with a given z-score.",
                params={"form": "x", "mu": mu, "sigma": sigma, "zz": str(z)},
            )
        k1, k2 = pick(r, [(1, 2), (2, 1), (1, 3), (2, 3), (1, 1), (2, 2), (3, 1)])
        lo, hi = mu - k1 * sigma, mu + k2 * sigma
        pc = emp_between(k1, k2) * 100
        return Generated(
            f"{intro} Use the empirical rule (68–95–99.7) to estimate the percentage of values between {lo} and {hi} {unit}.",
            A_approx(dstr(pc), 0.05, "%"), 2, 1,
            [f"\\({lo}\\) has \\(z = -{k1}\\) and \\({hi}\\) has \\(z = {k2}\\).",
             f"Below the mean: {dstr(EMP[k1] * 50)}%; above: {dstr(EMP[k2] * 50)}%. Total \\(\\approx {dstr(pc)}\\%\\)."],
            "The empirical rule: about 68%, 95% and 99.7% of a normal population lie within 1, 2 and 3 standard deviations of the mean.",
            "Convert each bound to a \\(z\\)-score, then split the region at the mean.",
            quicker="Draw the bell curve with the mean and ±1, ±2, ±3 standard deviations marked.",
            common_errors=[err(dstr(EMP[max(k1, k2)] * 100), "incomplete reasoning", ND, "The region isn't symmetric: halve each 'within' percentage.", step=2),
                           err(dstr((EMP[k1] + EMP[k2]) * 100), "conceptual", ND, "Only half of each 'within' percentage lies on each side of the mean.", step=2)],
            skill="Apply the empirical rule to a general normal distribution.",
            params={"form": "emp", "k1": k1, "k2": k2},
        )
    if d == 2:
        x1, z1 = _score(r, mu, sigma, 0.2, 2.2, -1)
        x2, z2 = _score(r, mu, sigma, 0.2, 2.5, 1)
        p1, p2 = phi4(-z1), phi4(z2)
        ans = p2 - (1 - p1)
        return Generated(
            f"{intro} {given(-z1, z2)} Find the probability that a randomly chosen value lies between {x1} and {x2} {unit}.",
            A_p(ans), 3, 2,
            [f"Standardise: \\(z_1 = \\dfrac{{{x1} - {mu}}}{{{sigma}}} = {dstr(z1)}\\), \\(z_2 = \\dfrac{{{x2} - {mu}}}{{{sigma}}} = {dstr(z2)}\\).",
             f"\\(P({dstr(z1)} < Z < {dstr(z2)}) = P(Z < {dstr(z2)}) - P(Z < {dstr(z1)})\\), and \\(P(Z < {dstr(z1)}) = 1 - {dstr(p1)} = {dstr(1 - p1)}\\).",
             f"\\(= {dstr(p2)} - {dstr(1 - p1)} = {dstr(ans)}\\)."],
            "Any normal variable is standardised by \\(z = \\frac{x - \\mu}{\\sigma}\\); then the standard normal table applies.",
            "Write the \\(z\\)-values, sketch, then combine table values.",
            quicker="Check the size against the empirical rule.",
            common_errors=[err(dstr(p2 - p1), "careless error", "sign error", "The lower value is below the mean: use symmetry, \\(P(Z < -a) = 1 - P(Z < a)\\).", step=2),
                           err(dstr(p2 + p1), "conceptual", ND, "A probability can't exceed 1; subtract the area below the lower value.", step=3)],
            skill="Find a probability for a general normal distribution.",
            checkpoints=[cp(dstr(z1), "z-score of the lower value", step=1), cp(dstr(z2), "z-score of the upper value", step=1)],
            params={"form": "between", "mu": mu, "sigma": sigma, "x1": x1, "x2": x2},
        )
    xa, za = _score(r, mu, sigma, 0.3, 2.5, 1)
    xb, zb = _score(r, mu, sigma, 0.2, 2.2, -1)
    N_ = pick(r, [200, 500, 1000, 2000])
    pa, pb = phi4(za), phi4(-zb)
    text = multipart(f"{intro} {given(za, -zb)}",
                     [("a", f"Find the \\(z\\)-score of {xa} {unit}.", 1),
                      ("b", f"Find the probability that a value is more than {xa} {unit}.", 1),
                      ("c", f"Find the probability that a value is between {xb} and {xa} {unit}.", 2),
                      ("d", f"In a sample of {N_}, how many values would you expect to exceed {xa} {unit}? Answer to the nearest whole number.", 1)])
    steps = [f"(a) \\(z = \\dfrac{{{xa} - {mu}}}{{{sigma}}} = {dstr(za)}\\).",
             f"(b) \\(P(Z > {dstr(za)}) = 1 - {dstr(pa)} = {dstr(1 - pa)}\\).",
             f"(c) \\({xb}\\) has \\(z = {dstr(zb)}\\); \\(P(Z < {dstr(zb)}) = 1 - {dstr(pb)} = {dstr(1 - pb)}\\).",
             f"\\(P({dstr(zb)} < Z < {dstr(za)}) = {dstr(pa)} - {dstr(1 - pb)} = {dstr(pa - 1 + pb)}\\).",
             f"(d) \\({N_}\\times {dstr(1 - pa)} = {dstr(N_ * (1 - pa))} \\approx {rnd(N_ * (1 - pa), 0)}\\)."]
    return Generated(
        text, A_parts(P("a", 1, A_num(dstr(za))), P("b", 1, A_p(1 - pa)), P("c", 2, A_p(pa - 1 + pb)), P("d", 1, A_round(N_ * (1 - pa), 0))), 5, 3, steps,
        "Standardise, use the table with complements and symmetry, and multiply a probability by the sample size for an expected count.",
        "Show each \\(z\\)-score and each table value — HSC marking rewards the setting out.",
        quicker="(d) should be a sensible fraction of the sample: compare with (b).",
        common_errors=[err(dstr(-za), "careless error", "sign error", "Subtract the mean from the value.", step=1, part="a"),
                       err(dstr(pa), "interpretation", ND, "That is the area to the left; 'more than' needs the right tail.", step=2, part="b"),
                       err(dstr(pa - pb), "careless error", "sign error", "The lower value is below the mean: use symmetry.", step=3, part="c"),
                       err(rnd(N_ * pa, 0), "interpretation", ND, "Use the probability of exceeding the value, from (b).", step=5, part="d")],
        skill="Solve a multi-step problem with a general normal distribution.",
        params={"form": "parts", "mu": mu, "sigma": sigma, "xa": xa, "xb": xb, "N": N_},
    )


# ======================================================================= 10F ===
ZQ = [("10", "1.28"), ("5", "1.64"), ("2.5", "1.96"), ("1", "2.33"), ("20", "0.84"), ("15", "1.04"), ("25", "0.67")]


def t_10F(r: Rng, d: int) -> Generated:
    mu, sigma, scene, unit = _normal(r)
    intro = f"{scene} are normally distributed with mean {mu} {unit} and standard deviation {sigma} {unit}."
    if d == 1:
        if r.random() < 0.5:
            k1, k2 = pick(r, [(1, 2), (2, 1), (1, 1), (2, 2), (1, 3), (3, 3)])
            N_ = pick(r, [200, 400, 1000, 2000])
            while (emp_between(k1, k2) * N_).q != 1:  # a whole-number expected count
                N_ *= 10
            cnt = emp_between(k1, k2) * N_
            return Generated(
                f"{intro} In a sample of {N_}, use the empirical rule (68–95–99.7) to estimate how many values lie between {mu - k1 * sigma} and {mu + k2 * sigma} {unit}.",
                A_approx(dstr(cnt), 0.5), 2, 1,
                [f"The bounds are \\(z = -{k1}\\) and \\(z = {k2}\\): about {dstr(emp_between(k1, k2) * 100)}% of values.",
                 f"\\({dstr(emp_between(k1, k2))}\\times {N_} = {dstr(cnt)}\\)."],
                "An expected count is the sample size times the probability.",
                "Find the percentage with the empirical rule first, then scale to the sample.",
                quicker="The count must be less than the sample size and more than half of it for a region containing the mean and at least one sd each side.",
                common_errors=[err(dstr(EMP[max(k1, k2)] * N_), "incomplete reasoning", ND, "The region isn't symmetric unless the two bounds are equally far from the mean.", step=1),
                               err(dstr(emp_between(k1, k2) * 100), "interpretation", ND, "That is the percentage; multiply the proportion by the sample size.", step=2)],
                skill="Estimate a count with the empirical rule.",
                params={"form": "count", "k1": k1, "k2": k2, "N": N_},
            )
        top, zq = pick(r, ZQ)
        cut = mu + sp.Rational(zq) * sigma
        return Generated(
            f"{intro} The top {top}% of values lie above a cut-off. Given that \\(P(Z < {zq}) \\approx {dstr(1 - sp.Rational(top) / 100)}\\), find the cut-off.",
            A_approx(dstr(cut), max(0.05, 0.004 * sigma)), 2, 1,
            [f"The cut-off has \\(z = {zq}\\).", f"\\(x = \\mu + z\\sigma = {mu} + {zq}\\times {sigma} = {dstr(cut)}\\) {unit}."],
            "A percentile of a normal distribution comes from its \\(z\\)-value: \\(x = \\mu + z\\sigma\\).",
            "Identify the \\(z\\)-value for the given area, then un-standardise.",
            quicker="The top few percent lie well above the mean, so the cut-off must exceed the mean.",
            common_errors=[err(dstr(mu - sp.Rational(zq) * sigma), "careless error", "sign error", "The TOP values lie above the mean: add \\(z\\sigma\\).", step=2),
                           err(dstr(mu + sp.Rational(zq)), "formula selection", ND, "Multiply \\(z\\) by the standard deviation.", step=2)],
            skill="Find a cut-off value for a normal distribution.",
            params={"form": "cut", "mu": mu, "sigma": sigma, "zq": zq},
        )
    if d == 2:
        if r.random() < 0.5:
            lo, zl = _score(r, mu, sigma, 0.8, 2.5, -1)
            hi, zh = _score(r, mu, sigma, 0.8, 2.5, 1)
            N_ = pick(r, [500, 1000, 2000, 5000])
            pl_, ph_ = phi4(-zl), phi4(zh)
            rej = (1 - pl_) + (1 - ph_)
            text = multipart(
                f"{intro} An item is rejected if it is below {lo} {unit} or above {hi} {unit}. {given(-zl, zh)}",
                [("a", "Find the proportion of items that are rejected.", 2),
                 ("b", f"In a batch of {N_} items, how many would you expect to be rejected? Answer to the nearest whole number.", 1)])
            steps = [f"(a) \\(z\\)-scores: \\({dstr(zl)}\\) and \\({dstr(zh)}\\).",
                     f"\\(P(Z < {dstr(zl)}) = 1 - {dstr(pl_)} = {dstr(1 - pl_)}\\); \\(P(Z > {dstr(zh)}) = 1 - {dstr(ph_)} = {dstr(1 - ph_)}\\).",
                     f"Rejected: \\({dstr(1 - pl_)} + {dstr(1 - ph_)} = {dstr(rej)}\\).",
                     f"(b) \\({N_}\\times {dstr(rej)} = {dstr(N_ * rej)} \\approx {rnd(N_ * rej, 0)}\\)."]
            return Generated(
                text, A_parts(P("a", 2, A_p(rej)), P("b", 1, A_round(N_ * rej, 0))), 3, 2, steps,
                "Quality control: the rejected proportion is the area in both tails beyond the specification limits.",
                "Standardise both limits and add the two tail areas.",
                quicker="Check with the empirical rule: limits about 2 sd away reject roughly 5%.",
                common_errors=[err(dstr(1 - rej), "interpretation", ND, "That is the proportion accepted.", step=3, part="a"),
                               err(dstr(1 - ph_), "incomplete reasoning", ND, "Items can be rejected at both ends: add the lower tail too.", step=3, part="a")],
                skill="Use the normal distribution for quality control.",
                params={"form": "qc", "mu": mu, "sigma": sigma, "lo": lo, "hi": hi, "N": N_},
            )
        top, zq = pick(r, ZQ)
        a_ = mu + r.randint(1, 3) * sigma
        new_mu = a_ - sp.Rational(zq) * sigma
        return Generated(
            f"A machine fills packets with a standard deviation of {sigma} g. The mean can be adjusted. Only {top}% of packets may weigh more than {a_} g. "
            f"Given that \\(P(Z < {zq}) \\approx {dstr(1 - sp.Rational(top) / 100)}\\), find the largest mean that achieves this.",
            A_approx(dstr(new_mu), max(0.05, 0.004 * sigma), "g"), 3, 2,
            [f"\\(P(X > {a_}) = {dstr(sp.Rational(top) / 100)}\\) means {a_} g has \\(z = {zq}\\).",
             f"\\(\\dfrac{{{a_} - \\mu}}{{{sigma}}} = {zq}\\).",
             f"\\(\\mu = {a_} - {zq}\\times {sigma} = {dstr(new_mu)}\\) g."],
            "Working backwards: a known tail area fixes the \\(z\\)-value of the boundary, and \\(z = \\frac{x - \\mu}{\\sigma}\\) then gives the unknown mean.",
            "Write the standardising equation with the unknown and solve it.",
            quicker="The mean must sit below the limit by \\(z\\) standard deviations.",
            common_errors=[err(dstr(a_ + sp.Rational(zq) * sigma), "careless error", "sign error", "The limit is ABOVE the mean, so subtract \\(z\\sigma\\).", step=3),
                           err(dstr(a_ - sp.Rational(zq)), "algebraic", "algebra", "Multiply \\(z\\) by \\(\\sigma\\) when rearranging.", step=3)],
            skill="Find an unknown mean from a normal probability.",
            params={"form": "mean", "a": a_, "sigma": sigma, "zq": zq},
        )
    top, zq = pick(r, ZQ)
    k = pick(r, [1, 2, 3])
    xa, za = _score(r, mu, sigma, 0.3, 2.5, 1)
    pa = phi4(za)
    cut = mu + sp.Rational(zq) * sigma
    text = multipart(
        f"{intro} {given(za)}",
        [("a", f"Find the probability that a value exceeds {xa} {unit}.", 1),
         ("b", f"Using the empirical rule, what percentage of values lie within {k} standard deviation{'s' if k > 1 else ''} of the mean?", 1),
         ("c", f"The top {top}% of values are labelled 'premium'. Given \\(P(Z < {zq}) \\approx {dstr(1 - sp.Rational(top) / 100)}\\), find the smallest premium value.", 1),
         ("d", f"The mean is to be changed (the standard deviation stays {sigma} {unit}) so that only {top}% of values exceed {xa} {unit}. Find the new mean.", 2)])
    new_mu = xa - sp.Rational(zq) * sigma
    steps = [f"(a) \\(z = \\dfrac{{{xa} - {mu}}}{{{sigma}}} = {dstr(za)}\\); \\(P(Z > {dstr(za)}) = 1 - {dstr(pa)} = {dstr(1 - pa)}\\).",
             f"(b) About {dstr(EMP[k] * 100)}% (the empirical rule).",
             f"(c) \\(x = {mu} + {zq}\\times {sigma} = {dstr(cut)}\\) {unit}.",
             f"(d) Now {xa} must have \\(z = {zq}\\): \\(\\dfrac{{{xa} - \\mu}}{{{sigma}}} = {zq}\\).",
             f"\\(\\mu = {xa} - {zq}\\times {sigma} = {dstr(new_mu)}\\) {unit}."]
    return Generated(
        text, A_parts(P("a", 1, A_p(1 - pa)), P("b", 1, A_approx(dstr(EMP[k] * 100), 0.05, "%")),
                      P("c", 1, A_approx(dstr(cut), max(0.05, 0.004 * sigma))), P("d", 2, A_approx(dstr(new_mu), max(0.05, 0.004 * sigma)))), 5, 3, steps,
        "Normal models answer forwards questions (value → probability) and backwards ones (probability → value, or → an unknown mean).",
        "For backwards questions write \\(z = \\frac{x - \\mu}{\\sigma}\\) with the unknown and solve.",
        quicker="(d) must move the mean down if the tail above the value is to shrink.",
        common_errors=[err(dstr(pa), "interpretation", ND, "'Exceeds' needs the right tail.", step=1, part="a"),
                       err(dstr(EMP[k] * 50), "conceptual", ND, "'Within' covers both sides of the mean.", step=2, part="b"),
                       err(dstr(mu - sp.Rational(zq) * sigma), "careless error", "sign error", "The top values lie above the mean.", step=3, part="c"),
                       err(dstr(xa + sp.Rational(zq) * sigma), "careless error", "sign error", "The value is above the mean: subtract \\(z\\sigma\\).", step=5, part="d")],
        skill="Apply the normal distribution forwards and backwards in context.",
        params={"form": "parts", "mu": mu, "sigma": sigma, "xa": xa, "zq": zq, "k": k},
    )
