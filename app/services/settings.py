"""Typed access to the ``settings`` table, with documented defaults.

All tunable educational parameters (selection weights, mixes, intervals) live here so they
can be changed from the Settings page without touching code."""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting

DEFAULTS: dict[str, Any] = {
    "setup_complete": False,
    "student_name": "Student",
    "hsc_year": 2027,
    "timezone": "Australia/Sydney",
    "target_minutes": 90,
    "budget_min_minutes": 80,
    "budget_max_minutes": 95,
    "weekdays": [0, 1, 2, 3, 4],  # Monday=0
    # normal | holiday | exam | light ; "auto" uses holiday_ranges to switch to holiday
    "mode": "auto",
    "holiday_ranges": [],  # [{"start": "2026-12-19", "end": "2027-01-26", "label": "Summer holidays"}]
    "holiday_target_minutes": 75,
    "light_target_minutes": 45,
    # Year timeline: used to move gradually from learning companion to exam preparation.
    "year12_start_date": None,  # set by the first-run wizard
    "hsc_start_date": "2027-10-11",  # ESTIMATE - edit once NESA publishes the 2027 timetable
    # Selection engine weights (section 10). Normalised at run time.
    "selection_weights": {
        "current": 0.30,
        "weakness": 0.20,
        "spaced": 0.15,
        "coverage": 0.10,
        "difficulty": 0.10,
        "novelty": 0.10,
        "source": 0.05,
    },
    # Maths: share of questions by learning state (section 5A)
    "maths_mix": {"learning": 0.55, "recent": 0.25, "older": 0.20},
    # Maths difficulty starting ratio out of 5 (section 5B)
    "maths_difficulty_start": {"foundation": 2, "hsc": 2, "challenge": 1},
    "english_unseen_share": 0.8,
    "enrichment_enabled": False,
    "difficulty_behaviour": "adaptive",  # adaptive | steady | stretch | consolidate
    "revision_intensity": "normal",  # light | normal | intense
    "feedback_depth": "full",  # full | concise
    "source_preferences": {"allow_trial": True, "allow_generated": True, "allow_adapted": True},
    "auto_approve_direct_confidence": 0.85,
    "ask_confidence": True,
    "show_why_these_questions": True,
    "ai_provider_override": None,  # None => from environment
    "ai_model_override": None,
}

# ---- v2 package settings: each package adds its keys ONLY inside its own block (keeps merges clean) ----
DEFAULTS.update({  # selection
    # Share of the day's minutes each subject aims for (per-subject time envelopes, +/- 15%).
    "selection_subject_shares": {"MATHS": 0.40, "ENGLISH": 0.33, "LEGAL": 0.27},
    # Mode profiles (section 15). Counts may drop below 5/3/3 only in these special modes.
    "light_day_counts": {"MATHS": 3, "ENGLISH": 2, "LEGAL": 2},
    "exam_difficulty_floor": 2,  # exam mode: no foundation-level Maths
    # A reading passage, once read, is not served again as an unseen text for this many days.
    "unseen_passage_cooldown_days": 70,
    # Legal extended responses per 4 weeks, by progress through the year ([progress, count] points).
    "legal_extended_per_month": [[0.0, 1], [0.15, 2], [0.4, 3], [0.6, 4], [0.75, 6], [1.0, 8]],
    "legal_extended_exam_per_month": 8,
    "legal_extended_min_sessions": 8,  # no extended response in the first sessions of the year
    # Legal weekly format mix (per 15 Legal questions) at the start and end of the year.
    "legal_weekly_formats": {"start": {"mcq": 4, "short_answer": 8, "stimulus": 2},
                             "end": {"mcq": 3, "short_answer": 6, "stimulus": 4}},
    # Active-time timer: stop counting after this many minutes without activity.
    "timer_idle_minutes": 10,
    # Missed days are only counted from this date (stamped the first time the app plans a day).
    "setup_completed_on": None,
    # A day counts towards the streak at this share of questions answered, or this many active minutes.
    "streak_min_fraction": 0.8,
    "streak_min_minutes": 60,
    # An earlier Maths topic not practised for this many days gets a coverage slot, however strong.
    "selection_coverage_days": 18,
    # Phases of the year as proportions of the span Year 12 start -> HSC start (selection-22).
    "selection_phase_thresholds": {"consolidation": 0.2, "trials": 0.75, "final": 0.92},
})
DEFAULTS.update({  # maths
})
DEFAULTS.update({  # english
})
DEFAULTS.update({  # legal
    "legal_max_options": 2,  # Legal Studies option topics studied at once (legal-11)
    "legal_recheck_days_legislation": 90,  # evidence re-check intervals by item type (legal-03/19)
    "legal_recheck_days_media": 180,
    "legal_recheck_days_other": 365,
    "legal_contemporary_years": 5,  # evidence newer than this counts as contemporary (legal-04)
    "legal_syllabus_confirmed": False,  # the student has confirmed the sub-areas against the NESA syllabus (legal-09)
    "legal_topics_chosen": False,  # the student has answered "Which Legal topics have you started?" (owner request)
})
DEFAULTS.update({  # adaptive
})
DEFAULTS.update({  # ingestion
    "auto_approve_imports": True,  # AI-mapped imports that pass every validation gate may be approved without review
    "admin_mode": False,  # show answers, guidelines and model responses in the library and review screens before an attempt
    "review_page_size": 25,
})
DEFAULTS.update({  # followup
    # "Ask about this feedback": maximum questions (turns) in one attempt's thread.
    "followup_max_turns": 20,
})
DEFAULTS.update({  # platform
    "ai_effort": "high",  # Claude output_config.effort for marking
    "setup_completed_at": None,
    "seed_signature": None,
})

# Spaced repetition intervals in days (section 12): (min, max)
REVIEW_INTERVALS = {
    "strong": (56, 70),
    "adequate": (28, 42),
    "weak": (14, 21),
    "very_weak": (7, 7),
}


def get(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return copy.deepcopy(DEFAULTS.get(key))
    return row.value


def set_(db: Session, key: str, value: Any) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.flush()


def all_settings(db: Session) -> dict[str, Any]:
    out = copy.deepcopy(DEFAULTS)
    for row in db.query(Setting).all():
        out[row.key] = row.value
    return out
