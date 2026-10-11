"""Phases of the year (selection-22, spec 57: "becomes more exam-like as the HSC approaches").

The phase comes from progress between the Year 12 start date and the HSC start date in Settings
(both owner-editable; the thresholds below are proportions of that span, not invented calendar
dates). Each phase nudges the day towards exam conditions:

* companion      — the first weeks (about Term 4): follows the class closely.
* consolidation  — about Terms 1–2: multi-part, exam-style questions are preferred a little.
* trials         — about Term 3: exam-style questions preferred more; the last study day of each
                   week is a timed session.
* final          — the last weeks: every session is timed and exam-style questions lead.

Legal extended responses already rise with progress (``legal_extended_per_month``)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Question
from app.models.common import ORIGIN_HISTORICAL, ORIGIN_SAMPLE, ORIGIN_TRIAL

_PARTS = re.compile(r"\(\s*a\s*\).*\(\s*b\s*\)", re.S | re.I)


@dataclass(frozen=True)
class Phase:
    name: str
    label: str
    exam_style_bonus: float  # added to a Maths question's stage-2 score
    timed: str  # "" | "weekly" | "daily"
    note: str


PHASES = {
    "companion": Phase("companion", "Learning companion", 0.0, "",
                       "Learning-companion phase: questions follow what you are learning in class."),
    "consolidation": Phase("consolidation", "Consolidation", 0.12, "",
                           "Consolidation phase: multi-part, exam-style questions are preferred where they exist."),
    "trials": Phase("trials", "Trial preparation", 0.25, "weekly",
                    "Trial-preparation phase: exam-style questions lead, and the last study day of each week is timed."),
    "final": Phase("final", "Final preparation", 0.35, "daily",
                   "Final-preparation phase: every session is timed and exam-style questions lead."),
}
DEFAULT_THRESHOLDS = {"consolidation": 0.2, "trials": 0.75, "final": 0.92}


def phase_for(progress: float, settings: dict) -> Phase:
    t = {**DEFAULT_THRESHOLDS, **(settings.get("selection_phase_thresholds") or {})}
    if progress >= float(t["final"]):
        return PHASES["final"]
    if progress >= float(t["trials"]):
        return PHASES["trials"]
    if progress >= float(t["consolidation"]):
        return PHASES["consolidation"]
    return PHASES["companion"]


def is_multipart(q: Question) -> bool:
    sol = q.solution if isinstance(q.solution, dict) else {}
    parts = sol.get("parts")
    if isinstance(parts, list) and len(parts) >= 2:
        return True
    return bool(_PARTS.search(q.question_text or ""))


def is_exam_style(q: Question) -> bool:
    """Multi-part, flagged exam-style, or real exam material (sample / past HSC / trial)."""
    sol = q.solution if isinstance(q.solution, dict) else {}
    if sol.get("exam_style") or sol.get("unfamiliar_context"):
        return True
    if q.historical_or_generated in (ORIGIN_SAMPLE, ORIGIN_HISTORICAL, ORIGIN_TRIAL):
        return True
    return is_multipart(q)


def timed_today(phase: Phase, weekday: int, study_days: list[int]) -> bool:
    if phase.timed == "daily":
        return True
    if phase.timed == "weekly":
        return weekday == max(study_days or [4])
    return False
