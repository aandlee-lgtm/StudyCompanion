"""Assessment package: marking, feedback, submission and 'why did I lose the mark?'.

Ownership (v2): core.py (submission, attempts, scheduling hooks), why.py (dispatcher),
maths.py (deterministic marking), written.py (shared written flow), english.py, legal.py."""
from app.services.assessment.common import MARKS_EXPECTATION, NO_OFFICIAL, VERBS, plan_and_outcome, subject_code  # noqa: F401
from app.services.assessment.core import apply_self_mark, submit  # noqa: F401
from app.services.assessment.legal import DISCLAIMER, evidence_for, unverified_citations  # noqa: F401
from app.services.assessment.maths import answer_display, mark_deterministic  # noqa: F401
from app.services.assessment.why import why_lost  # noqa: F401
from app.services.assessment.written import mark_written, written_ctx  # noqa: F401
