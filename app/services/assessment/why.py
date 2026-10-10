"""'Why did I lose the mark?' dispatcher."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.models import Attempt, Subject
from app.services import settings as st
from app.services.assessment import english, legal
from app.services.assessment.common import subject_code
from app.services.assessment.maths import why_lost_maths
from app.services.assessment.written import why_lost_written

log = logging.getLogger(__name__)


def why_lost(db: Session, attempt: Attempt) -> str:
    fb = attempt.feedback
    if fb.why_lost:
        return fb.why_lost
    q = attempt.question
    p = fb.payload
    if attempt.mark_awarded >= attempt.mark_possible:
        text = "You received full marks for this question — nothing was lost."
    elif p.get("kind") in ("maths", "mcq"):
        text = why_lost_maths(q, p)
    elif p.get("kind") == "skipped":
        text = "The question was skipped, so no marks could be awarded. Skipping is recorded honestly so the app schedules it for revision."
    else:
        text = None
        provider = get_provider(st.all_settings(db))
        if provider.generative:
            try:
                text = provider.generate_feedback({
                    "subject_name": db.get(Subject, q.subject_id).name, "marks": q.marks, "directive_verb": q.directive_verb,
                    "question": q.question_text, "mark": attempt.mark_awarded, "response": attempt.response_text, "feedback": p.get("result", {}),
                }).explanation
            except (AIError, AIUnavailable) as exc:
                log.warning("why_lost AI failed: %s", exc)
        if text is None:
            code = subject_code(db, q)
            text = (legal.why_lost(q, p, attempt) if code == "LEGAL" else english.why_lost(q, p, attempt))
        text = text or why_lost_written(q, p, attempt)
    fb.why_lost = text
    db.flush()
    return text
