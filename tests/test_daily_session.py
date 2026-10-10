from datetime import timedelta

from sqlalchemy import select

from app.models import DailySession, LearningPlanItem, Question, QuestionMapping
from app.models.common import APPROVAL_APPROVED, REJECT
from app.selection.context import build_context
from app.selection.engine import build_daily_selection, subject_code
from app.services import clock, plan, question_bank, sessions
from tests.conftest import TUESDAY, answer_correctly, plan_item, subject_of


def test_daily_question_counts(db):
    sess = sessions.get_or_create_today(db)
    db.commit()
    counts = {}
    for sq in sess.questions:
        counts[sq.subject_code] = counts.get(sq.subject_code, 0) + 1
    assert counts == {"MATHS": 5, "ENGLISH": 3, "LEGAL": 3}


def test_no_locked_topic_appears(db):
    for d in range(10):
        clock.set_today(TUESDAY + timedelta(days=d))
        if not sessions.study_day(db, clock.today()):
            continue
        sess = sessions.get_or_create_today(db)
        for sq in sess.questions:
            item = db.get(LearningPlanItem, sq.question.plan_item_id)
            assert item.status != "LOCKED", f"{item.code} is LOCKED but was served"
            assert item.active
        answer_correctly(db, sess)


def test_no_extension_question_appears(db):
    item = plan_item(db, "1A")
    src = question_bank.template_source(db)
    ext = question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text="Prove by mathematical induction that 3^n - 1 is even.",
                                        marks=3, difficulty=2, topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "0"},
                                        mapping_reason="test")
    ext.is_extension = True
    db.commit()
    ctx = build_context(db, TUESDAY)
    sel = build_daily_selection(db, ctx)
    assert ext.id not in {s.question.id for s in sel.items}


def test_reject_questions_never_selected(db):
    item = plan_item(db, "1A")
    rejected = db.execute(select(Question).where(Question.plan_item_id == item.id)).scalars().all()
    for q in rejected:
        q.relevance_status = REJECT  # even if (wrongly) still approved
    db.commit()
    ctx = build_context(db, TUESDAY)
    sel = build_daily_selection(db, ctx)
    assert not {q.id for q in rejected} & {s.question.id for s in sel.items}


def test_session_persists_after_refresh(db, client):
    r1 = client.get("/today", follow_redirects=False)
    r2 = client.get("/today", follow_redirects=False)
    assert r1.headers["location"] == r2.headers["location"]
    sid = int(r1.headers["location"].rsplit("/", 1)[1])
    db.expire_all()
    s = db.get(DailySession, sid)
    ids1 = [sq.question_id for sq in s.questions]
    client.get(f"/session/{sid}")
    client.get("/today")
    db.expire_all()
    assert [sq.question_id for sq in db.get(DailySession, sid).questions] == ids1
    assert db.execute(select(DailySession).where(DailySession.session_date == TUESDAY)).scalars().all().__len__() == 1


def test_draft_autosave_survives_refresh(db, client):
    loc = client.get("/today", follow_redirects=False).headers["location"]
    sid = int(loc.rsplit("/", 1)[1])
    db.expire_all()
    sq = next(q for q in db.get(DailySession, sid).questions if q.subject_code == "ENGLISH")
    client.post(f"/session/{sid}/q/{sq.position}/draft", data={"text": "My half-written answer", "time_seconds": 45})
    page = client.get(f"/session/{sid}/q/{sq.position}")
    assert "My half-written answer" in page.text


def test_legal_option_unavailable_until_activated(db):
    fam = plan_item(db, "LS-OPT-FAMILY")
    option_q = db.execute(select(Question).where(Question.plan_item_id == fam.id)).scalars().all()
    assert option_q
    # make option questions maximally attractive: lock everything else in Legal
    for it in plan.items(db, "LEGAL"):
        if it.id != fam.id:
            it.status = "LOCKED"
    db.commit()
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    assert not [s for s in sel.items if s.question.plan_item_id == fam.id]
    plan.set_option_active(db, fam.id, True)
    db.commit()
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    assert [s for s in sel.items if s.question.plan_item_id == fam.id]


def test_time_budget(db):
    ctx = build_context(db, TUESDAY)
    sel = build_daily_selection(db, ctx)
    from app.selection.engine import budget_bounds

    _, lo, hi = budget_bounds(ctx)
    assert sel.expected_minutes <= hi + 0.01
    assert sel.expected_minutes >= lo or any("shorter than" in n for n in sel.notes)


def test_time_budget_replaces_long_questions(db):
    """A deliberately over-long day is shortened by swapping, keeping 5/3/3."""
    from app.selection import engine

    ctx = build_context(db, TUESDAY)
    sel = build_daily_selection(db, ctx)
    for s in sel.items:  # make the chosen questions very long
        s.question.estimated_minutes = 20
    db.flush()
    groups = {c: engine.candidates(db, ctx, c) for c in ("MATHS", "ENGLISH", "LEGAL")}
    pools = {c: engine._flatten(groups[c], 1) for c in groups}
    before = engine.expected_minutes(sel.items)
    fixed, _ = engine.fit_budget(ctx, sel.items, pools)
    after = engine.expected_minutes(fixed)
    assert after < before
    counts = {}
    for s in fixed:
        counts[subject_code(s.question)] = counts.get(subject_code(s.question), 0) + 1
    assert counts == {"MATHS": 5, "ENGLISH": 3, "LEGAL": 3}
    db.rollback()


def test_source_attribution_persists(db, client):
    q = db.execute(select(Question).where(Question.approved.is_(True))).scalars().first()
    page = client.get(f"/questions/{q.id}")
    assert q.source.title in page.text
    assert db.execute(select(QuestionMapping).where(QuestionMapping.question_id == q.id)).scalars().first() is not None
    loc = client.get("/today", follow_redirects=False).headers["location"]
    sid = int(loc.rsplit("/", 1)[1])
    qp = client.get(f"/session/{sid}/q/1")
    assert "Source:" in qp.text and "2027 mapping:" in qp.text and "Relevance:" in qp.text


def test_english_uses_one_unseen_passage(db):
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    unseen = [s for s in sel.items if s.question.category == "unseen"]
    assert len(unseen) >= 2
    assert len({s.question.stimulus_id for s in unseen}) == 1


def test_enrichment_not_served_unless_enabled(db):
    from app.services import settings as st

    item = plan_item(db, "3D")
    src = question_bank.template_source(db)
    question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text="Challenge: prove the fundamental theorem of calculus for a continuous f.",
                                  marks=3, difficulty=3, topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "0"}, mapping_reason="t")
    item.status = "LEARNING"
    db.commit()
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    assert not [s for s in sel.items if s.question.plan_item_id == item.id]
    st.set_(db, "enrichment_enabled", True)
    db.commit()
    from app.selection.context import build_context as bc
    assert bc(db, TUESDAY).settings["enrichment_enabled"] is True
