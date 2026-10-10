"""English Advanced specifics for written marking (offline marking, feedback extras,
'why did I lose the mark?')."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.schemas import MarkingResult
from app.models import Question


def post_process(db: Session, q: Question, ctx: dict, result: MarkingResult, payload: dict, method: str) -> None:
    """Add English-only fields to the feedback payload (called by written.mark_written)."""
    return None


def why_lost(q: Question, p: dict, attempt) -> str | None:
    """English-specific offline explanation; None falls back to the generic written explainer."""
    return None
