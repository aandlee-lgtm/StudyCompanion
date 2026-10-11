"""Joint set optimiser (selection-01/02).

Each subject offers a list of complete, rule-respecting candidate sets (``Option``), each with an
educational value and a duration. The optimiser picks one set per subject to maximise the total
value minus time penalties: minutes outside the day's window cost a lot, minutes outside a
subject's envelope cost a little. Time is therefore a penalty term, never a rule that can swap a
weak-area or revision-due question for an unrelated one: the subject pickers only offer
alternatives that keep the day's priorities (other questions on the same plan item, or a
lower-priority 'flex' slot)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.selection.scoring import Scored

LAMBDA_WINDOW = 0.08  # value lost per minute outside the day's window
LAMBDA_ENVELOPE = 0.02  # value lost per minute outside a subject's envelope
LAMBDA_TARGET = 0.004  # gentle pull towards the target inside the window


@dataclass
class Option:
    subject: str
    items: list[Scored]
    value: float
    minutes: float  # question time plus reading time
    reading: float = 0.0
    facts: dict = field(default_factory=dict)

    @property
    def ids(self) -> set[int]:
        return {s.question.id for s in self.items}


def _outside(x: float, lo: float, hi: float) -> float:
    return (lo - x) if x < lo else ((x - hi) if x > hi else 0.0)


def bin_options(options: list[Option], width: float = 0.5, keep: int = 2) -> list[Option]:
    """Keep the best ``keep`` options per duration bin (and always the overall best)."""
    if not options:
        return []
    best = max(options, key=lambda o: o.value)
    bins: dict[int, list[Option]] = {}
    for o in options:
        bins.setdefault(int(o.minutes / width), []).append(o)
    out = [best]
    for lst in bins.values():
        lst.sort(key=lambda o: -o.value)
        out.extend(o for o in lst[:keep] if o is not best)
    return out


def choose(options: dict[str, list[Option]], window: tuple[float, float, float],
           envelopes: dict[str, tuple[float, float]]) -> tuple[dict[str, Option], dict]:
    """Pick one option per subject. Returns the choice and facts about the time trade-off."""
    target, lo, hi = window
    codes = [c for c in options if options[c]]
    pruned = {c: bin_options(options[c]) for c in codes}
    # Fold subject by subject, keeping the best partial plan per quarter-minute of total time.
    # Envelope penalties are per subject, so they are added as each subject joins.
    table: dict[int, tuple[float, float, tuple[Option, ...]]] = {0: (0.0, 0.0, ())}
    for c in codes:
        elo, ehi = envelopes.get(c, (0, 999))
        nxt: dict[int, tuple[float, float, tuple[Option, ...]]] = {}
        for _key, (val, mins, combo) in table.items():
            for o in pruned[c]:
                v = val + o.value - LAMBDA_ENVELOPE * _outside(o.minutes, elo, ehi)
                m = mins + o.minutes
                k = int(round(m * 4))
                if k not in nxt or v > nxt[k][0] + 1e-9:
                    nxt[k] = (v, m, combo + (o,))
        table = nxt
    best_combo, best_obj = None, None
    for val, mins, combo in table.values():
        obj = val - LAMBDA_WINDOW * _outside(mins, lo, hi) - LAMBDA_TARGET * abs(mins - target)
        if best_obj is None or obj > best_obj + 1e-9:
            best_obj, best_combo = obj, combo
    chosen = dict(zip(codes, best_combo)) if best_combo else {}
    total = round(sum(o.minutes for o in chosen.values()), 1)
    facts = {"total": total, "lo": lo, "hi": hi, "target": target, "in_window": lo <= total <= hi, "displaced": {}}
    for c in codes:
        top = max(options[c], key=lambda o: o.value)
        if chosen[c] is not top:
            facts["displaced"][c] = {
                "out": sorted(top.ids - chosen[c].ids), "in": sorted(chosen[c].ids - top.ids),
                "value_cost": round(top.value - chosen[c].value, 3), "minutes_gain": round(chosen[c].minutes - top.minutes, 1),
            }
    return chosen, facts
