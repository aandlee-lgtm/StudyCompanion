"""Chapter 8 — Series and finance (owner: maths).

Money answers are stored as compact exact expressions such as ``5000*(1+0.005)^120`` (never as a
huge expanded fraction) and marked to the nearest cent or dollar as the question asks. Every
template's ``params`` let the test-suite re-simulate the account period by period."""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

import sympy as sp

from app.services.maths_tpl_base import (
    A_num, A_parts, A_round, A_units, Generated, L, P, Rng, err, money, multipart, ordinal, pick, rnd,
)
from app.services.maths_tpl_base import dollars as _dollars

FIN = "financial periods"
SEQ = "sequence formula"
SER = "series formula"
MONTHLY = ["3.6", "4.8", "6", "7.2", "8.4", "9.6"]   # R/12 terminates: 0.003 … 0.008
ANNUAL = ["2.5", "3", "4", "4.5", "5", "5.5", "6"]
QUARTERLY = ["3", "4", "5", "6", "7", "8"]


def dollars(v, dp: int = 2) -> str:
    return _dollars(v, dp)


def R_(s: str) -> sp.Rational:
    return sp.Rational(s)


def dec(q) -> str:
    """A terminating rational as a plain decimal string: 1/200 -> '0.005', 21/20 -> '1.05'."""
    q = sp.Rational(q)
    d = Decimal(int(q.p)) / Decimal(int(q.q))
    s = format(d.normalize(), "f")
    return s


def val(expr: str) -> sp.Rational:
    """Exact value of a stored money expression (for display and checks only)."""
    return sp.nsimplify(sp.sympify(expr.replace("^", "**")))


def fl(expr: str) -> float:
    return float(sp.N(sp.sympify(expr.replace("^", "**")), 30))


def cents(expr: str, dp: int = 2) -> Decimal:
    return Decimal(str(sp.N(sp.sympify(expr.replace("^", "**")), 40))).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)


def m2(expr: str, dp: int = 2) -> str:
    """LaTeX money for a stored expression, rounded as the question asks."""
    return money(cents(expr, dp), dp)


def grow(r: str, n) -> str:
    return f"(1 + {r})^{n}"


def fv_str(M, r: str, n) -> str:
    """Future value of n end-of-period deposits M at rate r per period."""
    return f"{M}*((1 + {r})^{n} - 1)/{r}"


def first_n(cond, limit: int = 2000) -> int:
    """Smallest positive integer n for which cond(n) holds (exact arithmetic in cond)."""
    for n_ in range(1, limit):
        if cond(n_):
            return n_
    raise ValueError("no n found")


def pct(s: str) -> str:
    return f"{s}%"


def plain(v) -> str:
    """A whole number with thousands separators for maths mode: 12{,}000."""
    return f"{int(v):,}".replace(",", "{,}")


# ======================================================================= 8A ===
def t_8A(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            first, inc, rows = r.randint(12, 30), r.randint(2, 4), r.randint(12, 30)
            total = rows * (2 * first + (rows - 1) * inc) // 2
            return Generated(
                f"A theatre has {first} seats in the front row, and each row has {inc} more seats than the row in front of it. "
                f"There are {rows} rows. How many seats are there altogether?",
                A_num(total), 2, 1,
                [f"The numbers of seats form an arithmetic sequence with \\(a = {first}\\), \\(d = {inc}\\) and \\(n = {rows}\\).",
                 f"\\(S_{{{rows}}} = \\dfrac{{{rows}}}{{2}}\\left(2\\times {first} + {rows - 1}\\times {inc}\\right) = {total}\\) seats."],
                "A constant increase from one row to the next is an arithmetic sequence; the total is an arithmetic series.",
                "Define \\(a\\), \\(d\\) and \\(n\\) in words before substituting.",
                quicker=f"Last row \\(= {first + (rows - 1) * inc}\\); total \\(= \\frac{{n}}{{2}}(\\text{{first}} + \\text{{last}})\\).",
                common_errors=[err(first + (rows - 1) * inc, "interpretation", SER, "That is the number of seats in the back row; the question asks for the total.", step=2),
                               err(rows * (2 * first + rows * inc) // 2, "formula selection", SER, "Use \\((n - 1)d\\), not \\(nd\\), in the sum formula.", step=2),
                               err(rows * (2 * first + (rows - 1) * inc), "formula selection", SER, "You forgot to halve: \\(S_n = \\frac{n}{2}(\\ldots)\\).", step=2)],
                skill="Model a constant increase with an arithmetic series.",
                params={"form": "seats", "a": first, "d": inc, "n": rows},
            )
        S0 = pick(r, [48000, 52000, 60000, 65000, 70000])
        p = pick(r, ["2", "2.5", "3", "3.5", "4"])
        yr = r.randint(5, 12)
        ratio = dec(1 + R_(p) / 100)
        v = f"{S0}*{ratio}^{yr - 1}"
        return Generated(
            f"Ava's starting salary is {dollars(S0, 0)} per year. Each year her salary increases by {pct(p)} of the previous year's salary. "
            f"What is her salary in her {ordinal(yr)} year of work? Answer to the nearest dollar.",
            A_round(v, 0, "$"), 2, 1,
            [f"Each year the salary is multiplied by \\({ratio}\\): a geometric sequence with \\(a = {plain(S0)}\\) and \\(r = {ratio}\\).",
             f"\\(T_{{{yr}}} = ar^{{{yr - 1}}} = {plain(S0)}\\times {ratio}^{{{yr - 1}}} \\approx {m2(v, 0)}\\)."],
            "A percentage increase multiplies by the same factor each year, so salaries form a geometric sequence.",
            "Convert the percentage to the ratio \\(1 + \\frac{p}{100}\\) and quote \\(T_n = ar^{n-1}\\).",
            quicker="The first year is \\(n = 1\\) with no increase yet, so the power is always one less than the year number.",
            common_errors=[err(rnd(f"{S0}*{ratio}^{yr}", 0), "formula selection", SEQ, "Use \\(r^{n-1}\\): the first year has had no increase.", step=2),
                           err(rnd(f"{S0}*(1 + {yr - 1}*{p}/100)", 0), "formula selection", SEQ,
                               "That adds the same amount each year; a percentage increase multiplies, so the sequence is geometric.", step=1)],
            skill="Model percentage growth with a geometric sequence.",
            params={"form": "salary", "S0": S0, "p": p, "yr": yr},
        )
    if d == 2:
        a = pick(r, [50000, 55000, 60000, 64000])
        inc = pick(r, [1500, 2000, 2500, 3000])
        b = a - pick(r, [0, 2000, 4000])
        p = pick(r, ["3", "4", "5"])
        N = pick(r, [5, 8, 10, 12])
        ratio = dec(1 + R_(p) / 100)
        totA = N * (2 * a + (N - 1) * inc) // 2
        vB = f"{b}*({ratio}^{N} - 1)/({ratio} - 1)"
        text = multipart(
            f"Job A pays {dollars(a, 0)} in the first year, and the salary rises by {dollars(inc, 0)} each year. "
            f"Job B pays {dollars(b, 0)} in the first year, and the salary rises by {pct(p)} each year.",
            [("a", f"Find the total earned in Job A over the first {N} years.", 1),
             ("b", f"Find the total earned in Job B over the first {N} years, to the nearest dollar.", 2)])
        return Generated(
            text, A_parts(P("a", 1, A_units(totA, "$")), P("b", 2, A_round(vB, 0, "$"))), 3, 2,
            [f"(a) Arithmetic series: \\(S_{{{N}}} = \\dfrac{{{N}}}{{2}}\\left(2\\times {plain(a)} + {N - 1}\\times {plain(inc)}\\right) = {money(totA, 0)}\\).",
             f"(b) Geometric series with \\(a = {plain(b)}\\), \\(r = {ratio}\\): \\(S_{{{N}}} = \\dfrac{{{plain(b)}\\left({ratio}^{{{N}}} - 1\\right)}}{{{ratio} - 1}}\\).",
             f"\\(\\approx {m2(vB, 0)}\\)."],
            "A fixed dollar rise gives an arithmetic series; a percentage rise gives a geometric series.",
            "Name the type of series before choosing a formula.",
            quicker="Check (b) against \\(N\\) times the average of the first and last salaries — it should be close.",
            common_errors=[err(a + (N - 1) * inc, "interpretation", SER, "That is the salary in the last year, not the total.", step=1, part="a"),
                           err(rnd(f"{b}*{ratio}^{N - 1}", 0), "interpretation", SER, "That is the salary in year \\(N\\); the question asks for the total.", step=2, part="b"),
                           err(rnd(f"{b}*({ratio}^{N - 1} - 1)/({ratio} - 1)", 0), "formula selection", SER, "The sum of \\(n\\) terms uses \\(r^n\\), not \\(r^{n-1}\\).", step=2, part="b")],
            skill="Compare arithmetic and geometric growth in context.",
            params={"form": "compare", "a": a, "inc": inc, "b": b, "p": p, "N": N},
        )
    while True:
        a = pick(r, [50000, 55000, 60000, 62000])
        inc = pick(r, [1200, 1500, 1800, 2000])
        b = a - pick(r, [3000, 4000, 5000, 6000])
        p = pick(r, ["4", "4.5", "5", "6"])
        rq = 1 + R_(p) / 100
        try:
            y = first_n(lambda n_: b * rq ** (n_ - 1) > a + (n_ - 1) * inc, 60)
        except ValueError:
            continue
        if 3 <= y <= 30:
            break
    ratio = dec(rq)
    N = pick(r, [10, 15, 20])
    n1 = r.randint(5, 12)
    vB = f"{b}*({ratio}^{N} - 1)/({ratio} - 1)"
    sA = lambda n_: a + (n_ - 1) * inc  # noqa: E731
    sB = lambda n_: f"{b}*{ratio}^{n_ - 1}"  # noqa: E731
    text = multipart(
        f"Job A pays {dollars(a, 0)} in the first year, and the salary rises by {dollars(inc, 0)} each year. "
        f"Job B pays {dollars(b, 0)} in the first year, and the salary rises by {pct(p)} each year.",
        [("a", f"Find the salary for Job A in year {n1}.", 1),
         ("b", f"Find the total earned in Job B over the first {N} years, to the nearest dollar.", 2),
         ("c", "In which year does the annual salary for Job B first exceed the annual salary for Job A?", 2)])
    steps = [f"(a) Job A is arithmetic: \\(T_{{{n1}}} = {plain(a)} + {n1 - 1}\\times {plain(inc)} = {money(sA(n1), 0)}\\).",
             f"(b) Job B is geometric with \\(r = {ratio}\\): \\(S_{{{N}}} = \\dfrac{{{plain(b)}\\left({ratio}^{{{N}}} - 1\\right)}}{{{ratio} - 1}} \\approx {m2(vB, 0)}\\).",
             f"(c) We need \\({plain(b)}\\times {ratio}^{{n-1}} > {plain(a)} + (n - 1)\\times {plain(inc)}\\). Tabulate near the crossing:",
             f"Year {y - 1}: B \\(\\approx {m2(sB(y - 1), 0)}\\), A \\(= {money(sA(y - 1), 0)}\\); year {y}: B \\(\\approx {m2(sB(y), 0)}\\), A \\(= {money(sA(y), 0)}\\).",
             f"So Job B first pays more in year {y}."]
    return Generated(
        text, A_parts(P("a", 1, A_units(sA(n1), "$")), P("b", 2, A_round(vB, 0, "$")), P("c", 2, A_num(y))), 5, 3, steps,
        "Linear (arithmetic) growth adds a fixed amount; geometric growth multiplies, so it eventually overtakes any arithmetic sequence.",
        "When an equation mixes \\(r^{n}\\) and \\(n\\), tabulate values around the crossing and state both years you checked.",
        quicker="Estimate the crossing first: B's yearly rise is about the percentage of its salary; compare that with A's fixed rise.",
        common_errors=[err(a + n1 * inc, "formula selection", SEQ, "Use \\((n - 1)d\\): year 1 has had no rise yet.", step=1, part="a"),
                       err(rnd(f"{b}*({ratio}^{N - 1} - 1)/({ratio} - 1)", 0), "formula selection", SER, "The sum of \\(n\\) terms uses \\(r^n\\).", step=2, part="b"),
                       err(y - 1, "careless error", "inequality direction", f"In year {y - 1} Job B still pays less: check the year on each side of the crossing.", step=4, part="c")],
        skill="Compare arithmetic and geometric models and find when one overtakes the other.",
        params={"form": "cross", "a": a, "inc": inc, "b": b, "p": p, "N": N, "n1": n1},
    )


# ======================================================================= 8B ===
def t_8B(r: Rng, d: int) -> Generated:
    if d == 1:
        p = pick(r, ["2.5", "3", "4", "5", "6", "8"])
        mult = pick(r, [2, 3])
        rq = 1 + R_(p) / 100
        ratio = dec(rq)
        nn = first_n(lambda n_: rq**n_ >= mult)
        exact = math.log(mult) / math.log(float(rq))
        word = "double" if mult == 2 else "triple"
        return Generated(
            f"An investment grows by {pct(p)} each year, so after \\(n\\) years it is worth \\(P\\times {ratio}^n\\), where \\(P\\) is the amount invested. "
            f"Use logarithms to find the smallest whole number of years for the investment to {word} in value.",
            A_num(nn), 2, 1,
            [f"\\(P\\times {ratio}^n \\ge {mult}P\\), so \\({ratio}^n \\ge {mult}\\) and \\(n\\ln {ratio} \\ge \\ln {mult}\\).",
             f"\\(n \\ge \\dfrac{{\\ln {mult}}}{{\\ln {ratio}}} \\approx {exact:.3f}\\), so it takes {nn} years (round up)."],
            "Taking logarithms brings the unknown index down: \\(\\ln(r^n) = n\\ln r\\).",
            "The answer is a whole number of years: round up, and say why.",
            quicker="The 'rule of 72' (\\(72 \\div\\) rate) estimates doubling times — use it to check the size of your answer.",
            common_errors=[err(nn - 1, "careless error", "inequality direction", f"After {nn - 1} years it has not yet reached {mult} times its value: round up.", step=2),
                           err(rnd(exact, 2), "interpretation", "rounding", "\\(n\\) counts whole years: round the logarithm result up to a whole number.", step=2)],
            skill="Solve a growth inequality with logarithms.",
            params={"form": "multiply", "p": p, "mult": mult},
        )
    if d == 2:
        V0 = pick(r, [18000, 24000, 30000, 36000, 45000])
        p = pick(r, ["10", "12", "15", "18", "20"])
        rq = 1 - R_(p) / 100
        ratio = dec(rq)
        n1 = r.randint(3, 6)
        B = pick(r, [V0 // 4, V0 // 5, V0 // 3])
        nn = first_n(lambda n_: V0 * rq**n_ < B)
        exact = math.log(B / V0) / math.log(float(rq))
        v1 = f"{V0}*{ratio}^{n1}"
        text = multipart(
            f"A car bought for {dollars(V0, 0)} depreciates by {pct(p)} of its value each year.",
            [("a", f"Find its value after {n1} years, to the nearest dollar.", 1),
             ("b", f"Use logarithms to find after how many complete years its value first falls below {dollars(B, 0)}.", 2)])
        steps = [f"(a) Each year the value is multiplied by \\(1 - {dec(R_(p) / 100)} = {ratio}\\): \\(V = {plain(V0)}\\times {ratio}^{{{n1}}} \\approx {m2(v1, 0)}\\).",
                 f"(b) \\({plain(V0)}\\times {ratio}^n < {plain(B)}\\), so \\(n\\ln {ratio} < \\ln {L(sp.Rational(B, V0))}\\).",
                 f"\\(\\ln {ratio} < 0\\), so dividing reverses the inequality: \\(n > {exact:.3f}\\), i.e. after {nn} years."]
        return Generated(
            text, A_parts(P("a", 1, A_round(v1, 0, "$")), P("b", 2, A_num(nn))), 3, 2, steps,
            "Depreciation by a fixed percentage multiplies the value by \\(1 - \\frac{p}{100}\\) each year: a GP with \\(r < 1\\).",
            "When you divide by the logarithm of a number less than 1, reverse the inequality and say so.",
            quicker=f"Check: \\(V({nn - 1})\\) is still above {dollars(B, 0)} and \\(V({nn})\\) is below.",
            common_errors=[err(rnd(f"{V0}*{dec(1 + R_(p) / 100)}^{n1}", 0), "careless error", "sign error", "Depreciation multiplies by \\(1 - \\frac{p}{100}\\), not \\(1 + \\frac{p}{100}\\).", step=1, part="a"),
                           err(rnd(f"{V0}*(1 - {n1}*{p}/100)", 0), "formula selection", SEQ, "That removes the same dollar amount each year; the value falls by a percentage of its current value.", step=1, part="a"),
                           err(nn - 1, "careless error", "inequality direction", "Dividing by \\(\\ln\\) of a number below 1 reverses the inequality; then round up.", step=3, part="b")],
            skill="Use logarithms with a decreasing geometric sequence.",
            params={"form": "dep", "V0": V0, "p": p, "n1": n1, "B": B},
        )
    h = pick(r, [2, 3, 4, 5, 6, 8, 10])
    f = pick(r, [sp.Rational(3, 4), sp.Rational(2, 3), sp.Rational(4, 5), sp.Rational(3, 5), sp.Rational(1, 2)])
    k_ = r.randint(3, 6)
    bound = pick(r, [sp.Rational(1, 10), sp.Rational(1, 20), sp.Rational(1, 5)])
    nb = first_n(lambda n_: h * f**n_ < bound)
    hk = h * f**k_
    total = h + 2 * h * f / (1 - f)
    exact = math.log(float(bound / h)) / math.log(float(f))
    text = multipart(
        f"A ball is dropped from a height of {h} m. After each bounce it rises to \\({L(f)}\\) of the height from which it last fell.",
        [("a", f"Find the height of the {ordinal(k_)} rebound, in metres correct to 2 decimal places.", 1),
         ("b", f"Use logarithms to find the first rebound that is lower than \\({dec(bound)}\\) m. Give its rebound number.", 2),
         ("c", "Find the total distance the ball travels before it comes to rest.", 2)])
    steps = [f"(a) The rebounds form a GP with first term \\({L(h * f)}\\) and ratio \\({L(f)}\\): the {ordinal(k_)} rebound is \\({h}\\left({L(f)}\\right)^{{{k_}}} = {L(hk)} \\approx {float(hk):.2f}\\) m.",
             f"(b) \\({h}\\left({L(f)}\\right)^n < {dec(bound)}\\), so \\(n\\ln {L(f)} < \\ln {L(bound / h)}\\).",
             f"\\(\\ln {L(f)} < 0\\), so \\(n > {exact:.3f}\\): the {ordinal(nb)} rebound.",
             f"(c) The ball falls {h} m once, then travels each rebound height twice (up and down): \\({h} + 2\\times\\dfrac{{{L(h * f)}}}{{1 - {L(f)}}}\\).",
             f"\\(= {L(total)}\\) m."]
    return Generated(
        text, A_parts(P("a", 1, A_round(hk, 2, "m")), P("b", 2, A_num(nb)), P("c", 2, A_units(total, "m"))), 5, 3, steps,
        "Successive rebound heights form a geometric sequence with ratio below 1; the total distance uses its limiting sum.",
        "Draw the first two bounces: the first drop is travelled once, every rebound height twice.",
        quicker="The limiting sum \\(\\frac{a}{1 - r}\\) applies because \\(0 < r < 1\\); state that condition.",
        common_errors=[err(rnd(h * f ** (k_ - 1), 2), "formula selection", SEQ, "The first rebound is already \\(h r\\), so the \\(k\\)th rebound is \\(h r^k\\).", step=1, part="a"),
                       err(nb - 1, "careless error", "inequality direction", "Dividing by a negative logarithm reverses the inequality; round up to the next rebound.", step=3, part="b"),
                       err(h / (1 - f), "incomplete reasoning", SER, "That counts each height once; every rebound is travelled up and down.", step=4, part="c"),
                       err(2 * h / (1 - f), "careless error", SER, "The initial drop is only travelled once (down, not up).", step=4, part="c")],
        skill="Geometric sequences and limiting sums in a bouncing-ball model.",
        params={"form": "ball", "h": h, "f": str(f), "k": k_, "bound": str(bound)},
    )


# ======================================================================= 8C ===
def t_8C(r: Rng, d: int) -> Generated:
    if d == 1:
        P0 = pick(r, [2000, 4000, 5000, 6000, 8000, 12000, 15000])
        R = pick(r, ANNUAL)
        yrs = r.randint(2, 8)
        if r.random() < 0.5:
            I = P0 * R_(R) / 100 * yrs
            return Generated(
                f"Find the simple interest earned when {dollars(P0, 0)} is invested at {pct(R)} p.a. for {yrs} years.",
                A_units(I, "$"), 1, 1,
                [f"\\(I = Prn = {plain(P0)}\\times {dec(R_(R) / 100)}\\times {yrs} = {money(I)}\\)."],
                "Simple interest is the same each year: \\(I = Prn\\), with \\(r\\) as a decimal.",
                "Convert the percentage to a decimal before substituting.",
                quicker=f"One year's interest is {dollars(P0 * R_(R) / 100)}; multiply by {yrs}.",
                common_errors=[err(rnd(f"{P0}*(1 + {R}/100)^{yrs} - {P0}", 2), "formula selection", FIN, "That is compound interest; simple interest is \\(Prn\\).", step=1),
                               err(P0 + I, "interpretation", FIN, "That is the final amount; the question asks for the interest.", step=1)],
                skill="Calculate simple interest.",
                params={"form": "simple", "P": P0, "R": R, "n": yrs},
            )
        v = f"{P0}*{grow(dec(R_(R) / 100), yrs)}"
        return Generated(
            f"{dollars(P0, 0)} is invested at {pct(R)} p.a., compounded annually. Find the value of the investment after {yrs} years, to the nearest cent.",
            A_round(v, 2, "$"), 2, 1,
            [f"\\(A = P(1 + r)^n\\) with \\(r = {dec(R_(R) / 100)}\\) and \\(n = {yrs}\\).",
             f"\\(A = {plain(P0)}\\times {dec(1 + R_(R) / 100)}^{{{yrs}}} \\approx {m2(v)}\\)."],
            "Compound interest earns interest on the interest: the amount grows geometrically, \\(A = P(1 + r)^n\\).",
            "Write the formula, the substitution and the rounded answer with units.",
            quicker="Simple interest gives a slightly smaller amount — use it as a check that your answer is a little larger.",
            common_errors=[err(rnd(f"{P0}*(1 + {yrs}*{R}/100)", 2), "formula selection", FIN, "That is simple interest; with compounding, multiply by \\(1 + r\\) each year.", step=2),
                           err(rnd(f"{P0}*{grow(dec(R_(R) / 100), yrs)} - {P0}", 2), "interpretation", FIN, "That is the interest; the question asks for the value of the investment.", step=2)],
            skill="Calculate a compound interest amount.",
            params={"form": "compound", "P": P0, "R": R, "n": yrs, "m": 1},
        )
    if d == 2:
        P0 = pick(r, [3000, 5000, 8000, 10000, 20000])
        if r.random() < 0.6:
            freq, m = pick(r, [("monthly", 12), ("quarterly", 4)])
            R = pick(r, MONTHLY if m == 12 else QUARTERLY)
            yrs = r.randint(3, 10)
            rp = dec(R_(R) / (100 * m))
            v = f"{P0}*{grow(rp, m * yrs)}"
            return Generated(
                f"{dollars(P0, 0)} is invested at {pct(R)} p.a., compounded {freq}. Find the value of the investment after {yrs} years, to the nearest cent.",
                A_round(v, 2, "$"), 2, 2,
                [f"Per period: \\(r = \\dfrac{{{dec(R_(R) / 100)}}}{{{m}}} = {rp}\\); number of periods \\(n = {m}\\times {yrs} = {m * yrs}\\).",
                 f"\\(A = {plain(P0)}\\times {dec(1 + R_(rp))}^{{{m * yrs}}} \\approx {m2(v)}\\)."],
                "The rate and the number of periods must both match the compounding period.",
                "Write \\(r\\) per period and \\(n\\) in periods explicitly before substituting.",
                quicker="More frequent compounding gives slightly more than annual compounding — compare the two.",
                common_errors=[err(rnd(f"{P0}*{grow(dec(R_(R) / 100), yrs)}", 2), "formula selection", FIN, f"That compounds annually; here interest is added {freq}.", step=1),
                               err(rnd(f"{P0}*{grow(rp, yrs)}", 2), "formula selection", FIN, f"Count periods, not years: \\(n = {m * yrs}\\).", step=1)],
                skill="Compound interest with non-annual compounding.",
                params={"form": "compound", "P": P0, "R": R, "n": yrs, "m": m},
            )
        R = pick(r, ANNUAL)
        yrs = r.randint(4, 10)
        A_r = cents(f"{P0}*{grow(dec(R_(R) / 100), yrs)}")
        v = f"100*(({A_r}/{P0})^(1/{yrs}) - 1)"
        return Generated(
            f"{dollars(P0, 0)} grows to {dollars(A_r)} in {yrs} years, with interest compounded annually. "
            "Find the annual interest rate, as a percentage correct to 2 decimal places.",
            A_round(v, 2, "%"), 3, 2,
            [f"\\({plain(P0)}(1 + r)^{{{yrs}}} = {A_r}\\), so \\((1 + r)^{{{yrs}}} = \\dfrac{{{A_r}}}{{{plain(P0)}}}\\).",
             f"\\(1 + r = \\left(\\dfrac{{{A_r}}}{{{plain(P0)}}}\\right)^{{\\frac{{1}}{{{yrs}}}}}\\), so \\(r \\approx {fl(v) / 100:.6f}\\).",
             f"The rate is about \\({cents(v)}\\%\\) p.a."],
            "To find a compound rate, isolate \\((1 + r)^n\\) and take the \\(n\\)th root.",
            "Convert the decimal rate to a percentage only at the end.",
            quicker="A simple-interest estimate gives an upper bound for the compound rate.",
            common_errors=[err(rnd(f"100*({A_r}/{P0} - 1)/{yrs}", 2), "formula selection", FIN, "That is a simple-interest rate; with compounding take the \\(n\\)th root.", step=2),
                           err(rnd(f"({A_r}/{P0})^(1/{yrs}) - 1", 2), "notation", "units", "That is the decimal rate; multiply by 100 for a percentage.", step=3)],
            skill="Find a compound interest rate.",
            params={"form": "rate", "P": P0, "A": str(A_r), "n": yrs},
        )
    P0 = pick(r, [5000, 8000, 10000, 12000, 20000, 25000])
    R = pick(r, MONTHLY)
    yrs = r.randint(4, 12)
    mult = pick(r, [2, 3])
    rp = dec(R_(R) / 1200)
    va = f"{P0}*{grow(dec(R_(R) / 100), yrs)}"
    vb = f"{P0}*{grow(rp, 12 * yrs)}"
    rq = 1 + R_(R) / 100
    nn = first_n(lambda n_: rq**n_ > mult)
    exact = math.log(mult) / math.log(float(rq))
    text = multipart(
        f"{dollars(P0, 0)} is invested at {pct(R)} p.a.",
        [("a", f"Find its value after {yrs} years if interest is compounded annually, to the nearest cent.", 1),
         ("b", f"Find its value after {yrs} years if interest is compounded monthly, to the nearest cent.", 1),
         ("c", f"With interest compounded annually, use logarithms to find the number of complete years needed for the investment to exceed {dollars(mult * P0, 0)}.", 2)])
    steps = [f"(a) \\(A = {plain(P0)}\\times {dec(rq)}^{{{yrs}}} \\approx {m2(va)}\\).",
             f"(b) \\(r = \\dfrac{{{dec(R_(R) / 100)}}}{{12}} = {rp}\\) per month for \\({12 * yrs}\\) months: \\(A = {plain(P0)}\\times {dec(1 + R_(rp))}^{{{12 * yrs}}} \\approx {m2(vb)}\\).",
             f"(c) \\({plain(P0)}\\times {dec(rq)}^n > {plain(mult * P0)}\\), so \\(n > \\dfrac{{\\ln {mult}}}{{\\ln {dec(rq)}}} \\approx {exact:.3f}\\).",
             f"So {nn} complete years."]
    return Generated(
        text, A_parts(P("a", 1, A_round(va, 2, "$")), P("b", 1, A_round(vb, 2, "$")), P("c", 2, A_num(nn))), 4, 3, steps,
        "Compound interest is a geometric sequence; more frequent compounding gives a slightly larger amount, and logarithms find the time.",
        "In every part, state \\(r\\) per period and \\(n\\) in periods.",
        quicker="The answer to (b) must be a little more than (a); if not, the period conversion is wrong.",
        common_errors=[err(rnd(f"{P0}*(1 + {yrs}*{R}/100)", 2), "formula selection", FIN, "That is simple interest.", step=1, part="a"),
                       err(rnd(f"{P0}*{grow(rp, yrs)}", 2), "formula selection", FIN, f"Count months: \\(n = {12 * yrs}\\).", step=2, part="b"),
                       err(nn - 1, "careless error", "inequality direction", "Round up: after that many years it has not yet reached the target.", step=4, part="c")],
        skill="Compare compounding periods and solve for time with logarithms.",
        params={"form": "parts", "P": P0, "R": R, "n": yrs, "mult": mult},
    )


# ======================================================================= 8D ===
def t_8D(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            M, R, yrs, per, m = pick(r, [100, 150, 200, 250, 500]), pick(r, MONTHLY), r.randint(2, 10), "month", 12
        else:
            M, R, yrs, per, m = pick(r, [1000, 2000, 2500, 5000]), pick(r, ANNUAL), r.randint(5, 20), "year", 1
        rp = dec(R_(R) / (100 * m))
        N = m * yrs
        v = fv_str(M, rp, N)
        comp = "monthly" if m == 12 else "annually"
        return Generated(
            f"{dollars(M, 0)} is deposited at the end of each {per} into an account earning {pct(R)} p.a. interest, compounded {comp}. "
            f"Find the balance immediately after the last deposit at the end of {yrs} years, to the nearest cent.",
            A_round(v, 2, "$"), 2, 1,
            [f"\\(r = {rp}\\) per {per}, \\(n = {N}\\) deposits; the balance is a geometric series \\(M + M(1 + r) + \\cdots + M(1 + r)^{{n-1}}\\).",
             f"\\(A = M\\dfrac{{(1 + r)^n - 1}}{{r}} = {plain(M)}\\times\\dfrac{{{dec(1 + R_(rp))}^{{{N}}} - 1}}{{{rp}}} \\approx {m2(v)}\\)."],
            "Each deposit earns compound interest for a different number of periods; together they form a geometric series.",
            "Show the series (first few terms) before using the sum formula — HSC questions usually ask for it.",
            quicker=f"The total deposited is {dollars(M * N, 0)}; your answer must be more than that, but not by a huge amount.",
            common_errors=[err(M * N, "conceptual", FIN, "That ignores interest: each deposit grows by compound interest.", step=1),
                           err(rnd(f"{M}*(1 + {rp})^{N}", 2), "conceptual", SER, "That compounds a single deposit; there are many deposits, each with its own number of periods.", step=1)],
            skill="Find the future value of regular deposits.",
            params={"form": "fv", "M": M, "R": R, "m": m, "N": N, "due": False},
        )
    if d == 2:
        if r.random() < 0.5:
            M, R, yrs = pick(r, [1000, 2000, 3000, 5000]), pick(r, ANNUAL), r.randint(5, 20)
            rp = dec(R_(R) / 100)
            v = f"{M}*(1 + {rp})*((1 + {rp})^{yrs} - 1)/{rp}"
            return Generated(
                f"{dollars(M, 0)} is deposited at the start of each year into an account earning {pct(R)} p.a., compounded annually. "
                f"Find the balance at the end of {yrs} years, to the nearest cent.",
                A_round(v, 2, "$"), 3, 2,
                [f"The first deposit earns interest for {yrs} years, the last for 1 year: \\(A = M({dec(1 + R_(rp))})^{{{yrs}}} + \\cdots + M({dec(1 + R_(rp))})^{{1}}\\).",
                 f"This is a GP with first term \\(M(1 + r)\\), ratio \\(1 + r\\), {yrs} terms: \\(A = M(1 + r)\\dfrac{{(1 + r)^{{{yrs}}} - 1}}{{r}}\\).",
                 f"\\(A = {plain(M)}\\times {dec(1 + R_(rp))}\\times\\dfrac{{{dec(1 + R_(rp))}^{{{yrs}}} - 1}}{{{rp}}} \\approx {m2(v)}\\)."],
                "With deposits at the start of each period every deposit earns one extra period of interest compared with end-of-period deposits.",
                "Write the first and last terms of the series to see how many periods each deposit earns.",
                quicker="Start-of-period balance = end-of-period balance × \\((1 + r)\\).",
                common_errors=[err(rnd(fv_str(M, rp, yrs), 2), "interpretation", FIN, "Deposits are at the START of each year, so each earns one more year of interest.", step=1),
                               err(M * yrs, "conceptual", FIN, "That ignores interest.", step=1)],
                skill="Future value of deposits made at the start of each period.",
                params={"form": "fv", "M": M, "R": R, "m": 1, "N": yrs, "due": True},
            )
        T = pick(r, [10000, 20000, 25000, 50000])
        R, yrs = pick(r, MONTHLY), r.randint(3, 8)
        rp = dec(R_(R) / 1200)
        N = 12 * yrs
        v = f"{T}*{rp}/((1 + {rp})^{N} - 1)"
        return Generated(
            f"Mia wants {dollars(T, 0)} in {yrs} years. She deposits \\(M\\) dollars at the end of each month into an account earning {pct(R)} p.a. interest, compounded monthly. "
            "Find \\(M\\), to the nearest cent.",
            A_round(v, 2, "$"), 3, 2,
            [f"\\(r = {rp}\\), \\(n = {N}\\): the balance after the last deposit is \\(M\\dfrac{{(1 + r)^{{{N}}} - 1}}{{r}}\\).",
             f"\\(M\\dfrac{{{dec(1 + R_(rp))}^{{{N}}} - 1}}{{{rp}}} = {plain(T)}\\).",
             f"\\(M = \\dfrac{{{plain(T)}\\times {rp}}}{{{dec(1 + R_(rp))}^{{{N}}} - 1}} \\approx {m2(v)}\\)."],
            "Set the future value of the deposits equal to the target and solve for the deposit.",
            "Keep the bracket exact on the calculator; round only the final answer.",
            quicker=f"Without interest she would need {dollars(sp.Rational(T, N))} a month; interest makes the answer a little smaller.",
            common_errors=[err(rnd(sp.Rational(T, N), 2), "conceptual", FIN, "That ignores interest on the deposits.", step=1),
                           err(rnd(f"{T}*{dec(R_(R) / 100)}/((1 + {dec(R_(R) / 100)})^{N} - 1)", 2), "formula selection", FIN, "Use the monthly rate \\(r = \\frac{R}{12}\\).", step=1)],
            skill="Find the regular deposit needed to reach a target.",
            checkpoints=[],
            params={"form": "target", "T": T, "R": R, "N": N},
        )
    M = pick(r, [100, 150, 200, 300, 400, 500])
    R = pick(r, MONTHLY)
    yrs = r.randint(3, 10)
    rp = dec(R_(R) / 1200)
    rq = 1 + R_(rp)
    N = 12 * yrs
    T = pick(r, [5000, 10000, 15000, 20000, 30000])
    while M * N <= T // 2 or M * 6 > T:
        T = pick(r, [5000, 10000, 15000, 20000, 30000, 50000])
        M = pick(r, [100, 150, 200, 300, 400, 500])
    nn = first_n(lambda n_: M * (rq**n_ - 1) / R_(rp) > T, 5000)
    v3 = f"{M}*(1 + {rp})^2 + {M}*(1 + {rp}) + {M}"
    vb = fv_str(M, rp, N)
    exact = math.log(1 + T * float(R_(rp)) / M) / math.log(float(rq))
    text = multipart(
        f"Sam deposits {dollars(M, 0)} at the end of each month into an account earning {pct(R)} p.a. interest, compounded monthly.",
        [("a", "Find the balance immediately after the 3rd deposit, to the nearest cent.", 1),
         ("b", f"Find the balance immediately after the last deposit at the end of {yrs} years, to the nearest cent.", 2),
         ("c", f"How many deposits are needed for the balance to first exceed {dollars(T, 0)}?", 2)])
    steps = [f"(a) \\(r = {rp}\\). After 3 deposits: \\({M}(1 + r)^2 + {M}(1 + r) + {M} \\approx {m2(v3)}\\).",
             f"(b) After \\(n\\) deposits the balance is the GP sum \\({M}\\dfrac{{(1 + r)^n - 1}}{{r}}\\); with \\(n = {N}\\):",
             f"\\({M}\\times\\dfrac{{{dec(rq)}^{{{N}}} - 1}}{{{rp}}} \\approx {m2(vb)}\\).",
             f"(c) \\({M}\\dfrac{{{dec(rq)}^n - 1}}{{{rp}}} > {plain(T)}\\) gives \\({dec(rq)}^n > {L(1 + T * R_(rp) / M)}\\), so \\(n > {exact:.3f}\\).",
             f"So {nn} deposits are needed."]
    return Generated(
        text, A_parts(P("a", 1, A_round(v3, 2, "$")), P("b", 2, A_round(vb, 2, "$")), P("c", 2, A_num(nn))), 5, 3, steps,
        "The balance after \\(n\\) regular deposits is a geometric series, so the sum formula gives it and logarithms find \\(n\\).",
        "Develop the balance after 1, 2 and 3 deposits to show the pattern before using the sum formula.",
        quicker="(a) is a check on (b): substitute \\(n = 3\\) into your formula.",
        common_errors=[err(3 * M, "conceptual", FIN, "Each earlier deposit has earned interest.", step=1, part="a"),
                       err(M * N, "conceptual", FIN, "That ignores interest.", step=2, part="b"),
                       err(nn - 1, "careless error", "inequality direction", "Round up: the balance must exceed the target.", step=5, part="c")],
        skill="Build and use the balance of a regular-deposit account.",
        params={"form": "parts", "M": M, "R": R, "N": N, "T": T},
    )


# ======================================================================= 8E ===
def _repayment(P0, rp: str, N: int) -> str:
    return f"{P0}*{rp}*(1 + {rp})^{N}/((1 + {rp})^{N} - 1)"


def t_8E(r: Rng, d: int) -> Generated:
    if d == 1:
        P0 = pick(r, [5000, 8000, 12000, 20000, 25000, 30000])
        R = pick(r, MONTHLY)
        M = pick(r, [250, 300, 400, 500, 600, 750])
        rp = dec(R_(R) / 1200)
        v = f"{P0}*(1 + {rp}) - {M}"
        return Generated(
            f"A loan of {dollars(P0, 0)} is charged interest at {pct(R)} p.a., compounded monthly. Repayments of {dollars(M, 0)} are made at the end of each month. "
            "Find the amount owing immediately after the first repayment, to the nearest cent.",
            A_round(v, 2, "$"), 2, 1,
            [f"Monthly rate \\(r = \\dfrac{{{dec(R_(R) / 100)}}}{{12}} = {rp}\\).",
             f"\\(A_1 = P(1 + r) - M = {plain(P0)}\\times {dec(1 + R_(rp))} - {M} = {m2(v)}\\)."],
            "Each month interest is added to the balance first, then the repayment is subtracted.",
            "Write \\(A_1\\) in the form \\(P(1 + r) - M\\); later balances follow the same pattern.",
            quicker=f"Interest for the first month is {dollars(P0 * R_(rp))}; add it, then subtract the repayment.",
            common_errors=[err(P0 - M, "conceptual", FIN, "Interest is charged before the repayment.", step=2),
                           err(rnd(f"{P0}*(1 + {dec(R_(R) / 100)}) - {M}", 2), "formula selection", FIN, "Use the monthly rate \\(\\frac{R}{12}\\).", step=1),
                           err(rnd(f"({P0} - {M})*(1 + {rp})", 2), "conceptual", FIN, "Interest is added for the month before the end-of-month repayment.", step=2)],
            skill="Find a loan balance after one repayment.",
            params={"form": "A1", "P": P0, "R": R, "M": M},
        )
    P0 = pick(r, [10000, 15000, 20000, 30000, 40000, 250000, 400000])
    R = pick(r, MONTHLY)
    yrs = pick(r, [3, 4, 5]) if P0 < 100000 else pick(r, [20, 25, 30])
    rp = dec(R_(R) / 1200)
    N = 12 * yrs
    vM = _repayment(P0, rp, N)
    if d == 2:
        return Generated(
            f"A loan of {dollars(P0, 0)} is to be repaid in equal monthly instalments over {yrs} years. Interest is charged at {pct(R)} p.a., compounded monthly. "
            "Find the monthly repayment, to the nearest cent.",
            A_round(vM, 2, "$"), 3, 2,
            [f"\\(r = {rp}\\), \\(n = {N}\\). After \\(n\\) months: \\(A_n = P(1 + r)^n - M\\dfrac{{(1 + r)^n - 1}}{{r}}\\).",
             f"The loan is repaid when \\(A_{{{N}}} = 0\\): \\(M = \\dfrac{{Pr(1 + r)^{{{N}}}}}{{(1 + r)^{{{N}}} - 1}}\\).",
             f"\\(M = \\dfrac{{{plain(P0)}\\times {rp}\\times {dec(1 + R_(rp))}^{{{N}}}}}{{{dec(1 + R_(rp))}^{{{N}}} - 1}} \\approx {m2(vM)}\\)."],
            "The balance is the compounded loan minus the compounded repayments (a GP); setting it to zero gives the repayment.",
            "Derive \\(A_1, A_2, A_3\\) in HSC questions; the pattern justifies the general formula.",
            quicker=f"Without interest the repayment would be {dollars(sp.Rational(P0, N))}; the true repayment must be larger.",
            common_errors=[err(rnd(sp.Rational(P0, N), 2), "conceptual", FIN, "That ignores interest.", step=2),
                           err(rnd(f"{P0}*(1 + {rp})^{N}/{N}", 2), "conceptual", FIN,
                               "Interest stops accruing on the part already repaid, so you cannot spread the compounded loan evenly.", step=2),
                           err(rnd(_repayment(P0, dec(R_(R) / 100), N), 2), "formula selection", FIN, "Use the monthly rate.", step=1)],
            skill="Find the repayment on a reducing-balance loan.",
            params={"form": "M", "P": P0, "R": R, "N": N},
        )
    M_exact = val(vM)
    Mr_s = str(cents(vM))  # the repayment actually paid, e.g. '1462.78'
    Mr = sp.Rational(Mr_s)
    K_years = r.randint(1, yrs - 1)
    K = 12 * K_years
    interest = N * Mr - P0
    tol_c = float(abs(N * (Mr - M_exact))) + 0.01
    bal = f"{P0}*(1 + {rp})^{K} - {Mr_s}*((1 + {rp})^{K} - 1)/{rp}"
    bal_exactM = val(f"{P0}*(1 + {rp})^{K}") - M_exact * (val(f"(1 + {rp})^{K}") - 1) / R_(rp)
    tol_d = float(abs(val(bal) - bal_exactM)) + 0.01
    vA1 = f"{P0}*(1 + {rp}) - {Mr_s}"
    text = multipart(
        f"A loan of {dollars(P0, 0)} is to be repaid in equal monthly instalments of \\(M\\) dollars over {yrs} years. "
        f"Interest is charged at {pct(R)} p.a., compounded monthly, and the repayment is made at the end of each month.",
        [("a", "Find the monthly repayment \\(M\\), to the nearest cent.", 2),
         ("b", "Using your rounded value of \\(M\\), find the amount owing immediately after the first repayment, to the nearest cent.", 1),
         ("c", "Find the total interest paid over the life of the loan, to the nearest cent.", 1),
         ("d", f"Find the amount still owing after {K_years} year{'s' if K_years > 1 else ''}, to the nearest cent.", 2)])
    steps = [f"(a) \\(r = {rp}\\), \\(n = {N}\\): \\(M = \\dfrac{{Pr(1 + r)^n}}{{(1 + r)^n - 1}} \\approx {m2(vM)}\\).",
             f"(b) \\(A_1 = {plain(P0)}\\times {dec(1 + R_(rp))} - {Mr_s} = {m2(vA1)}\\).",
             f"(c) Total repaid \\(= {N}\\times {Mr_s} = {money(N * Mr)}\\); interest \\(= {money(N * Mr)} - {money(P0)} = {money(interest)}\\).",
             f"(d) \\(A_{{{K}}} = P(1 + r)^{{{K}}} - M\\dfrac{{(1 + r)^{{{K}}} - 1}}{{r}}\\) with \\(M = {Mr_s}\\).",
             f"\\(A_{{{K}}} \\approx {m2(bal)}\\)."]
    return Generated(
        text,
        A_parts(P("a", 2, A_round(vM, 2, "$")), P("b", 1, A_round(vA1, 2, "$")),
                P("c", 1, {"type": "num", "value": dec(interest), "tol": round(tol_c, 4), "units": "$"}),
                P("d", 2, {"type": "num", "value": str(cents(bal)), "tol": round(tol_d + 0.005, 4), "units": "$"})),
        6, 3, steps,
        "A reducing-balance loan: each month interest is added and the repayment subtracted; the balance is a compounded principal minus a GP of repayments.",
        "Use the rounded repayment in later parts (it is what is actually paid) and say so.",
        quicker="The amount owing after half the term is more than half the loan, because early repayments are mostly interest.",
        common_errors=[err(rnd(sp.Rational(P0, N), 2), "conceptual", FIN, "That ignores interest.", step=1, part="a"),
                       err(rnd(f"{P0} - {Mr_s}", 2), "conceptual", FIN, "Interest is added before the repayment.", step=2, part="b"),
                       err(N * Mr, "interpretation", FIN, "That is the total repaid; subtract the amount borrowed to get the interest.", step=3, part="c"),
                       err(P0 - K * Mr, "conceptual", FIN, "Interest is charged on the balance every month; use the balance formula.", step=4, part="d")],
        skill="Analyse a reducing-balance loan.",
        params={"form": "parts", "P": P0, "R": R, "N": N, "K": K},
    )


# ======================================================================= 8F ===
def t_8F(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            P0 = pick(r, [100000, 200000, 250000, 400000, 500000])
            R = pick(r, MONTHLY)
            W = pick(r, [1500, 2000, 2500, 3000, 4000])
            rp = dec(R_(R) / 1200)
            v = f"{P0}*(1 + {rp})^2 - {W}*(1 + {rp}) - {W}"
            return Generated(
                f"A retirement fund of {dollars(P0, 0)} earns {pct(R)} p.a. interest, compounded monthly. At the end of each month, after interest is added, "
                f"a pension of {dollars(W, 0)} is withdrawn. Find the balance immediately after the second withdrawal, to the nearest cent.",
                A_round(v, 2, "$"), 2, 1,
                [f"\\(r = {rp}\\). After one month: \\(B_1 = {plain(P0)}(1 + r) - {W}\\).",
                 f"\\(B_2 = B_1(1 + r) - {W} = {plain(P0)}(1 + r)^2 - {W}(1 + r) - {W} \\approx {m2(v)}\\)."],
                "An annuity fund is a loan in reverse: interest is added, then the withdrawal is taken.",
                "Write \\(B_1\\) and \\(B_2\\) separately — the pattern gives the general formula.",
                quicker=f"Monthly interest on {dollars(P0, 0)} is {dollars(P0 * R_(rp))}; if the pension is larger, the fund shrinks.",
                common_errors=[err(P0 - 2 * W, "conceptual", FIN, "Interest is added each month.", step=1),
                               err(rnd(f"{P0}*(1 + {rp})^2 - 2*{W}", 2), "conceptual", FIN, "The first withdrawal also stops that money earning interest in month 2.", step=2)],
                skill="Track an annuity balance over two periods.",
                params={"form": "B2", "P": P0, "R": R, "W": W},
            )
        W = pick(r, [10000, 20000, 25000, 30000, 40000])
        R = pick(r, ANNUAL)
        yrs = pick(r, [10, 15, 20, 25])
        rp = dec(R_(R) / 100)
        v = f"{W}*(1 - (1 + {rp})^(-{yrs}))/{rp}"
        return Generated(
            f"How much must be in a fund earning {pct(R)} p.a., compounded annually, to pay {dollars(W, 0)} at the end of each year for {yrs} years, "
            "leaving nothing at the end? Answer to the nearest dollar.",
            A_round(v, 0, "$"), 2, 1,
            [f"Each payment is worth its present value \\(\\dfrac{{{plain(W)}}}{{(1 + r)^k}}\\) now, with \\(r = {rp}\\).",
             f"Sum of the GP: \\(N = {plain(W)}\\times\\dfrac{{1 - (1 + r)^{{-{yrs}}}}}{{r}} \\approx {m2(v, 0)}\\)."],
            "The fund needed now is the sum of the present values of all the payments (a geometric series).",
            "State what each term of the series represents.",
            quicker=f"The fund must be less than {dollars(W * yrs, 0)} because it earns interest while paying out.",
            common_errors=[err(W * yrs, "conceptual", FIN, "That ignores the interest the fund earns.", step=1),
                           err(rnd(fv_str(W, rp, yrs), 0), "formula selection", FIN, "That is a future value; the fund is needed NOW, so discount each payment.", step=2)],
            skill="Find the present value of an annuity.",
            params={"form": "pv", "W": W, "R": R, "n": yrs},
        )
    if d == 2:
        P0 = pick(r, [200000, 300000, 400000, 500000, 600000])
        R = pick(r, MONTHLY)
        rp = dec(R_(R) / 1200)
        if r.random() < 0.5:
            yrs = pick(r, [15, 20, 25])
            N = 12 * yrs
            v = _repayment(P0, rp, N)
            return Generated(
                f"A retiree invests {dollars(P0, 0)} in an annuity earning {pct(R)} p.a., compounded monthly. She withdraws an equal amount \\(W\\) at the end of each month "
                f"so that the fund lasts exactly {yrs} years. Find \\(W\\), to the nearest cent.",
                A_round(v, 2, "$"), 3, 2,
                [f"\\(r = {rp}\\). After \\(n\\) withdrawals: \\(B_n = P(1 + r)^n - W\\dfrac{{(1 + r)^n - 1}}{{r}}\\).",
                 f"\\(B_{{{N}}} = 0\\) gives \\(W = \\dfrac{{Pr(1 + r)^{{{N}}}}}{{(1 + r)^{{{N}}} - 1}}\\).",
                 f"\\(W \\approx {m2(v)}\\)."],
                "An annuity is the reverse of a loan: the fund is the principal, the withdrawals are the repayments.",
                "Set the final balance to zero and solve for \\(W\\).",
                quicker=f"Without interest she could take {dollars(sp.Rational(P0, N))} a month; interest lets her take more.",
                common_errors=[err(rnd(sp.Rational(P0, N), 2), "conceptual", FIN, "That ignores interest on the remaining fund.", step=2),
                               err(rnd(_repayment(P0, dec(R_(R) / 100), N), 2), "formula selection", FIN, "Use the monthly rate.", step=1)],
                skill="Find the pension an annuity fund can pay.",
                params={"form": "W", "P": P0, "R": R, "N": N},
            )
        interest1 = P0 * R_(rp)
        W = int(math.ceil(float(interest1) * pick(r, [1.5, 2, 2.5, 3]) / 100) * 100)
        rq = 1 + R_(rp)
        count = 0
        bal = sp.Rational(P0)
        while bal * rq >= W and count < 5000:
            bal = bal * rq - W
            count += 1
        exact = -math.log(1 - float(P0 * R_(rp)) / W) / math.log(float(rq))
        if abs(exact - round(exact)) < 1e-6:
            return t_8F(r, d)  # an exact whole number of withdrawals is ambiguous; draw again
        return Generated(
            f"A fund of {dollars(P0, 0)} earns {pct(R)} p.a., compounded monthly. At the end of each month, after interest, {dollars(W, 0)} is withdrawn. "
            "How many full withdrawals of this amount can be made?",
            A_num(count), 3, 2,
            [f"\\(r = {rp}\\). The fund runs out when \\(P(1 + r)^n - W\\dfrac{{(1 + r)^n - 1}}{{r}} = 0\\).",
             f"\\((1 + r)^n(Pr - W) = -W\\), so \\((1 + r)^n = \\dfrac{{W}}{{W - Pr}} = {L(sp.Rational(W) / (W - P0 * R_(rp)))}\\).",
             f"\\(n = \\dfrac{{\\ln {L(sp.Rational(W) / (W - P0 * R_(rp)))}}}{{\\ln {dec(rq)}}} \\approx {exact:.3f}\\): {count} full withdrawals (the last part-withdrawal is smaller)."],
            "When the withdrawal exceeds the monthly interest, the fund shrinks; the time it lasts is found with logarithms.",
            "Round DOWN for full withdrawals and explain why.",
            quicker=f"The monthly interest at the start is {dollars(interest1)}; the withdrawal is bigger, so the fund must run out.",
            common_errors=[err(count + 1, "careless error", "rounding", "Round down: the last withdrawal cannot be made in full.", step=3),
                           err(P0 // W, "conceptual", FIN, "That ignores the interest the fund keeps earning.", step=1)],
            skill="Find how long an annuity lasts.",
            params={"form": "count", "P": P0, "R": R, "W": W},
        )
    while True:
        C = pick(r, [5000, 8000, 10000, 12000, 15000])
        R = pick(r, ANNUAL)
        N1 = pick(r, [20, 25, 30, 35, 40])
        N2 = pick(r, [15, 20, 25])
        rp = dec(R_(R) / 100)
        rq = 1 + R_(rp)
        F = fv_str(C, rp, N1)
        Fx, Fr = val(F), sp.Rational(str(cents(F, 0)))
        Wx = Fx * R_(rp) * rq**N2 / (rq**N2 - 1)
        Wr = Fr * R_(rp) * rq**N2 / (rq**N2 - 1)
        if cents(str(Wx), 0) != cents(str(Wr), 0):
            continue
        W2 = int(math.ceil(float(Wx) * pick(r, [1.2, 1.3, 1.5]) / 1000) * 1000)

        def lasts(fund):
            cnt, b = 0, fund
            while b * rq >= W2 and cnt < 500:
                b = b * rq - W2
                cnt += 1
            return cnt
        cnt = lasts(Fx)
        if cnt != lasts(Fr):
            continue
        break
    vW = f"({F})*{rp}*(1 + {rp})^{N2}/((1 + {rp})^{N2} - 1)"
    exact = -math.log(1 - float(Fx * R_(rp)) / W2) / math.log(float(rq))
    text = multipart(
        f"Lee contributes {dollars(C, 0)} at the end of each year to a superannuation fund earning {pct(R)} p.a., compounded annually, for {N1} years. "
        "At retirement the fund is converted to an annuity that keeps earning the same rate and pays a pension at the end of each year.",
        [("a", f"Find the value of the fund at retirement, to the nearest dollar.", 2),
         ("b", f"Find the annual pension that would make the fund last exactly {N2} years, to the nearest dollar.", 2),
         ("c", f"If instead Lee withdraws {dollars(W2, 0)} at the end of each year, for how many full years can this pension be paid?", 2)])
    steps = [f"(a) The contributions form a GP: \\(F = {plain(C)}\\dfrac{{(1 + r)^{{{N1}}} - 1}}{{r}}\\) with \\(r = {rp}\\).",
             f"\\(F \\approx {m2(F, 0)}\\).",
             f"(b) \\(F(1 + r)^{{{N2}}} - W\\dfrac{{(1 + r)^{{{N2}}} - 1}}{{r}} = 0\\), so \\(W = \\dfrac{{Fr(1 + r)^{{{N2}}}}}{{(1 + r)^{{{N2}}} - 1}} \\approx {m2(vW, 0)}\\).",
             f"(c) \\((1 + r)^n = \\dfrac{{W}}{{W - Fr}}\\), so \\(n = \\dfrac{{\\ln\\frac{{W}}{{W - Fr}}}}{{\\ln(1 + r)}} \\approx {exact:.3f}\\).",
             f"So {cnt} full years."]
    return Generated(
        text, A_parts(P("a", 2, A_round(F, 0, "$")), P("b", 2, A_round(vW, 0, "$")), P("c", 2, A_num(cnt))), 6, 3, steps,
        "Superannuation has two phases: an accumulation phase (a future value of regular contributions) and a pension phase (an annuity that runs the fund down).",
        "Keep the unrounded fund value in the calculator for (b) and (c).",
        quicker="A pension larger than the annual interest \\(Fr\\) must eventually exhaust the fund; one smaller would last forever.",
        common_errors=[err(C * N1, "conceptual", FIN, "That ignores interest on the contributions.", step=1, part="a"),
                       err(rnd(f"({F})/{N2}", 0), "conceptual", FIN, "The fund keeps earning interest while it pays the pension.", step=3, part="b"),
                       err(cnt + 1, "careless error", "rounding", "Round down: the last pension payment cannot be made in full.", step=4, part="c")],
        skill="Model superannuation: accumulation then pension.",
        params={"form": "super", "C": C, "R": R, "N1": N1, "N2": N2, "W2": W2},
    )
