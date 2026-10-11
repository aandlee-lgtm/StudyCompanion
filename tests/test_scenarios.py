"""Quality-control scenarios A–F (section 51)."""
from datetime import timedelta

from sqlalchemy import select

from app.ai import factory
from app.models import LearningPlanItem, LegalEvidence, Question, RevisionQueue
from app.selection.context import build_context
from app.selection.engine import build_daily_selection, maths_difficulty_quota
from app.services import assessment, clock, plan, sessions
from app.services import settings as st
from tests.conftest import TUESDAY, answer_correctly, plan_item
from tests.fakes import FakeProvider, marking_json


def test_A_new_chapter_mostly_current_no_future(db):
    plan.start_from(db, plan_item(db, "2A").id)
    db.commit()
    sess = sessions.get_or_create_today(db)
    maths = [sq for sq in sess.questions if sq.subject_code == "MATHS"]
    items = [db.get(LearningPlanItem, sq.question.plan_item_id) for sq in maths]
    assert sum(1 for i in items if i.code == "2A") >= 2  # most of the day is the new chapter
    assert all(i.status != "LOCKED" for i in items)
    assert not any(i.chapter == 2 and i.code > "2A" for i in items)  # no future subtopics
    assert any(i.code != "2A" for i in items)  # controlled older revision retained


def test_B_wrong_maths_answer_gets_full_teaching_feedback(db):
    item = plan_item(db, "1A")
    q = db.execute(select(Question).where(Question.plan_item_id == item.id, Question.marks >= 2)).scalars().first()
    a = assessment.submit(db, q, "424242", working="I guessed", confidence="very_confident")
    db.commit()
    p = a.feedback.payload
    assert a.mark_awarded == 0
    for key in ("student_answer", "correct_answer", "worked_solution", "divergence", "concept", "technique", "outcome", "revision"):
        assert p.get(key), key
    assert p["error_category"]
    r = db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == item.id, RevisionQueue.status == "open")).scalars().first()
    assert r is not None and (r.due_date - TUESDAY).days <= 2  # earlier revision
    assert "worked solution" in assessment.why_lost(db, a).lower() or "concept" in assessment.why_lost(db, a).lower()


def test_C_superficial_english_response(db):
    q = db.execute(select(Question).where(Question.category == "unseen", Question.marks == 4)).scalars().first()
    a = assessment.submit(db, q, "The writer uses a metaphor. It is about memory.")
    db.commit()
    p = a.feedback.payload
    assert 0 < a.mark_possible and a.mark_awarded <= 2  # appropriate partial (or low) mark
    assert p["model_answer"]  # Band 6 model response for this question
    assert p["comparison"]  # comparison with the student's response
    assert "Offline estimate" in p["label"]  # honest labelling without AI
    why = assessment.why_lost(db, a)
    assert "4-mark" in why and "Analyse" in why
    # with an AI provider the full feedback structure is shown
    factory.set_test_provider(FakeProvider(default=__import__("json").loads(marking_json(1.5, 4))))
    a2 = assessment.submit(db, q, "The writer uses a metaphor. It is about memory.")
    r = a2.feedback.payload["result"]
    assert r["comparison"] and r["model_answer"] and r["improved_answer"]
    assert "technique identification without analysis" in a2.feedback.error_categories


def test_D_outdated_legislation_flagged_with_verified_evidence(db):
    ev = db.execute(select(LegalEvidence).where(LegalEvidence.title.like("Bail Act 2013%"))).scalar_one()
    ev.last_verified_date = TUESDAY
    q = db.execute(select(Question).where(Question.question_text.like("%bail laws%"))).scalar_one()
    reply = marking_json(1.5, 4, corrections=["The Bail Act 1978 (NSW) was replaced by the Bail Act 2013 (NSW)."],
                         evidence_suggestions=["Bail Act 2013 (NSW)"], model_answer="Under the Bail Act 2013 (NSW) ... Smith v Jones shows ...",
                         errors=[{"category": "outdated legislation", "description": "Relies on the repealed Bail Act 1978"}])
    fake = FakeProvider(default=__import__("json").loads(reply))
    factory.set_test_provider(fake)
    a = assessment.submit(db, q, "Under the Bail Act 1978 (NSW) there is a presumption in favour of bail, so the law is effective.")
    db.commit()
    p = a.feedback.payload
    assert "outdated legislation" in a.feedback.error_categories
    assert p["result"]["corrections"]
    assert p["facts_checked"] == TUESDAY.isoformat()  # 'Current information checked: [date]'
    assert "Smith v Jones" in p["unverified_references"]  # invented authority is flagged, not trusted
    assert "Bail Act 2013 (NSW)" not in p["unverified_references"]
    assert "LEGAL EVIDENCE BANK (verification status per item" in fake.prompts[0] and "Bail Act 2013" in fake.prompts[0]  # v2 header (legal-13)


def test_E_consistent_success_raises_difficulty(db):
    start_ctx = build_context(db, TUESDAY)
    start_quota, start_target = maths_difficulty_quota(start_ctx), start_ctx.target_difficulty("MATHS")
    day = TUESDAY
    for _ in range(15):
        clock.set_today(day)
        if sessions.study_day(db, day):
            s = sessions.get_or_create_today(db)
            answer_correctly(db, s, 1.0, "very_confident")
        day += timedelta(days=1)
    ctx = build_context(db, day)
    assert ctx.target_difficulty("MATHS") >= start_target + 0.3
    q = maths_difficulty_quota(ctx)
    assert q[3] > start_quota[3] or q[1] < start_quota[1]


def test_F_struggling_adapts_down_but_keeps_hsc_standard(db):
    day = TUESDAY
    for _ in range(10):
        clock.set_today(day)
        if sessions.study_day(db, day):
            s = sessions.get_or_create_today(db)
            answer_correctly(db, s, 0.0, "unsure")
        day += timedelta(days=1)
    ctx = build_context(db, day)
    assert ctx.target_difficulty("MATHS") < 1.6
    q = maths_difficulty_quota(ctx)
    assert q[1] >= 3 and q[2] >= 2  # more foundation, HSC-standard work retained
