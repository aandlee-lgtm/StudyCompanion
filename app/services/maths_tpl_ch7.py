"""Chapter 7 — Motion and rates (owner: maths). Time is t; all calculus from chapters 2–6 may be used."""
from __future__ import annotations

import math

import sympy as sp

from app.services.maths_tpl_base import (
    A_expr, A_iv, A_mcq, A_num, A_parts, A_round, A_set, A_units, Generated, L, P, Rng, S, co, cp, err, mcq_options, multipart,
    nonzero, pick, pl, pn, region, rnd, t,
)

MOT = "rates and motion"
MOD = "modelling"
E = sp.E


def tl(e) -> str:
    return pl(e, t)


def _particle(r: Rng):
    """x(t) with v(t) = 3(t - p)(t - q), 0 < p < q integers, p + q even."""
    while True:
        p, q = sorted(r.sample(range(1, 7), 2))
        if (p + q) % 2 == 0:
            break
    c = r.randint(-8, 8)
    xt = t**3 - sp.Rational(3 * (p + q), 2) * t**2 + 3 * p * q * t + c
    return sp.expand(xt), p, q, c


STEM = "A particle moves in a straight line. Its displacement \\(x\\) metres from a fixed point \\(O\\) after \\(t\\) seconds is given by"


# ======================================================================= 7A ===
def t_7A(r: Rng, d: int) -> Generated:
    if d == 1:
        if r.random() < 0.5:
            a, b, c = nonzero(r, -4, 5), nonzero(r, -9, 9), r.randint(-10, 10)
            xt = a * t**2 + b * t + c
            m = r.randint(1, 6)
            v = 2 * a * m + b
            return Generated(
                f"{STEM} \\(x = {tl(xt)}\\). Find the velocity of the particle when \\(t = {m}\\).",
                A_units(v, "m/s"), 1, 1,
                [f"\\(v = \\dfrac{{dx}}{{dt}} = {tl(sp.diff(xt, t))}\\), so at \\(t = {m}\\), \\(v = {v}\\) m/s."],
                "Velocity is the rate of change of displacement: \\(v = \\frac{dx}{dt}\\).",
                "Differentiate first, then substitute; include units.",
                quicker="A negative velocity means the particle is moving in the negative direction at that instant.",
                common_errors=[err(xt.subs(t, m), "conceptual", MOT, "That is the displacement; velocity is \\(\\frac{dx}{dt}\\).", step=1),
                               err(2 * a, "conceptual", MOT, "That is the acceleration.", step=1)],
                skill="Find velocity from displacement.",
                params={"form": "v", "x": str(xt), "m": m},
            )
        xt, p, q, c = _particle(r)
        m = r.randint(0, 6)
        acc = sp.diff(xt, t, 2).subs(t, m)
        return Generated(
            f"{STEM} \\(x = {tl(xt)}\\). Find the acceleration of the particle when \\(t = {m}\\).",
            A_units(acc, "m/s^2"), 2, 1,
            [f"\\(v = {tl(sp.diff(xt, t))}\\).", f"\\(a = \\dfrac{{dv}}{{dt}} = {tl(sp.diff(xt, t, 2))}\\), so at \\(t = {m}\\), \\(a = {acc}\\) m/s²."],
            "Acceleration is the rate of change of velocity: \\(a = \\frac{dv}{dt} = \\frac{d^2x}{dt^2}\\).",
            "Show both derivatives; include units of m/s².",
            quicker="For a cubic displacement the acceleration is linear in \\(t\\).",
            common_errors=[err(sp.diff(xt, t).subs(t, m), "conceptual", MOT, "That is the velocity; differentiate again for acceleration.", step=2)],
            skill="Find acceleration from displacement.",
            params={"form": "a", "x": str(xt), "m": m},
        )
    xt, p, q, c = _particle(r)
    vt = sp.diff(xt, t)
    if d == 2:
        acc = sp.diff(vt, t).subs(t, p)
        text = multipart(f"{STEM} \\(x = {tl(xt)}\\).",
                         [("a", "Find the times when the particle is at rest.", 2), ("b", "Find the acceleration at the first of these times.", 1)])
        return Generated(
            text, A_parts(P("a", 2, A_set([p, q])), P("b", 1, A_units(acc, "m/s^2"))), 3, 2,
            [f"(a) \\(v = {tl(vt)} = 3(t - {p})(t - {q})\\).", f"\\(v = 0\\) when \\(t = {p}\\) or \\(t = {q}\\) seconds.",
             f"(b) \\(a = {tl(sp.diff(vt, t))}\\); at \\(t = {p}\\), \\(a = {acc}\\) m/s²."],
            "A particle is at rest when its velocity is zero.",
            "Factorise \\(v\\); state both times.",
            quicker="Take out the common factor 3 before factorising.",
            common_errors=[err(S(-p, -q), "careless error", "sign error", "Sign error when solving \\(v = 0\\).", step=2, part="a"),
                           err(vt.subs(t, p), "conceptual", MOT, "Acceleration is \\(\\frac{dv}{dt}\\), not \\(v\\).", step=3, part="b")],
            skill="Find when a particle is at rest and its acceleration then.",
            checkpoints=[cp(vt, "the velocity", step=1, part="a", vars_=("t",))],
            params={"form": "rest", "x": str(xt)},
        )
    T = q + r.randint(1, 2)
    x0, xp, xq, xT = xt.subs(t, 0), xt.subs(t, p), xt.subs(t, q), xt.subs(t, T)
    dist = abs(xp - x0) + abs(xq - xp) + abs(xT - xq)
    ac_m = r.randint(0, 6)
    text = multipart(f"{STEM} \\(x = {tl(xt)}\\).",
                     [("a", "Find the initial velocity.", 1), ("b", "Find the times when the particle is at rest.", 2),
                      ("c", f"Find the total distance travelled in the first {T} seconds.", 2), ("d", f"Find the acceleration when \\(t = {ac_m}\\).", 1)])
    steps = [f"(a) \\(v = {tl(vt)}\\), so at \\(t = 0\\), \\(v = {vt.subs(t, 0)}\\) m/s.",
             f"(b) \\(v = 3(t - {p})(t - {q}) = 0\\) when \\(t = {p}\\) or \\(t = {q}\\).",
             f"(c) The particle changes direction at \\(t = {p}\\) and \\(t = {q}\\): \\(x(0) = {x0}\\), \\(x({p}) = {L(xp)}\\), \\(x({q}) = {L(xq)}\\), \\(x({T}) = {L(xT)}\\).",
             f"Distance \\(= |{L(xp)} - {pn(x0)}| + |{L(xq)} - {pn(xp)}| + |{L(xT)} - {pn(xq)}| = {L(dist)}\\) m.",
             f"(d) \\(a = {tl(sp.diff(vt, t))}\\), so at \\(t = {ac_m}\\), \\(a = {sp.diff(vt, t).subs(t, ac_m)}\\) m/s²."]
    return Generated(
        text,
        A_parts(P("a", 1, A_units(vt.subs(t, 0), "m/s")), P("b", 2, A_set([p, q])), P("c", 2, A_units(dist, "m")),
                P("d", 1, A_units(sp.diff(vt, t).subs(t, ac_m), "m/s^2"))), 6, 3, steps,
        "Distance travelled is not displacement: the particle turns where \\(v = 0\\), so add the lengths of each leg of the journey.",
        "Tabulate the positions at \\(t = 0\\), at each turning time and at the end, and draw them on a number line.",
        quicker="A number-line diagram of the motion makes the distance obvious and catches sign slips.",
        common_errors=[err(abs(xT - x0), "conceptual", MOT, "That is the change in displacement; the particle turns around, so add each leg.", step=4, part="c"),
                       err(xT, "interpretation", MOT, "That is the final position, not the distance travelled.", step=4, part="c"),
                       err(x0, "conceptual", MOT, "That is the initial displacement; velocity is \\(\\frac{dx}{dt}\\).", step=1, part="a"),
                       err(S(-p, -q), "careless error", "sign error", "Sign error when solving \\(v = 0\\).", step=2, part="b")],
        skill="Analyse straight-line motion: velocity, rest, distance, acceleration.",
        checkpoints=[cp(vt, "the velocity", step=1, part="b", vars_=("t",)), cp(vt, "the velocity", step=1, part="c", vars_=("t",))],
        params={"form": "parts", "x": str(xt), "T": T, "m": ac_m},
    )


# ======================================================================= 7B ===
def t_7B(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = r.randint(1, 4), nonzero(r, -8, 8), r.randint(-6, 6)
        vt = 3 * a * t**2 + 2 * b * t
        xt = a * t**3 + b * t**2 + c
        return Generated(
            f"A particle moves in a straight line with velocity \\(v = {tl(vt)}\\) m/s. Initially it is at \\(x = {c}\\). Find \\(x\\) as a function of \\(t\\).",
            A_expr(xt, ("t",)), 2, 1,
            [f"\\(x = \\displaystyle\\int v\\,dt = {tl(a * t**3 + b * t**2)} + C\\).", f"At \\(t = 0\\), \\(x = {c}\\), so \\(C = {c}\\): \\(x = {tl(xt)}\\)."],
            "Displacement is a primitive of velocity; the initial position fixes the constant.",
            "Write \\(+C\\) and then use the initial condition explicitly.",
            quicker="Check: differentiate your \\(x\\) to get \\(v\\) back, and substitute \\(t = 0\\).",
            common_errors=[err(a * t**3 + b * t**2, "incomplete reasoning", "constant of integration", f"Use the initial position to find \\(C = {c}\\).", step=2)
                           if c else err(6 * a * t + 2 * b, "conceptual", MOT, "That is the acceleration; integrate to get displacement.", step=1),
                           err(6 * a * t + 2 * b, "conceptual", MOT, "Differentiating gives acceleration; integrate to get displacement.", step=1)],
            skill="Find displacement from velocity and an initial position.",
            checkpoints=[cp(a * t**3 + b * t**2, "the primitive of v", step=1, vars_=("t",))],
            params={"form": "x", "v": str(vt), "x0": c},
        )
    if d == 2:
        if r.random() < 0.6:
            k, b = r.randint(1, 4), r.randint(-6, 6)
            v0, x0 = r.randint(-5, 8), r.randint(-5, 5)
            T = r.randint(1, 4)
            vt = 3 * k * t**2 + b * t + v0
            xt = k * t**3 + sp.Rational(b, 2) * t**2 + v0 * t + x0
            at = sp.diff(vt, t)
            val = xt.subs(t, T)
            return Generated(
                f"A particle has acceleration \\(a = {tl(at)}\\) m/s². Initially its velocity is \\({v0}\\) m/s and its displacement is \\({x0}\\) m. Find its displacement after {T} seconds.",
                A_units(val, "m"), 3, 2,
                [f"\\(v = \\displaystyle\\int a\\,dt = {tl(3 * k * t**2 + b * t)} + C_1\\); \\(v(0) = {v0}\\) gives \\(C_1 = {v0}\\).",
                 f"\\(x = \\displaystyle\\int v\\,dt = {tl(xt - x0)} + C_2\\); \\(x(0) = {x0}\\) gives \\(C_2 = {x0}\\).",
                 f"\\(x({T}) = {L(val)}\\) m."],
                "Integrate twice, using the initial velocity and the initial displacement for the two constants.",
                "Find each constant immediately after each integration.",
                quicker="Check the units: integrating m/s² over time gives m/s, then m.",
                common_errors=[err(val - v0 * T, "incomplete reasoning", "constant of integration", "Include the initial velocity: it adds \\(v_0 t\\) to the displacement.", step=1)
                               if v0 else err(val - x0, "incomplete reasoning", "constant of integration", "Include the initial displacement.", step=2),
                               err(val - x0, "incomplete reasoning", "constant of integration", "Include the initial displacement.", step=2)],
                skill="Integrate acceleration twice with initial conditions.",
                checkpoints=[cp(vt, "the velocity", step=1, vars_=("t",))],
                params={"form": "acc", "a": str(at), "v0": v0, "x0": x0, "T": T},
            )
        A, k = pick(r, [2, 4, 6, 10]), pick(r, [1, 2])
        vt = A * sp.exp(-k * t)
        T = pick(r, [1, 2, 3])
        val = sp.Rational(A, k) * (1 - sp.exp(-k * T))
        return Generated(
            f"A particle starts at the origin and moves with velocity \\(v = {A}e^{{{L(-k * t)}}}\\) m/s. Find its exact displacement after {T} seconds.",
            A_units(val, "m"), 2, 2,
            [f"\\(x = \\displaystyle\\int_0^{{{T}}} {A}e^{{{L(-k * t)}}}\\,dt = \\Big[{L(-sp.Rational(A, k) * sp.exp(-k * t))}\\Big]_0^{{{T}}}\\).",
             f"\\(= {L(val)}\\) m."],
            "Displacement from the origin is the definite integral of velocity from \\(0\\) to \\(t\\).",
            "Keep the answer exact with \\(e\\).",
            quicker=f"As \\(t \\to \\infty\\) the particle approaches \\(x = {L(sp.Rational(A, k))}\\): your answer must be below that.",
            common_errors=[err(-sp.Rational(A, k) * sp.exp(-k * T), "incomplete reasoning", "limits of integration", "Subtract the value at \\(t = 0\\).", step=2),
                           err(A * k * (1 - sp.exp(-k * T)), "conceptual", "chain rule", "Integrating divides by the coefficient of \\(t\\).", step=1)],
            skill="Find displacement from an exponential velocity.",
            params={"form": "expv", "A": A, "k": k, "T": T},
        )
    while True:
        p, q = sorted(r.sample(range(1, 7), 2))
        if q - p >= 2:
            break
    kf = pick(r, [1, 2, 3])
    vt = kf * (t - p) * (t - q)
    xt = sp.integrate(sp.expand(vt), t)
    T = q + r.randint(1, 3)
    dist = abs(xt.subs(t, p)) + abs(xt.subs(t, q) - xt.subs(t, p)) + abs(xt.subs(t, T) - xt.subs(t, q))
    text = multipart(f"A particle starts at the origin and moves in a straight line with velocity \\(v = {tl(sp.expand(vt))}\\) m/s.",
                     [("a", "Find the displacement \\(x\\) as a function of \\(t\\).", 2), ("b", "Find the times when the particle is at rest.", 1),
                      ("c", f"Find the total distance travelled in the first {T} seconds.", 2)])
    steps = [f"(a) \\(x = {tl(xt)} + C\\), and \\(x(0) = 0\\) gives \\(C = 0\\).",
             f"(b) \\(v = {co(kf, '')}(t - {p})(t - {q}) = 0\\) when \\(t = {p}\\) or \\(t = {q}\\).",
             f"(c) Positions: \\(x({p}) = {L(xt.subs(t, p))}\\), \\(x({q}) = {L(xt.subs(t, q))}\\), \\(x({T}) = {L(xt.subs(t, T))}\\).",
             f"Distance \\(= {L(abs(xt.subs(t, p)))} + {L(abs(xt.subs(t, q) - xt.subs(t, p)))} + {L(abs(xt.subs(t, T) - xt.subs(t, q)))} = {L(dist)}\\) m."]
    return Generated(
        text, A_parts(P("a", 2, A_expr(xt, ("t",))), P("b", 1, A_set([p, q])), P("c", 2, A_units(dist, "m"))), 5, 3, steps,
        "Integrate velocity for displacement; distance needs the motion split at every change of direction.",
        "Find when \\(v = 0\\) before computing a distance — that is where the particle turns.",
        quicker="Distance \\(= \\int_0^T |v|\\,dt\\): the same as adding the legs.",
        common_errors=[err(sp.integrate(vt, (t, 0, T)), "conceptual", MOT, "That is the displacement; the particle changes direction, so add the legs.", step=4, part="c"),
                       err(sp.diff(vt, t), "conceptual", MOT, "Integrate velocity for displacement.", step=1, part="a")],
        skill="Find displacement and distance from velocity.",
        checkpoints=[cp(xt, "the displacement", step=1, part="c", vars_=("t",))],
        params={"form": "parts", "k": kf, "p": p, "q": q, "T": T},
    )


# ======================================================================= 7C ===
def t_7C(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b, c = r.randint(1, 6), r.randint(5, 40), r.randint(100, 500)
        m = r.randint(2, 10)
        V = a * t**2 + b * t + c
        rate = 2 * a * m + b
        return Generated(
            f"Water is poured into a tank so that the volume after \\(t\\) minutes is \\(V = {tl(V)}\\) litres. Find the rate at which the volume is increasing when \\(t = {m}\\).",
            A_units(rate, "L/min"), 1, 1,
            [f"\\(\\dfrac{{dV}}{{dt}} = {tl(sp.diff(V, t))}\\), so at \\(t = {m}\\) the rate is \\({rate}\\) L/min."],
            "A rate of change is a derivative with respect to time.",
            "Differentiate, substitute, and give units (litres per minute).",
            quicker="The rate is the gradient of the graph of \\(V\\) against \\(t\\).",
            common_errors=[err(V.subs(t, m), "conceptual", MOD, "That is the volume; the rate is \\(\\frac{dV}{dt}\\).", step=1),
                           err(sp.Rational(V.subs(t, m) - c, m), "conceptual", MOD, "That is the average rate since \\(t = 0\\); the instantaneous rate is the derivative.", step=1)],
            skill="Find an instantaneous rate of change.",
            params={"form": "rate", "V": str(V), "m": m},
        )
    if d == 2:
        A, T = pick(r, [2, 3, 4, 5]), pick(r, [10, 20, 30, 40])
        m = pick(r, [T // 5, T // 4, T // 2])
        V = A * (T - t) ** 2
        rate = 2 * A * (T - m)
        text = multipart(f"A tank drains so that the volume of water after \\(t\\) minutes is \\(V = {A}({T} - t)^2\\) litres, for \\(0 \\le t \\le {T}\\).",
                         [("a", f"At what rate is water leaving the tank when \\(t = {m}\\)?", 1), ("b", "How much water was in the tank initially?", 1),
                          ("c", "At what time is the water leaving at half its initial rate?", 1)])
        return Generated(
            text, A_parts(P("a", 1, A_units(rate, "L/min")), P("b", 1, A_units(A * T * T, "L")), P("c", 1, A_units(sp.Rational(T, 2), "min"))), 3, 2,
            [f"(a) \\(\\dfrac{{dV}}{{dt}} = -{2 * A}({T} - t)\\); at \\(t = {m}\\) it is \\({-rate}\\), so water leaves at \\({rate}\\) L/min.",
             f"(b) \\(V(0) = {A}\\times {T}^2 = {A * T * T}\\) L.",
             f"(c) The initial rate is \\({2 * A * T}\\) L/min; \\({2 * A}({T} - t) = {A * T}\\) gives \\(t = {L(sp.Rational(T, 2))}\\) minutes."],
            "A negative \\(\\frac{dV}{dt}\\) means the volume is decreasing; 'the rate at which water leaves' is its magnitude.",
            "Interpret the sign of the derivative in words.",
            quicker="\\(\\frac{dV}{dt}\\) is linear in \\(t\\), so half the initial rate occurs halfway through the draining time.",
            common_errors=[err(-rate, "interpretation", "sign error", "The question asks for the rate of leaving, a positive quantity.", step=1, part="a"),
                           err(V.subs(t, m), "conceptual", MOD, "That is the volume; the rate is the derivative.", step=1, part="a"),
                           err(sp.Rational(T, 4), "arithmetic", MOD, "Solve \\(2A(T - t) = AT\\).", step=3, part="c")],
            skill="Interpret the derivative of a draining model.",
            params={"form": "drain", "A": A, "T": T, "m": m},
        )
    a = pick(r, [3, 6, 9, 12])
    b = pick(r, [1, 2, 3])
    Tm = 2 * a // (3 * b) if (2 * a) % (3 * b) == 0 else None
    while Tm is None:
        a, b = pick(r, [3, 6, 9, 12]), pick(r, [1, 2, 3])
        Tm = 2 * a // (3 * b) if (2 * a) % (3 * b) == 0 else None
    P0 = pick(r, [200, 500, 1000, 2000])
    Pt = P0 + a * t**2 - b * t**3
    end = sp.Rational(2 * a, 3 * b)
    fastest = sp.Rational(a, 3 * b)
    m = r.randint(1, max(1, int(end) - 1))
    rate_m = sp.diff(Pt, t).subs(t, m)
    text = multipart(f"The population of a colony of insects \\(t\\) weeks after observation began is modelled by \\(P = {tl(Pt)}\\), for \\(t \\ge 0\\).",
                     [("a", f"Find the rate of change of the population when \\(t = {m}\\).", 1),
                      ("b", "For what values of \\(t\\) is the population increasing?", 2),
                      ("c", "When is the population increasing most rapidly?", 2)])
    steps = [f"(a) \\(\\dfrac{{dP}}{{dt}} = {tl(sp.diff(Pt, t))}\\); at \\(t = {m}\\) this is \\({rate_m}\\) insects per week.",
             f"(b) \\(\\dfrac{{dP}}{{dt}} = {co(3 * b, '')}t\\left({L(end)} - t\\right) > 0\\) for \\(0 < t < {L(end)}\\).",
             f"(c) The growth rate \\(\\dfrac{{dP}}{{dt}}\\) is greatest where \\(\\dfrac{{d^2P}}{{dt^2}} = {tl(sp.diff(Pt, t, 2))} = 0\\), i.e. \\(t = {L(fastest)}\\) weeks.",
             f"\\(\\dfrac{{d^3P}}{{dt^3}} = {-6 * b} < 0\\), so this is a maximum of the growth rate."]
    return Generated(
        text, A_parts(P("a", 1, A_num(rate_m)), P("b", 2, A_iv([(0, end, False, False)], var="t", ends="ignore")), P("c", 2, A_num(fastest))), 5, 3, steps,
        "Increasing means \\(\\frac{dP}{dt} > 0\\); 'increasing most rapidly' means the rate \\(\\frac{dP}{dt}\\) is at a maximum, where \\(\\frac{d^2P}{dt^2} = 0\\).",
        "Distinguish the population, its rate of change, and the rate's rate of change — label each derivative.",
        quicker="The fastest growth is at the point of inflection of the population graph.",
        common_errors=[err(end, "interpretation", MOD, "That is when growth stops; the fastest growth is where \\(P'' = 0\\).", step=3, part="c"),
                       err(region([(end, None, False, False)], "t"), "interpretation", "inequality direction", "That is where the population is decreasing.", step=2, part="b"),
                       err(Pt.subs(t, m), "conceptual", MOD, "That is the population; the rate is the derivative.", step=1, part="a")],
        skill="Interpret first and second derivatives in a population model.",
        checkpoints=[cp(sp.diff(Pt, t), "the rate dP/dt", step=1, part="b", vars_=("t",))],
        params={"form": "pop", "P": str(Pt), "m": m},
    )


# ======================================================================= 7D ===
def t_7D(r: Rng, d: int) -> Generated:
    if d == 1:
        a, b = r.randint(2, 20), r.randint(1, 6)
        T = r.randint(3, 15)
        Rt = a + b * t
        vol = a * T + sp.Rational(b * T * T, 2)
        return Generated(
            f"Water flows into an empty tank at a rate of \\(R = {tl(Rt)}\\) litres per minute. How much water is in the tank after {T} minutes?",
            A_units(vol, "L"), 2, 1,
            [f"\\(V = \\displaystyle\\int_0^{{{T}}} ({tl(Rt)})\\,dt = \\Big[{tl(a * t + sp.Rational(b, 2) * t**2)}\\Big]_0^{{{T}}}\\).", f"\\(= {L(vol)}\\) litres."],
            "The amount that accumulates is the integral of the rate.",
            "Write the integral with limits \\(0\\) and \\(T\\); the tank starts empty so no constant is needed.",
            quicker="Area under a straight-line rate graph is a trapezium: width × average height.",
            common_errors=[err(Rt.subs(t, T), "conceptual", MOD, "That is the rate at that moment; the volume is the integral of the rate.", step=1),
                           err(Rt.subs(t, T) * T, "conceptual", MOD, "The rate changes over time: integrate, don't multiply the final rate by the time.", step=1)],
            skill="Find an accumulated amount from a rate.",
            params={"form": "fill", "R": str(Rt), "T": T, "V0": 0},
        )
    if d == 2:
        c, kv = pick(r, [20, 30, 40, 60, 80]), pick(r, [2, 4, 5])
        V0 = pick(r, [0, 50, 100, 200])
        Ts = sp.Rational(c, kv)
        vol = V0 + c * Ts - sp.Rational(kv, 2) * Ts**2
        text = multipart(f"Oil flows into a container at \\(R = {c} - {kv}t\\) litres per minute until the flow stops. Initially the container holds {V0} litres.",
                         [("a", "When does the flow stop?", 1), ("b", "How much oil is in the container when the flow stops?", 2)])
        return Generated(
            text, A_parts(P("a", 1, A_units(Ts, "min")), P("b", 2, A_units(vol, "L"))), 3, 2,
            [f"(a) \\({c} - {kv}t = 0\\) when \\(t = {L(Ts)}\\) minutes.",
             f"(b) \\(V = {V0} + \\displaystyle\\int_0^{{{L(Ts)}}} ({c} - {kv}t)\\,dt = {V0} + \\Big[{c}t - {co(sp.Rational(kv, 2), 't^2')}\\Big]_0^{{{L(Ts)}}}\\).",
             f"\\(= {L(vol)}\\) litres."],
            "Amount = initial amount + integral of the rate over the time interval.",
            "Add the initial volume — it is the constant of integration.",
            quicker="Under a decreasing linear rate the inflow is a triangle: ½ × base × initial rate.",
            common_errors=[err(vol - V0, "incomplete reasoning", "constant of integration", f"Add the initial {V0} litres.", step=2, part="b")
                           if V0 else err(c * Ts, "conceptual", MOD, "The rate decreases: integrate it.", step=2, part="b"),
                           err(c * Ts + V0, "conceptual", MOD, "The rate decreases over time: integrate, don't multiply the initial rate by the time.", step=2, part="b")],
            skill="Find an amount from a decreasing rate and an initial amount.",
            params={"form": "stop", "c": c, "k": kv, "V0": V0},
        )
    a, T = pick(r, [1, 2, 3, 6]), pick(r, [6, 10, 12])
    V0 = pick(r, [0, 100, 500])
    Rt = a * t * (T - t)
    Vt = V0 + sp.integrate(sp.expand(Rt), (t, 0, t))
    total = Vt.subs(t, T) - V0
    m = pick(r, [T // 2, T // 3, 2])
    text = multipart(f"Rain falls into a reservoir so that \\(t\\) hours after a storm begins, water flows in at \\(R = {co(a, '')}t({T} - t)\\) megalitres per hour, for \\(0 \\le t \\le {T}\\). Initially the reservoir holds {V0} megalitres.",
                     [("a", "At what time is the rate of inflow greatest?", 1),
                      ("b", "Find an expression for the volume \\(V\\) of water in the reservoir after \\(t\\) hours.", 2),
                      ("c", f"Find the volume after {m} hours.", 1), ("d", f"How much water flows in during the whole {T}-hour storm?", 1)])
    steps = [f"(a) \\(R\\) is a concave-down parabola with zeros \\(0\\) and \\({T}\\), so it is greatest at \\(t = {L(sp.Rational(T, 2))}\\).",
             f"(b) \\(V = {V0} + \\displaystyle\\int_0^t {co(a, '')}s({T} - s)\\,ds = {tl(Vt)}\\).",
             f"(c) \\(V({m}) = {L(Vt.subs(t, m))}\\) megalitres.",
             f"(d) \\(V({T}) - V(0) = {L(total)}\\) megalitres."]
    return Generated(
        text, A_parts(P("a", 1, A_num(sp.Rational(T, 2))), P("b", 2, A_expr(Vt, ("t",))), P("c", 1, A_num(Vt.subs(t, m))), P("d", 1, A_num(total))), 5, 3, steps,
        "The volume is the initial volume plus the integral of the inflow rate; the rate's maximum is a separate question about \\(R\\).",
        "Keep the rate \\(R\\) and the volume \\(V\\) clearly separate in your working.",
        quicker="The total inflow is the area under the rate graph: for a parabola that is \\(\\frac{a T^3}{6}\\).",
        common_errors=[err(Vt - V0, "incomplete reasoning", "constant of integration", "Include the initial volume.", step=2, part="b")
                       if V0 else err(sp.diff(Rt, t), "conceptual", MOD, "Integrate the rate to get the volume.", step=2, part="b"),
                       err(Rt.subs(t, m), "conceptual", MOD, "That is the inflow rate at that time, not the volume.", step=3, part="c"),
                       err(Vt.subs(t, T), "interpretation", MOD, "That includes the initial volume; the question asks how much flows in.", step=4, part="d")
                       if V0 else err(Rt.subs(t, sp.Rational(T, 2)) * T, "conceptual", MOD, "Integrate the rate over the storm.", step=4, part="d")],
        skill="Integrate a rate to model accumulation.",
        checkpoints=[cp(Vt, "the volume function", step=2, part="c", vars_=("t",))],
        params={"form": "storm", "a": a, "T": T, "V0": V0, "m": m},
    )


# ======================================================================= 7E ===
def t_7E(r: Rng, d: int) -> Generated:
    if d == 1:
        N0 = pick(r, [200, 500, 1200, 3000, 50])
        kv = pick(r, [sp.Rational(1, 10), sp.Rational(3, 100), sp.Rational(1, 20), sp.Rational(-1, 25), sp.Rational(-3, 50)])
        T = r.randint(3, 20)
        val = N0 * sp.exp(kv * T)
        word = "growing" if kv > 0 else "decaying"
        return Generated(
            f"A population is {word} according to \\(N = {N0}e^{{{L(kv * t)}}}\\), where \\(t\\) is in years. Find the population after {T} years, to the nearest whole number.",
            A_round(val, 0), 2, 1,
            [f"\\(N({T}) = {N0}e^{{{L(kv * T)}}} \\approx {float(val):.3f}\\).", f"To the nearest whole number: \\({int(math.floor(float(val) + 0.5))}\\)."],
            "In \\(N = N_0e^{kt}\\), \\(N_0\\) is the initial value and \\(k\\) the growth constant (negative for decay).",
            "Show the substituted expression before the calculator value.",
            quicker="Estimate first: \\(e^{kt} \\approx 1 + kt\\) for small \\(kt\\).",
            common_errors=[err(rnd(N0 * sp.exp(kv) * T, 0), "careless error", "calculator error", "Put the whole index \\(kt\\) inside the exponential: use brackets on the calculator.", step=1),
                           err(rnd(N0 * (1 + kv) ** T, 0), "formula selection", MOD, "That is compound growth \\((1 + k)^t\\); the model is \\(e^{kt}\\).", step=1)],
            skill="Evaluate an exponential growth or decay model.",
            params={"form": "eval", "N0": N0, "k": str(kv), "T": T},
        )
    if d == 2:
        if r.random() < 0.5:
            h = pick(r, [5, 8, 10, 12, 20, 30])
            kv = sp.log(2) / h
            return Generated(
                f"A radioactive substance has a half-life of {h} years. Its mass is \\(M = M_0e^{{-kt}}\\). Find the exact value of \\(k\\).",
                A_num(kv), 2, 2,
                [f"After one half-life \\(M = \\tfrac12M_0\\): \\(e^{{-{h}k}} = \\tfrac12\\).", f"\\(-{h}k = \\ln\\tfrac12 = -\\ln 2\\), so \\(k = \\dfrac{{\\ln 2}}{{{h}}}\\)."],
                "The half-life is the time for the quantity to halve, so \\(e^{-kh} = \\frac12\\).",
                "Keep \\(k\\) exact (with \\(\\ln 2\\)) to avoid rounding errors later.",
                quicker="For any half-life \\(h\\), \\(k = \\frac{\\ln 2}{h}\\).",
                common_errors=[err(-kv, "careless error", "sign error", "With the model \\(M_0e^{-kt}\\), \\(k\\) is positive.", step=2),
                               err(sp.Rational(1, 2 * h), "conceptual", "log laws", "Solve \\(e^{-kh} = \\frac12\\) with logarithms.", step=2)],
                skill="Find the decay constant from a half-life.",
                params={"form": "half", "h": h},
            )
        N0 = pick(r, [100, 200, 400, 1000])
        f = pick(r, [2, 3, sp.Rational(3, 2), sp.Rational(5, 2)])
        t1 = pick(r, [2, 3, 4, 5, 10])
        kv = sp.log(f) / t1
        return Generated(
            f"A population grows according to \\(P = {N0}e^{{kt}}\\), with \\(t\\) in years. After {t1} years the population is {L(N0 * f)}. Find the exact value of \\(k\\).",
            A_num(kv), 2, 2,
            [f"\\({L(N0 * f)} = {N0}e^{{{t1}k}}\\), so \\(e^{{{t1}k}} = {L(f)}\\).", f"\\(k = \\dfrac{{\\ln {L(f)}}}{{{t1}}}\\)."],
            "Two values of an exponential model determine \\(k\\): divide to cancel \\(P_0\\), then take logarithms.",
            "Isolate the exponential before taking logs.",
            quicker="\\(k = \\frac{1}{t}\\ln\\frac{P}{P_0}\\).",
            common_errors=[err(sp.log(N0 * f) / t1, "algebraic", "log laws", f"Divide by {N0} before taking logarithms.", step=1),
                           err(sp.log(f) * t1, "algebraic", "algebra", f"Divide by {t1}.", step=2)],
            skill="Find a growth constant from two measurements.",
            params={"form": "k", "N0": N0, "f": str(f), "t1": t1},
        )
    if r.random() < 0.5:
        N0 = pick(r, [500, 800, 1000, 2000, 5000])
        f = pick(r, [2, 3, sp.Rational(3, 2)])
        t1 = pick(r, [4, 5, 8, 10])
        kv = sp.log(f) / t1
        T = t1 + r.randint(2, 8)
        M = N0 * pick(r, [4, 5, 6, 10])
        tM = sp.log(sp.Rational(M, N0)) / kv
        PT = N0 * sp.exp(kv * T)
        rateM = kv * M
        text = multipart(f"A town's population is modelled by \\(P = {N0}e^{{kt}}\\), where \\(t\\) is the number of years after 2020. In {2020 + t1} the population was {L(N0 * f)}.",
                         [("a", "Find the exact value of \\(k\\).", 1), ("b", f"Find the population in {2020 + T}, to the nearest whole number.", 1),
                          ("c", f"After how many years will the population reach {M}? Answer correct to 1 decimal place.", 2),
                          ("d", f"At what rate is the population growing when it is {M}? Answer to the nearest whole number of people per year.", 1)])
        steps = [f"(a) \\({L(N0 * f)} = {N0}e^{{{t1}k}}\\), so \\(k = \\dfrac{{\\ln {L(f)}}}{{{t1}}}\\).",
                 f"(b) \\(P({T}) = {N0}e^{{{T}k}} \\approx {float(PT):.2f}\\), i.e. about {int(math.floor(float(PT) + 0.5))} people.",
                 f"(c) \\({M} = {N0}e^{{kt}}\\) gives \\(t = \\dfrac{{\\ln {L(sp.Rational(M, N0))}}}{{k}} \\approx {float(tM):.3f}\\).",
                 f"So about {float(tM):.1f} years.",
                 f"(d) \\(\\dfrac{{dP}}{{dt}} = kP = {L(kv)}\\times {M} \\approx {float(rateM):.2f}\\) people per year."]
        return Generated(
            text,
            A_parts(P("a", 1, A_num(kv)), P("b", 1, A_round(PT, 0)), P("c", 2, A_round(tM, 1, "years")), P("d", 1, A_round(rateM, 0))), 5, 3, steps,
            "Exponential growth \\(P = P_0e^{kt}\\) satisfies \\(\\frac{dP}{dt} = kP\\): the growth rate is proportional to the population.",
            "Use the exact \\(k\\) in later parts; rounding \\(k\\) early changes the answers.",
            quicker="For (d) there is no need to find the time: \\(\\frac{dP}{dt} = kP\\) directly.",
            common_errors=[err(sp.log(N0 * f) / t1, "algebraic", "log laws", f"Divide by {N0} before taking logs.", step=1, part="a"),
                           err(rnd(N0 * sp.exp(sp.Float(round(float(kv), 2)) * T), 0), "careless error", "rounding", "Don't round \\(k\\) before using it.", step=2, part="b"),
                           err(rnd(kv * N0, 0), "conceptual", MOD, f"\\(\\frac{{dP}}{{dt}} = kP\\) with \\(P = {M}\\), not the initial population.", step=5, part="d"),
                           err(rnd(sp.log(M) / kv, 1), "algebraic", "log laws", f"Divide by {N0} first: \\(e^{{kt}} = \\frac{{{M}}}{{{N0}}}\\).", step=3, part="c")],
            skill="Build and use an exponential growth model.",
            params={"form": "growth", "N0": N0, "f": str(f), "t1": t1, "T": T, "M": M},
        )
    A = pick(r, [18, 20, 22, 25])
    B = pick(r, [60, 70, 75, 80])
    t1 = pick(r, [5, 10])
    T1 = A + B // 2 if r.random() < 0.5 else A + B // 4
    kv = sp.log(sp.Rational(B, T1 - A)) / t1
    target = A + pick(r, [5, 10])
    tT = sp.log(sp.Rational(B, target - A)) / kv
    text = multipart(f"A cup of coffee cools in a room at {A}°C. Its temperature after \\(t\\) minutes is \\(T = {A} + Be^{{-kt}}\\). Initially the coffee is at {A + B}°C, and after {t1} minutes it is at {T1}°C.",
                     [("a", "Find \\(B\\).", 1), ("b", "Find the exact value of \\(k\\).", 2),
                      ("c", f"How long does the coffee take to cool to {target}°C? Answer in minutes, correct to 1 decimal place.", 2)])
    steps = [f"(a) At \\(t = 0\\): \\({A + B} = {A} + B\\), so \\(B = {B}\\).",
             f"(b) \\({T1} = {A} + {B}e^{{-{t1}k}}\\), so \\(e^{{-{t1}k}} = {L(sp.Rational(T1 - A, B))}\\).",
             f"\\(k = \\dfrac{{1}}{{{t1}}}\\ln {L(sp.Rational(B, T1 - A))}\\).",
             f"(c) \\({target} = {A} + {B}e^{{-kt}}\\) gives \\(t = \\dfrac{{1}}{{k}}\\ln {L(sp.Rational(B, target - A))} \\approx {float(tT):.3f}\\), so about {float(tT):.1f} minutes."]
    return Generated(
        text, A_parts(P("a", 1, A_num(B)), P("b", 2, A_num(kv)), P("c", 2, A_round(tT, 1, "min"))), 5, 3, steps,
        "Newton's law of cooling: the excess temperature above the surroundings decays exponentially.",
        "Subtract the room temperature before taking logarithms — the most common slip.",
        quicker="Work with the excess temperature \\(T - A\\): it halves, thirds, … like any decay.",
        common_errors=[err(A + B, "interpretation", MOD, "\\(B\\) is the initial excess over room temperature.", step=1, part="a"),
                       err(sp.log(sp.Rational(A + B, T1)) / t1, "conceptual", MOD, "Subtract the room temperature first: \\(T - A = Be^{-kt}\\).", step=2, part="b"),
                       err(rnd(sp.log(sp.Rational(A + B, target)) / kv, 1), "conceptual", MOD, "Use the excess temperature \\(T - A\\).", step=4, part="c")],
        skill="Use Newton's law of cooling.",
        params={"form": "cool", "A": A, "B": B, "t1": t1, "T1": T1, "target": target},
    )
