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
})
DEFAULTS.update({  # maths
})
DEFAULTS.update({  # english
})
DEFAULTS.update({  # legal
})
DEFAULTS.update({  # adaptive
})
DEFAULTS.update({  # ingestion
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
