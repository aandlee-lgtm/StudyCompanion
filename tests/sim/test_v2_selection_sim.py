"""Longitudinal selection simulations (selection-21): the defects the v1 audit measured are now
asserted over simulated weeks of study, with the real engine and the real marking pipeline."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

import pytest

from tests.sim.harness import WEAK_ITEMS, SimResult, run_sim

START = date(2026, 10, 12)  # a Monday


# ------------------------------------------------------------------ invariants ---
def check_counts(res: SimResult, counts=(5, 3, 3)) -> None:
    for r in res.study_days():
        c = Counter(i["subject"] for i in r.items)
        assert (c["MATHS"], c["ENGLISH"], c["LEGAL"]) == counts, (r.day, c)


def check_no_early_exact_repeat(res: SimResult, strict: bool) -> None:
    """An exact repeat before its revision date only ever comes from the labelled fallback ladder
    (and, with a v2-sized bank, never at all). Never on consecutive study days."""
    last_served: dict[int, date] = {}
    for r in res.study_days():
        for i in r.items:
            prev = i["prev"]
            if prev and prev[1] and prev[1] > r.day:
                assert not strict, f"{r.day}: question {i['qid']} repeated before its revision date {prev[1]}"
                assert i["kind"] in ("ladder", "retry", "repeat", "near_duplicate"), (r.day, i)
                assert any(w in i["reason"] for w in ("Repeat", "Rewrite")), i["reason"]
            if i["qid"] in last_served:
                assert (r.day - last_served[i["qid"]]).days >= 3, f"{i['qid']} served {last_served[i['qid']]} and {r.day}"
        for i in r.items:
            last_served[i["qid"]] = r.day


def check_one_passage(res: SimResult) -> None:
    for r in res.study_days():
        units = {i["unit"] for i in r.items if i["subject"] == "ENGLISH" and i["category"] == "unseen"}
        assert len(units) <= 1, (r.day, units)


def check_distinct_marks(res: SimResult) -> None:
    for r in res.study_days():
        marks = [i["marks"] for i in r.items if i["subject"] == "ENGLISH" and i["category"] == "unseen"]
        assert len(marks) == len(set(marks)), (r.day, marks)


def check_maths_forms(res: SimResult, max_repeat_days: float) -> None:
    """At most one question per form per session; a second instance only for a learning item with
    no alternative, on a small share of days."""
    repeat_days = 0
    for r in res.study_days():
        forms = Counter(i["form"] for i in r.items if i["subject"] == "MATHS")
        dup = {f for f, n in forms.items() if n > 1}
        for f in dup:
            assert forms[f] <= 2, (r.day, f)
            assert all(i["bucket"] == "learning" for i in r.items if i["form"] == f), (r.day, f)
        repeat_days += bool(dup)
    assert repeat_days <= max_repeat_days * len(res.study_days()), repeat_days


def check_legal_daily(res: SimResult) -> None:
    from app.selection.context import verb_tier_of

    for r in res.study_days():
        legal = [i for i in r.items if i["subject"] == "LEGAL"]
        fmts = Counter(i["format"] for i in legal)
        ext = fmts["extended"]
        assert ext <= 1
        assert fmts["mcq"] <= (2 if ext else 1), (r.day, fmts)
        assert max(verb_tier_of(i["type"], i["verb"], "", i["marks"]) for i in legal) >= 2, (r.day, legal)
        assert len({i["unit"] for i in legal if i["unit"]}) <= 1


def check_window(res: SimResult, share: float) -> None:
    days = res.study_days()
    ok = sum(1 for r in days if r.window[0] <= r.expected <= r.window[1])
    assert ok >= share * len(days), f"{ok}/{len(days)} days in the window: {[r.expected for r in days]}"


def check_y11_coverage(res: SimResult, window_days: int = 20) -> None:
    days = res.study_days()
    for k in range(0, len(days) - window_days + 1, window_days):
        block = days[k:k + window_days]
        seen = {i["item"] for r in block for i in r.items}
        missing = res.y11_codes - seen
        assert not missing, f"Year 11 items not served between {block[0].day} and {block[-1].day}: {missing}"


def check_band_stability(res: SimResult) -> None:
    bands = [r.band for r in res.study_days() if r.band]
    changes = [k for k in range(1, len(bands)) if bands[k] != bands[k - 1]]
    for a, b in zip(changes, changes[1:]):
        assert b - a >= 3, f"difficulty band changed at sessions {a} and {b}: {bands}"


def check_stimulus_weekly(res: SimResult) -> None:
    weeks: dict[date, int] = defaultdict(int)
    days_in_week: dict[date, int] = defaultdict(int)
    for r in res.study_days():
        monday = r.day - timedelta(days=r.day.weekday())
        days_in_week[monday] += 1
        weeks[monday] += sum(1 for i in r.items if i["format"] == "stimulus")
    for monday, n in weeks.items():
        if days_in_week[monday] == 5:
            assert n >= 2, f"week of {monday}: {n} stimulus questions"


def check_extended(res: SimResult) -> None:
    ext = [(r.day, i["item"]) for r in res.study_days() for i in r.items if i["format"] == "extended"]
    assert ext, "no extended response at all"
    first4 = {item for _d, item in ext[:4]}
    if len(ext) >= 2:
        assert {"LS-CRIME", "LS-HR"} <= first4, ext
    for (d1, _a), (d2, _b) in zip(ext, ext[1:]):
        assert (d2 - d1).days >= 7, ext  # Term 4: never more than about one a week
    # monthly (4-week) counts never fall as the year progresses
    blocks = Counter((d - START).days // 28 for d, _ in ext)
    full = [blocks.get(k, 0) for k in range(max(blocks) + 1)][: (res.study_days()[-1].day - START).days // 28]
    assert all(b >= a for a, b in zip(full, full[1:])) or len(full) < 2, full


# ----------------------------------------------------------------------- fast ---
def test_mixed_student_v2_bank_four_weeks(sim_dir):
    res = run_sim(sim_dir, "mixed", 4, start=START)
    check_counts(res)
    check_window(res, 0.9)
    check_no_early_exact_repeat(res, strict=True)
    check_one_passage(res)
    check_distinct_marks(res)
    check_maths_forms(res, 0.25)
    check_legal_daily(res)
    check_stimulus_weekly(res)
    check_y11_coverage(res)
    check_band_stability(res)
    nums = [r.number for r in res.study_days()]
    assert nums == list(range(1, len(nums) + 1))


def test_small_bank_uses_labelled_fallbacks_never_consecutive_days(sim_dir):
    """With the v1 seed bank only, English and Legal run dry within a week: repeats then come
    from the labelled ladder (rewrite tasks, oldest-seen repeats), never back to back."""
    res = run_sim(sim_dir, "mixed", 3, start=START, v2_bank=False)
    check_no_early_exact_repeat(res, strict=False)
    check_one_passage(res)
    kinds = Counter(i["kind"] for r in res.study_days() for i in r.items)
    assert kinds["retry"] > 0  # rewrite tasks are used before plain repeats
    notes = " ".join(n for r in res.study_days() for n in r.notes)
    assert "unread passage" in notes and "Legal Studies: only" in notes  # bank health is reported


def test_resumed_missed_day_shares_nothing_with_today(sim_dir):
    miss = {START + timedelta(days=1), START + timedelta(days=8)}
    res = run_sim(sim_dir, "mixed", 2, start=START, miss=miss, missaction="resume")
    overlaps = [r.resume_overlap for r in res.records if r.resume_overlap is not None]
    assert overlaps and all(o == 0 for o in overlaps)


def test_light_mode_is_shorter_with_fewer_questions(sim_dir):
    res = run_sim(sim_dir, "mixed", 1, start=START, mode="light")
    check_counts(res, (3, 2, 2))
    for r in res.study_days():
        assert r.expected <= 50.5, r.expected
        assert not any(i["format"] == "extended" for i in r.items)
    check_window(res, 0.8)


def test_exam_mode_has_no_foundation_maths(sim_dir):
    res = run_sim(sim_dir, "strong", 1, start=START, mode="exam")
    for r in res.study_days():
        assert all(i["difficulty"] >= 2 for i in r.items if i["subject"] == "MATHS"), r.day


# ----------------------------------------------------------------------- slow ---
@pytest.mark.slow
@pytest.mark.parametrize("profile", ["mixed", "strong", "struggling", "improving"])
def test_twelve_week_profiles(sim_dir, profile):
    res = run_sim(sim_dir, profile, 12, start=START)
    check_counts(res)
    check_window(res, 0.9)
    check_no_early_exact_repeat(res, strict=False)
    check_one_passage(res)
    check_distinct_marks(res)
    check_maths_forms(res, 0.2)
    check_legal_daily(res)
    check_stimulus_weekly(res)
    check_y11_coverage(res)
    check_band_stability(res)
    check_extended(res)
    if profile == "mixed":  # weak items get at least twice the exposure of mastered ones (selection-05)
        served = Counter(i["item"] for r in res.study_days() for i in r.items if i["subject"] == "MATHS")
        weak_y11 = [served[c] for c in res.y11_codes & WEAK_ITEMS]
        strong_y11 = [served[c] for c in res.y11_codes - WEAK_ITEMS]
        assert sum(weak_y11) / len(weak_y11) >= 2 * sum(strong_y11) / len(strong_y11), (weak_y11, strong_y11)


@pytest.mark.slow
def test_holiday_block_focuses_on_weak_areas(sim_dir):
    res = run_sim(sim_dir, "mixed", 6, start=START, holiday=(START + timedelta(days=21), START + timedelta(days=34)))
    hol = [r for r in res.study_days() if r.mode == "holiday"]
    assert hol
    for r in hol:
        assert r.window[1] <= 80.5
        weak = [i for i in r.items if i["subject"] == "MATHS" and "weak_focus" in i["flags"]]
        assert len(weak) >= 1, r.day
