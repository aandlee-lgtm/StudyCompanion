"""Shared helpers and constants for assessment (all subjects)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import LearningPlanItem, Question, Subject, SyllabusOutcome

NO_OFFICIAL = "AI-estimated mark based on NESA syllabus/performance criteria."

ENGLISH_ERRORS = {"insufficient textual evidence", "technique identification without analysis", "weak thesis", "descriptive response",
                  "poor comparison", "limited evaluation", "imprecise expression"}
LEGAL_ERRORS = {"missing authority", "outdated legislation", "weak judgement", "description instead of evaluation",
                "insufficient contemporary evidence", "poor use of cases", "failure to address directive verb"}
MARKS_EXPECTATION = {
    1: "one accurate point",
    2: "one clear, accurate point supported by a piece of evidence and briefly explained",
    3: "a clear point with apt evidence AND an explanation of its effect or significance (or two briefer points)",
    4: "two developed points, each linking evidence to a technique or concept and explaining how it shapes meaning or answers the question",
    5: "a sustained, coherent answer: 2–3 developed points, integrated evidence and an explicit judgement or comparison",
    6: "a structured mini-essay: a clear thesis, 3 developed points with integrated evidence, and sophisticated analysis of form and meaning",
}
VERBS = {
    "identify": "recognise and name", "explain": "relate cause and effect; make relationships evident", "analyse": "draw out how parts relate and what they imply",
    "evaluate": "make a judgement based on criteria", "assess": "make a judgement of value or effectiveness", "compare": "show similarities AND differences",
    "discuss": "provide points for and/or against", "compose": "create a purposeful text",
}



def subject_code(db: Session, q: Question) -> str:
    return db.get(Subject, q.subject_id).code


def plan_and_outcome(db: Session, q: Question) -> tuple[LearningPlanItem | None, str]:
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    outcome = db.get(SyllabusOutcome, q.syllabus_outcome_id) if q.syllabus_outcome_id else None
    topic = item.topic.name if item and item.topic else ""
    out = f"{topic} — {outcome.code}" if outcome else topic
    return item, out

