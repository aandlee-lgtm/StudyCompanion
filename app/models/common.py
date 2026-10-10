from __future__ import annotations

from datetime import datetime


def utcnow() -> datetime:
    """Timestamp for database rows. Despite the historical name this is the student's LOCAL
    wall-clock time (see app.services.clock.local_now), so that dates shown and compared with
    the study day (Australia/Sydney by default) agree near midnight."""
    from app.services.clock import local_now

    return local_now()


# Learning-plan statuses
LOCKED, LEARNING, LEARNED, REVISION = "LOCKED", "LEARNING", "LEARNED", "REVISION"
PLAN_STATUSES = (LOCKED, LEARNING, LEARNED, REVISION)

# Relevance classifications for historical questions
DIRECT, PARTIAL, ADAPTABLE, REJECT = "DIRECT", "PARTIAL", "ADAPTABLE", "REJECT"
RELEVANCE = (DIRECT, PARTIAL, ADAPTABLE, REJECT)

# Question origin labels shown to the student
ORIGIN_HISTORICAL = "HISTORICAL"  # genuine NESA HSC question
ORIGIN_SAMPLE = "NESA_SAMPLE"  # official NESA sample/specimen material
ORIGIN_TRIAL = "TRIAL"  # TRIAL / NON-NESA
ORIGIN_GENERATED = "GENERATED"
ORIGIN_ADAPTED = "ADAPTED"  # ADAPTED FROM HISTORICAL QUESTION
ORIGINS = (ORIGIN_HISTORICAL, ORIGIN_SAMPLE, ORIGIN_TRIAL, ORIGIN_GENERATED, ORIGIN_ADAPTED)

ORIGIN_LABELS = {
    ORIGIN_HISTORICAL: "NESA HSC",
    ORIGIN_SAMPLE: "NESA sample material",
    ORIGIN_TRIAL: "TRIAL / NON-NESA",
    ORIGIN_GENERATED: "GENERATED",
    ORIGIN_ADAPTED: "ADAPTED FROM HISTORICAL QUESTION",
}

APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED = "pending", "approved", "rejected"

SUBJECT_MATHS, SUBJECT_ENGLISH, SUBJECT_LEGAL = "MATHS", "ENGLISH", "LEGAL"
SUBJECTS = (SUBJECT_MATHS, SUBJECT_ENGLISH, SUBJECT_LEGAL)
DAILY_COUNTS = {SUBJECT_MATHS: 5, SUBJECT_ENGLISH: 3, SUBJECT_LEGAL: 3}
