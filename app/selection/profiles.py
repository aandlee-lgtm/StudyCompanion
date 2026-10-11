"""Mode profiles (spec 14 and 15): what a NORMAL, HOLIDAY/REVISION, EXAM or LIGHT day looks like.

A profile fixes the counts per subject, the time window, each subject's time envelope, the Maths
learning/recent/older mix, difficulty adjustments, and the extended-response policy. All numbers
come from Settings, so they can be changed without touching code."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.common import DAILY_COUNTS

MODES = ("normal", "holiday", "exam", "light")
MODE_LABELS = {"normal": "Normal", "holiday": "Holiday / revision", "exam": "Exam", "light": "Light day"}


@dataclass
class ModeProfile:
    name: str
    counts: dict[str, int]
    target: float
    lo: float
    hi: float
    envelopes: dict[str, tuple[float, float]]
    maths_mix: dict[str, float]
    difficulty_shift: float = 0.0
    difficulty_floor: int = 1
    extended: str = "plan"  # plan | none | exam
    timed: bool = False
    weak_focus: int = 0  # holiday: Maths slots reserved for the weakest items
    notes: list[str] = field(default_factory=list)

    @property
    def total_questions(self) -> int:
        return sum(self.counts.values())


def _envelopes(target: float, shares: dict[str, float], counts: dict[str, int]) -> dict[str, tuple[float, float]]:
    """Per-subject time envelope: share x target, +/-15%, scaled by the subject's count."""
    full = {k: max(1, v) for k, v in DAILY_COUNTS.items()}
    raw = {k: shares.get(k, 1 / 3) * (counts.get(k, 0) / full[k]) for k in DAILY_COUNTS}
    total = sum(raw.values()) or 1.0
    out = {}
    for k, v in raw.items():
        mid = target * v / total
        out[k] = (round(mid * 0.85, 1), round(mid * 1.15, 1))
    return out


def build_profile(mode: str, s: dict) -> ModeProfile:
    shares = s.get("selection_subject_shares") or {"MATHS": 0.40, "ENGLISH": 0.33, "LEGAL": 0.27}
    mix = dict(s.get("maths_mix") or {"learning": 0.55, "recent": 0.25, "older": 0.20})
    counts = dict(DAILY_COUNTS)
    target = float(s.get("target_minutes", 90) or 90)
    lo, hi = float(s.get("budget_min_minutes", 80) or 80), float(s.get("budget_max_minutes", 95) or 95)
    if not lo < target <= hi:  # a custom target without a matching window: keep a proportional window
        lo, hi = round(target * 0.89, 1), round(target * 1.06, 1)
    p = ModeProfile(name=mode, counts=counts, target=target, lo=lo, hi=hi, envelopes={}, maths_mix=mix)
    if mode == "light":
        lc = s.get("light_day_counts") or {"MATHS": 3, "ENGLISH": 2, "LEGAL": 2}
        p.counts = {k: max(1, min(DAILY_COUNTS[k], int(lc.get(k, DAILY_COUNTS[k])))) for k in DAILY_COUNTS}
        p.target = float(s.get("light_target_minutes", 45) or 45)
        p.lo, p.hi = p.target - 5, p.target + 5
        p.extended = "none"
        p.notes.append(f"Light day: {p.counts['MATHS']} Mathematics, {p.counts['ENGLISH']} English and "
                       f"{p.counts['LEGAL']} Legal Studies questions, about {p.target:.0f} minutes, no extended response.")
    elif mode == "holiday":
        p.target = float(s.get("holiday_target_minutes", 75) or 75)
        p.lo, p.hi = round(p.target - 10, 1), round(p.target + 5, 1)
        p.maths_mix = {"learning": 0.35, "recent": 0.35, "older": 0.30}
        p.difficulty_shift = -0.1
        p.weak_focus = 2
        p.notes.append("Holiday / revision mode: less new content, more revision, and at least two Mathematics questions "
                       "from your weakest areas.")
    elif mode == "exam":
        p.lo, p.hi = max(p.lo, round(p.target * 0.94, 1)), p.hi
        p.maths_mix = {"learning": 0.30, "recent": 0.35, "older": 0.35}
        p.difficulty_shift = 0.3
        p.difficulty_floor = int(s.get("exam_difficulty_floor", 2) or 1)
        p.extended = "exam"
        p.timed = True
        p.notes.append("Exam mode: HSC-standard questions across the course, a countdown for the session, and more "
                       "extended responses.")
    p.envelopes = _envelopes(p.target, shares, p.counts)
    return p
