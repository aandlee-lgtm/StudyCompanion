from datetime import timedelta

from sqlalchemy import select

from app.models import QuestionExposure, RevisionQueue
from app.services import assessment, clock, mastery, sessions
from tests.conftest import TUESDAY, plan_item


def _maths_q(db, code="1A"):
    from app.models import Question

    item = plan_item(db, code)
    return db.execute(select(Question).where(Question.plan_item_id == item.id)).scalars().first()


def test_intervals_by_quality():
    assert mastery.quality(1.0, "very_confident", None, False)[0] == "strong"
    assert mastery.quality(0.7, "confident", None, False)[0] == "adequate"
    assert mastery.quality(0.4, None, None, False)[0] == "weak"
    assert mastery.quality(0.0, None, None, False)[0] == "very_weak"
    assert mastery.quality(0.0, None, None, True)[0] == "very_weak"  # skipped
    assert 56 <= mastery.interval_days("strong", None) <= 70
    assert 28 <= mastery.interval_days("adequate", None) <= 42
    assert 14 <= mastery.interval_days("weak", None) <= 21
    assert mastery.interval_days("very_weak", None) == 7
    assert mastery.interval_days("strong", 60) == 70  # repeated success moves to the long end


def test_lucky_guess_is_not_mastery():
    bucket, evidence = mastery.quality(1.0, "guess", None, False)
    assert bucket != "strong" and evidence <= 0.5


def test_careless_error_with_high_confidence_treated_differently():
    # v2 (adaptive-05): a slip is treated as a slip only when it is corroborated (strong prior mastery
    # on the skill plus a slip pattern / correct method); otherwise a very confident wrong answer is a
    # misconception, never stronger evidence than an unsure one.
    strong_prior = {"prior_mastery": 0.85, "prior_attempts": 5}
    slip = mastery.quality(0.0, "very_confident", "sign", False, slip_evidence=True, **strong_prior)
    misunderstanding = mastery.quality(0.0, "very_confident", "conceptual", False, **strong_prior)
    assert slip[0] == "adequate" and slip[1] <= 0.6 and misunderstanding[0] == "very_weak"
    assert mastery.assess(0.0, "very_confident", "sign", False).kind == "misconception"  # not corroborated


def test_exposure_and_schedule_recorded(db):
    q = _maths_q(db)
    a = assessment.submit(db, q, q.answer["value"] if q.answer["type"] != "set" else ",".join(q.answer["values"]), confidence="very_confident")
    db.commit()
    e = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == q.id)).scalar_one()
    assert e.attempts == 1 and e.score_history == [1.0]
    assert 56 <= (e.next_revision_date - TUESDAY).days <= 70
    # v2 (adaptive-08): the current LEARNING item is not 'recycled' (it is in daily practice anyway)
    assert db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == q.plan_item_id)).scalars().first() is None
    # strong answers on a LEARNED skill schedule a deliberate two-month recycle of the concept
    from app.models.common import LEARNED

    item = plan_item(db, "1A")
    item.status = LEARNED
    clock.set_today(TUESDAY + timedelta(days=70))
    assessment.submit(db, q, q.answer["value"] if q.answer["type"] != "set" else ",".join(q.answer["values"]), confidence="very_confident")
    db.commit()
    r = db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == q.plan_item_id, RevisionQueue.kind == "recycle")).scalars().first()
    assert r and 55 <= (r.due_date - (TUESDAY + timedelta(days=70))).days <= 65


def test_weak_answer_schedules_earlier_revision_with_different_question(db):
    q = _maths_q(db)
    assessment.submit(db, q, "987654", confidence="confident")
    db.commit()
    e = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == q.id)).scalar_one()
    assert (e.next_revision_date - TUESDAY).days == 7
    r = db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == q.plan_item_id, RevisionQueue.status == "open")).scalars().first()
    assert r and (r.due_date - TUESDAY).days <= 2
    # in a few days the skill is revised, but the identical question is not yet repeated
    clock.set_today(TUESDAY + timedelta(days=3))
    s = sessions.get_or_create_today(db)
    ids = [sq.question_id for sq in s.questions]
    assert q.id not in ids
    assert any(db.get(type(q), i).plan_item_id == q.plan_item_id for i in ids)


def test_no_exact_repeat_on_consecutive_days(db):
    from app.services import legal_plan  # v2: Legal is served only from started sub-areas; start them all
    from tests.conftest import answer_correctly

    legal_plan.apply_started(db, [i.id for i in legal_plan.legal_items(db) if legal_plan.is_sub_area(i)])
    db.commit()
    seen = set()
    for d in (0, 1, 2):
        clock.set_today(TUESDAY + timedelta(days=d))
        s = sessions.get_or_create_today(db)
        ids = {sq.question_id for sq in s.questions}
        assert not ids & seen
        seen |= ids
        answer_correctly(db, s)
