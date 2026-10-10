"""Mathematics: two-stage selection (selection-05) producing duration-diverse candidate sets.

Stage 1 gives today's slots to plan items: the learning/recent/older mix fixes how many slots
each bucket gets, and within a bucket items compete on their stage-1 priority (weights). A
recent/older item gets one slot unless its bucket has no other item (selection-06); a struggling
item is guaranteed a slot at least every second session; holiday mode reserves slots for the
weakest items. Stage 2 picks the question for each slot (difficulty fit for that item, novelty,
source) under hard rules: one question per form per session (selection-07) and no
near-duplicates."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.selection.context import StudentContext
from app.selection.optimiser import Option
from app.selection.pool import Pool, near_duplicate
from app.selection.scoring import FRESH, LADDER, REPEAT, RETRY, Scored, item_priority, learning_bucket

BUCKETS = ("learning", "recent", "older")
BANDS = [  # (upper bound of target difficulty, band, foundation/HSC/challenging out of 5)
    (1.35, "consolidate", {1: 3, 2: 2, 3: 0}),
    (1.85, "start", None),
    (2.2, "build", {1: 1, 2: 3, 3: 1}),
    (2.6, "stretch", {1: 1, 2: 2, 3: 2}),
    (9.0, "exam-ready", {1: 0, 2: 3, 3: 2}),
]
HYSTERESIS = 0.08


def _apportion(mix: dict, n: int) -> dict:
    raw = {k: max(0.0, float(v)) * n / (sum(max(0.0, float(x)) for x in mix.values()) or 1) for k, v in mix.items()}
    q = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - q[k], reverse=True)[: n - sum(q.values())]:
        q[k] += 1
    return q


def maths_bucket_quota(ctx: StudentContext, n: int | None = None) -> dict[str, int]:
    n = ctx.profile.counts["MATHS"] if n is None else n
    mix = {k: ctx.profile.maths_mix.get(k, 0) for k in BUCKETS}
    return _apportion(mix, n)


def _band_index(t: float) -> int:
    return next(i for i, (ub, _n, _q) in enumerate(BANDS) if t < ub)


def difficulty_band(ctx: StudentContext) -> str:
    """The foundation/HSC/challenging band, with hysteresis: it changes only when the target has
    clearly crossed a boundary, and at most once in three sessions (selection-09)."""
    t = ctx.target_difficulty("MATHS")
    raw = BANDS[_band_index(t)][1]
    prev = [b for _d, b in ctx.previous_bands if any(b == x[1] for x in BANDS)]
    if not prev or raw == prev[0]:
        return raw
    last = prev[0]
    li = next(i for i, x in enumerate(BANDS) if x[1] == last)
    lo_b = BANDS[li - 1][0] if li > 0 else -9.0
    hi_b = BANDS[li][0]
    if lo_b - HYSTERESIS <= t < hi_b + HYSTERESIS:
        return last
    if len(prev) >= 3 and len(set(prev[:3])) > 1:
        return last  # changed within the last three sessions: hold
    return raw


def maths_difficulty_quota(ctx: StudentContext, n: int | None = None) -> dict[int, int]:
    """Foundation/HSC/challenging composition. Starts at 2/2/1 and shifts with the band (year
    progress + performance). Always keeps HSC-standard work."""
    n = ctx.profile.counts["MATHS"] if n is None else n
    start = ctx.settings.get("maths_difficulty_start") or {"foundation": 2, "hsc": 2, "challenge": 1}
    band = difficulty_band(ctx)
    q5 = next(q for _ub, b, q in BANDS if b == band) or {1: start["foundation"], 2: start["hsc"], 3: start["challenge"]}
    q5 = dict(q5)
    if ctx.profile.difficulty_floor >= 2:
        q5[2] += q5.get(1, 0)
        q5[1] = 0
    q = _apportion(q5, n) if n != sum(q5.values()) else q5
    if q.get(2, 0) == 0 and n >= 2:  # never abandon HSC-standard questions
        donor = 1 if q.get(1, 0) > q.get(3, 0) else 3
        q[donor] -= 1
        q[2] = 1
    return {1: q.get(1, 0), 2: q.get(2, 0), 3: q.get(3, 0)}


@dataclass
class Slot:
    item_id: int | None
    bucket: str
    priority: float
    flags: list[str]
    protected: bool
    cands: list[Scored] = field(default_factory=list)
    repeat_form_ok: bool = False  # a second instance of a form, only when no alternative exists


def _weakest(ctx: StudentContext, item_ids: list[int | None], k: int) -> list[int | None]:
    scored = []
    for i in item_ids:
        m = ctx.mastery.get(i or -1)
        if m is not None and m.attempts >= 2:
            scored.append((m.mastery, i))
    return [i for _m, i in sorted(scored)[:k]]


def allocate(ctx: StudentContext, pool: Pool, n: int) -> tuple[list[Slot], dict]:
    """Stage 1: give the n slots to plan items."""
    by_item = pool.by_item()
    for lst in by_item.values():  # verify the leading candidates so capacity counts real options
        forms: set[str] = set()
        for s in lst:
            pool.verify(s)
            forms.add(pool.form(s))
            if len(forms) >= 4:
                break
        lst.sort(key=lambda s: (s.tier, -s.score))
    facts: dict = {"notes": [], "learning_without_questions": []}
    max_tier = FRESH
    for t in (FRESH, LADDER, RETRY, REPEAT):
        max_tier = t
        cap_total = sum(len({pool.form(s) for s in lst if s.tier <= t}) for lst in by_item.values())
        if cap_total >= n:
            break
    facts["max_tier"] = max_tier
    info = {}
    for item_id, lst in by_item.items():
        forms = {pool.form(s) for s in lst if s.tier <= max_tier}
        if not forms:
            continue
        p, f, flags = item_priority(ctx, item_id)
        item = ctx.plan.get(item_id or -1)
        n_q = sum(1 for s in lst if s.tier <= max_tier)
        info[item_id] = {"prio": p, "flags": flags, "bucket": learning_bucket(ctx, item), "cap": len(forms), "n_q": n_q,
                         "chapter": getattr(item, "chapter", None)}
    for it in ctx.plan.values():
        if it.subject.code == "MATHS" and it.status == "LEARNING" and it.active and it.id not in info:
            facts["learning_without_questions"].append(it.id)
    if ctx.profile.weak_focus:
        for i in _weakest(ctx, list(info), ctx.profile.weak_focus):
            info[i]["prio"] += 0.6
            info[i]["flags"].append("weak_focus")
    learning_chapters = {v["chapter"] for v in info.values() if v["bucket"] == "learning"}
    for v in info.values():  # when the learning item is short of forms, prefer recent work from the same chapter
        if v["bucket"] == "recent" and v["chapter"] in learning_chapters:
            v["prio"] += 0.05
    quota = maths_bucket_quota(ctx, n)
    per_bucket = {b: [i for i, v in info.items() if v["bucket"] == b] for b in BUCKETS}
    count: dict = {}
    slots: list[Slot] = []

    def cap(i, bucket, relaxed):
        c = info[i]["cap"]
        if relaxed >= 2:
            return c
        if bucket == "learning" or relaxed:
            return min(c, 3)
        return min(c, 1 if len(per_bucket[bucket]) > 1 else 2)

    def take(bucket_list, relaxed, extra_cap: int = 0, repeat_form_ok: bool = False) -> bool:
        best, best_v = None, None
        for i in bucket_list:
            if count.get(i, 0) >= min(cap(i, info[i]["bucket"], relaxed) + extra_cap, info[i]["n_q"]):
                continue
            decay = 0.55 if info[i]["bucket"] == "learning" else 0.35
            v = info[i]["prio"] * (decay ** count.get(i, 0))
            if best_v is None or v > best_v:
                best, best_v = i, v
        if best is None:
            return False
        first = count.get(best, 0) == 0
        count[best] = count.get(best, 0) + 1
        fl = info[best]["flags"]
        protected = bool({"catch_up", "rebuild", "revision_due", "weak_focus"} & set(fl)) or (info[best]["bucket"] == "learning" and first)
        slots.append(Slot(best, info[best]["bucket"], round(best_v, 4), list(fl), protected, repeat_form_ok=repeat_form_ok))
        return True

    leftover = {b: 0 for b in BUCKETS}
    for b in BUCKETS:
        for _ in range(quota.get(b, 0)):
            if not take(per_bucket[b], 0):
                leftover[b] += 1
    # Learning slots the current items cannot fill with distinct forms: recent work from the same
    # chapter first, then (no alternative) a second instance of a learning form (selection-07).
    same_chapter = [i for i in per_bucket["recent"] if info[i]["chapter"] in learning_chapters]
    while leftover["learning"] and take(same_chapter, 0):
        leftover["learning"] -= 1
    while leftover["learning"] and per_bucket["learning"] and take(per_bucket["learning"], 1, extra_cap=1, repeat_form_ok=True):
        leftover["learning"] -= 1
    rest = sum(leftover.values())
    for relaxed in (1, 2):
        for b in BUCKETS:
            while rest and take(per_bucket[b], relaxed):
                rest -= 1
    facts["quota"] = quota
    facts["achieved"] = {b: sum(1 for s in slots if s.bucket == b) for b in BUCKETS}
    facts["info"] = {i: {"prio": v["prio"], "flags": v["flags"], "bucket": v["bucket"]} for i, v in info.items()}
    return slots, facts


def _slot_candidates(ctx: StudentContext, pool: Pool, slots: list[Slot], max_tier: int) -> None:
    allocated = {s.item_id for s in slots}
    by_bucket_alts: dict[str, list] = {}
    for s in slots:
        s.cands = [c for c in pool.ranked(lambda c, i=s.item_id: c.question.plan_item_id == i and c.tier <= max_tier, k=6)
                   if c.tier <= max_tier]
        if s.protected:
            continue
        if s.bucket not in by_bucket_alts:
            alts = []
            others = sorted(
                {c.question.plan_item_id for c in pool.cands if c.bucket == s.bucket and c.question.plan_item_id not in allocated and c.tier <= max_tier},
                key=lambda i: -item_priority(ctx, i)[0],
            )[:2]
            for i in others:
                alts.extend(c for c in pool.ranked(lambda c, i=i: c.question.plan_item_id == i and c.tier <= max_tier, k=3)
                            if c.tier <= max_tier)
            by_bucket_alts[s.bucket] = alts
        s.cands = s.cands + by_bucket_alts[s.bucket]


def pick_maths(ctx: StudentContext, pool: Pool, n: int | None = None) -> tuple[list[Option], dict]:
    n = ctx.profile.counts["MATHS"] if n is None else n
    slots, facts = allocate(ctx, pool, n)
    _slot_candidates(ctx, pool, slots, facts["max_tier"])
    dq = maths_difficulty_quota(ctx, n)
    facts["difficulty_quota"] = dq
    facts["band"] = difficulty_band(ctx)
    floor = ctx.profile.difficulty_floor
    # beam search over slots, keeping duration diversity
    states = [(0.0, 0.0, ())]
    for allow_same_form in (False, True):
        states = [(0.0, 0.0, ())]
        for slot in slots:
            nxt = []
            for val, mins, chosen in states:
                forms = {pool.form(c) for c in chosen}
                for c in slot.cands:
                    if any(c.question.id == x.question.id for x in chosen):
                        continue
                    f = pool.form(c)
                    pen = 0.0
                    if f in forms:
                        same = sum(1 for x in chosen if pool.form(x) == f)
                        if slot.repeat_form_ok and same < 2:
                            pen += 0.4
                        elif not allow_same_form:
                            continue
                        else:
                            pen += 1.0
                    if any(near_duplicate(c.question, x.question) for x in chosen):
                        continue
                    last = ctx.recent_forms.get(f)
                    if last is not None:
                        gap = (ctx.today - last).days
                        pen += 0.3 if gap <= 3 else (0.1 if gap <= 7 else 0.0)
                    if (c.question.difficulty or 2) < floor:
                        pen += 1.5
                    nxt.append((val + c.score - pen, mins + c.minutes, chosen + (c,)))
            if not nxt:
                continue  # this slot cannot be filled without breaking a rule
            bins: dict[int, list] = {}
            for st in nxt:
                bins.setdefault(int(st[1]), []).append(st)
            states = []
            for lst in bins.values():
                lst.sort(key=lambda st: -st[0])
                states.extend(lst[:4])
            states.sort(key=lambda st: -st[0])
            states = states[:120]
        if states and len(states[0][2]) >= min(n, len(slots)):
            break
    if states and len(states[0][2]) < n:  # a slot could not be filled: complete from any remaining candidate
        filler = [c for c in pool.ranked(lambda c: c.tier <= max(facts["max_tier"], REPEAT), k=12)]
        grown = []
        for val, mins, chosen in states[:20]:
            forms = {pool.form(c) for c in chosen}
            for c in filler:
                if len(chosen) >= n:
                    break
                if c.question.id in {x.question.id for x in chosen} or pool.form(c) in forms:
                    continue
                if any(near_duplicate(c.question, x.question) for x in chosen):
                    continue
                chosen = chosen + (c,)
                forms.add(pool.form(c))
                val, mins = val + c.score, mins + c.minutes
            grown.append((val, mins, chosen))
        states = grown
    options = []
    for val, mins, chosen in states:
        if not chosen:
            continue
        counts = {1: 0, 2: 0, 3: 0}
        for c in chosen:
            counts[max(1, min(3, c.question.difficulty or 2))] += 1
        dev = sum(abs(counts[d] - dq.get(d, 0)) for d in counts) / 2
        short = max(0, n - len(chosen))
        options.append(Option("MATHS", list(chosen), round(val - 0.15 * dev - 3.0 * short, 4), round(mins, 2),
                              facts={"difficulty_counts": counts}))
    facts["slots"] = [{"item": s.item_id, "bucket": s.bucket, "flags": s.flags, "protected": s.protected} for s in slots]
    return options, facts
