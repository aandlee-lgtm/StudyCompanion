import pytest
from sqlalchemy import select

from app.ai import factory
from app.ai.base import AIError, extract_json
from app.ai.schemas import MarkingResult
from app.models import Attempt, AttemptFeedback, Question
from app.services import assessment
from tests.fakes import FakeProvider, marking_json


def test_marking_result_rejects_impossible_mark():
    with pytest.raises(Exception):
        MarkingResult.model_validate({"mark_awarded": 5, "mark_possible": 4})


def test_extract_json_handles_fences():
    assert extract_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_malformed_output_retried_then_rejected():
    p = FakeProvider(replies=["not json at all", '{"mark_awarded": "lots"}'])
    with pytest.raises(AIError):
        p.mark_response({"subject": "ENGLISH", "subject_name": "English Advanced", "marks": 4, "question": "Q", "response": "R"})
    assert len(p.prompts) == 2 and "previous reply was invalid" in p.prompts[1]


def test_retry_recovers_from_one_bad_reply():
    p = FakeProvider(replies=["{broken", marking_json(3, 4)])
    r = p.mark_response({"subject": "ENGLISH", "subject_name": "English Advanced", "marks": 4, "question": "Q", "response": "R"})
    assert r.mark_awarded == 3


def _english_q(db, marks=4):
    return db.execute(select(Question).where(Question.category == "unseen", Question.marks == marks)).scalars().first()


def test_malformed_ai_output_never_corrupts_database(db):
    q = _english_q(db)
    factory.set_test_provider(FakeProvider(replies=["garbage", "more garbage"]))
    a = assessment.submit(db, q, "The metaphor shows memory.")
    db.commit()
    fb = db.execute(select(AttemptFeedback).where(AttemptFeedback.attempt_id == a.id)).scalar_one()
    assert fb.payload["method"] == "offline_estimate"
    assert "AI marking was unavailable" in fb.payload["note"]
    assert 0 <= a.mark_awarded <= a.mark_possible


def test_structured_prompt_contains_required_context(db):
    q = _english_q(db)
    p = FakeProvider(default=__import__("json").loads(marking_json(2, 4)))
    factory.set_test_provider(p)
    assessment.submit(db, q, "My answer")
    prompt = p.prompts[0]
    for needle in ("MARKS AVAILABLE: 4", "DIRECTIVE VERB: Analyse", "QUESTION:", "STUDENT RESPONSE:", "STIMULUS", "PERFORMANCE BANDS", "JSON"):
        assert needle in prompt
    assert "APP-AUTHORED MARKING CRITERIA (not official NESA" in prompt


def test_ai_mark_is_labelled_estimate_not_official(db):
    q = _english_q(db)
    factory.set_test_provider(FakeProvider(default=__import__("json").loads(marking_json(2, 4))))
    a = assessment.submit(db, q, "My answer")
    assert a.feedback.payload["label"] == assessment.NO_OFFICIAL
    assert a.mark_awarded == 2


def test_ai_mark_clamped_to_question_marks(db):
    q = _english_q(db, marks=2)
    factory.set_test_provider(FakeProvider(default=__import__("json").loads(marking_json(4, 4))))
    a = assessment.submit(db, q, "My answer")
    assert a.mark_awarded == 2 and a.mark_possible == 2
