"""Real-time swap of an unanswered question (owner request 2026-10-11, package swap).

Pins: replacement constraints (same subject, similar minutes and marks, plan item not LOCKED, no
exact repeat the repeat rules forbid, never the same plan item for "not learnt", Maths one question
per form), logging, plan-item locking (explicit only), no attempt/skip/mastery/exposure side
effects, English reading sets swapping as a whole, the no-replacement case, refusals once answered,
the JSON endpoint, the no-JS form fallback and the cross-site (CSRF) rule."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import (
    Attempt,
    DailySession,
    LearningPlanItem,
    Mastery,
    Question,
    QuestionExposure,
    RevisionQueue,
    SessionQuestion,
    SessionSwap,
    Subject,
    WorkingPhoto,
)
from app.models.common import LOCKED
from app.selection import swap as sw
from app.selection.context import build_context, form_key
from app.services import assessment, clock, sessions
from tests.conftest import TUESDAY


def _bank(db):
    from tests.sim.harness import add_v2_like_bank

    add_v2_like_bank(db)
    db.commit()


def _today(db, bank: bool = True) -> DailySession:
    if bank:
        _bank(db)
    sess = sessions.get_or_create_today(db)
    db.commit()
    return sess


def _rows(sess, code):
    return [x for x in sess.questions if x.subject_code == code]


def _row(sess, pos) -> SessionQuestion:
    return next(x for x in sess.questions if x.position == pos)


def _counts(db) -> dict:
    return {m.__name__: db.execute(select(func.count()).select_from(m)).scalar_one()
            for m in (Attempt, QuestionExposure, Mastery, RevisionQueue)}


def _statuses(db) -> dict:
    return {it.id: it.status for it in db.execute(select(LearningPlanItem)).scalars()}


def _passage_rows(sess):
    return [x for x in sess.questions if x.subject_code == "ENGLISH" and x.question.category == "unseen" and x.question.stimulus_id]


# ---------------------------------------------------------------- constraints ---
def test_not_learnt_replacement_keeps_subject_size_and_avoids_the_topic(db):
    sess = _today(db)
    sq = _rows(sess, "MATHS")[0]
    orig, pos = sq.question, sq.position
    orig_item, orig_min, orig_marks = orig.plan_item_id, orig.estimated_minutes, orig.marks
    rec = sessions.swap_question(db, sess, sq, "not_learnt")
    db.commit()
    new = _row(sess, pos)
    q = new.question
    assert rec.outcome == "replaced" and new.subject_code == "MATHS" and q.id != orig.id
    assert q.plan_item_id != orig_item  # never the same plan item when the reason is "not learnt"
    item = db.get(LearningPlanItem, q.plan_item_id)
    assert item.status != LOCKED and item.subject.code == "MATHS"
    assert abs(q.estimated_minutes - orig_min) <= max(5.0, 0.6 * orig_min)
    assert abs(q.marks - orig_marks) <= max(2, round(0.5 * orig_marks))
    others = [x.question for x in sess.questions if x.id != new.id]
    assert q.id not in {o.id for o in others}
    assert form_key(q) not in {form_key(o) for o in others if o.subject_id == q.subject_id}  # one question per form
    assert new.status == "pending" and new.score_breakdown["swap"]["replaced"] == orig.id
    assert new.reason.startswith("Swapped in")
    # nothing else moved
    assert [x.position for x in sess.questions] == list(range(1, len(sess.questions) + 1))


def test_different_never_brings_back_a_sibling_form_or_a_swapped_out_question(db):
    sess = _today(db)
    pos = _rows(sess, "MATHS")[1].position
    seen_ids, seen_forms = {_row(sess, pos).question_id}, {form_key(_row(sess, pos).question)}
    for _ in range(4):
        rec = sessions.swap_question(db, sess, _row(sess, pos), "different")
        db.commit()
        if rec.outcome != "replaced":
            break
        q = _row(sess, pos).question
        assert q.id not in seen_ids, "a question swapped out earlier today came back"
        assert form_key(q) not in seen_forms, "a template sibling (same form, new numbers) is not a different question"
        seen_ids.add(q.id)
        seen_forms.add(form_key(q))
    assert len(seen_ids) >= 3


def _only_candidates(db, sess, code, keep: set[int]) -> None:
    """Make ``keep`` the only questions of ``code`` outside the session that could be served."""
    subj = db.execute(select(Subject).where(Subject.code == code)).scalar_one()
    in_session = {x.question_id for x in sess.questions}
    for q in db.execute(select(Question).where(Question.subject_id == subj.id)).scalars():
        if q.id not in in_session and q.id not in keep:
            q.approved = False
    db.flush()


def test_an_exact_repeat_the_repeat_rules_forbid_is_never_a_replacement(db):
    sess = _today(db)
    sq = _rows(sess, "LEGAL")[0]
    unit = sw.unit_for(sess, sq)
    first = sw.find_replacement(db, unit, "different", TUESDAY)
    assert first.items
    x = first.items[0].question
    _only_candidates(db, sess, "LEGAL", {x.id})
    assert sw.find_replacement(db, unit, "different", TUESDAY).items[0].question.id == x.id  # the only candidate
    # ... but it was answered 5 days ago and its revision date is 10 days away: an exact repeat is not allowed
    db.add(QuestionExposure(question_id=x.id, first_seen=TUESDAY - timedelta(days=5), last_seen=TUESDAY - timedelta(days=5),
                            attempts=1, score_history=[0.9], mastery=0.9, interval_days=15,
                            next_revision_date=TUESDAY + timedelta(days=10)))
    db.flush()
    again = sw.find_replacement(db, unit, "different", TUESDAY)
    assert again.items == [] and "exact repeat is not allowed before its revision date" in again.why_none
    rec = sessions.swap_question(db, sess, sq, "different")
    assert rec.outcome == "removed" and x.id not in {r.question_id for r in sess.questions}


def test_a_template_sibling_with_new_numbers_is_not_a_different_question(db):
    from app.services import question_bank as qb

    sess = _today(db)
    sq = _rows(sess, "MATHS")[0]
    orig = sq.question
    orig.solution = {**(orig.solution or {}), "template_family": "swap-test-family"}
    sib = qb.create_question(db, subject_code="MATHS", source_id=orig.source_id, mapping_reason="test",
                             question_text="Sibling form with entirely different wording and the numbers 7, 11 and 13 changed.",
                             marks=orig.marks, question_type=orig.question_type, difficulty=orig.difficulty,
                             estimated_minutes=orig.estimated_minutes, topic_id=orig.topic_id, plan_item_id=orig.plan_item_id,
                             category=orig.category, historical_or_generated=orig.historical_or_generated,
                             answer={"type": "numeric", "value": "1"}, solution={"template_family": "swap-test-family"})
    _only_candidates(db, sess, "MATHS", {sib.id})
    assert form_key(sib) == form_key(orig)
    rep = sw.find_replacement(db, sw.unit_for(sess, sq), "different", TUESDAY)
    assert rep.items == [] and "same kind of question" in rep.why_none
    sib.solution = {"template_family": "another-family"}  # a genuinely different form qualifies
    db.flush()
    rep = sw.find_replacement(db, sw.unit_for(sess, sq), "different", TUESDAY)
    assert [s.question.id for s in rep.items] == [sib.id]


def test_later_swaps_do_not_bring_back_a_topic_flagged_not_learnt(db):
    sess = _today(db)
    sq = _rows(sess, "MATHS")[0]
    pos, item = sq.position, sq.question.plan_item_id
    sessions.swap_question(db, sess, sq, "not_learnt")  # no lock: the topic stays as it is in the plan
    db.commit()
    assert db.get(LearningPlanItem, item).status != LOCKED
    for _ in range(3):
        rec = sessions.swap_question(db, sess, _row(sess, pos), "different")
        db.commit()
        if rec.outcome != "replaced":
            break
        assert _row(sess, pos).question.plan_item_id != item


def test_legal_swap_keeps_the_legal_mix(db):
    sess = _today(db)
    replaced = 0
    for sq in list(_rows(sess, "LEGAL")):
        pos = sq.position
        rec = sessions.swap_question(db, sess, sq, "different")
        db.commit()
        if rec.outcome == "removed":
            continue
        replaced += 1
        from app.selection.context import legal_format

        fmts = [legal_format(x.question) for x in _rows(sess, "LEGAL")]
        stims = {x.question.stimulus_id for x in _rows(sess, "LEGAL") if x.question.stimulus_id}
        assert fmts.count("extended") <= 1 and len(stims) <= 1
        assert fmts.count("mcq") <= (2 if "extended" in fmts else 1)
        assert _row(sess, pos).subject_code == "LEGAL"
    assert replaced >= 2


# ------------------------------------------------------------------ side effects ---
def test_swap_records_no_attempt_skip_mastery_or_exposure_and_is_logged(db):
    sess = _today(db)
    before = _counts(db)
    mastery_before = {m.plan_item_id: m.mastery for m in db.execute(select(Mastery)).scalars()}
    sq = _rows(sess, "LEGAL")[0]
    orig_id, pos = sq.question_id, sq.position
    rec = sessions.swap_question(db, sess, sq, "different")
    db.commit()
    assert _counts(db) == before
    assert {m.plan_item_id: m.mastery for m in db.execute(select(Mastery)).scalars()} == mastery_before
    assert db.execute(select(QuestionExposure).where(QuestionExposure.question_id == orig_id)).scalar_one_or_none() is None
    assert all(x.status == "pending" for x in sess.questions)
    # the swapped-out question is not "served": it can come back on another day
    ctx = build_context(db, TUESDAY + timedelta(days=1))
    assert orig_id not in ctx.served
    # who / when / why / from / to
    rec = db.get(SessionSwap, rec.id)
    assert rec.session_id == sess.id and rec.actor == "student" and rec.created_at is not None
    assert rec.reason == "different" and rec.subject_code == "LEGAL" and rec.position == pos
    assert rec.from_question_ids == [orig_id] and rec.to_question_ids == [_row(sess, pos).question_id]
    assert rec.details["local_time"] and rec.message.startswith(f"Swapped Q{pos}")
    assert "Nothing was recorded" in rec.message


# ----------------------------------------------------------------- plan locking ---
def test_not_learnt_with_lock_marks_the_topic_not_taught_and_future_sessions_avoid_it(db):
    sess = _today(db)
    sq = _rows(sess, "LEGAL")[0]
    item_id = sq.question.plan_item_id
    ctl = sessions.swap_controls(db, sess)[sq.id]
    assert ctl["lock"] and ctl["lock"]["item_id"] == item_id and ctl["lock"]["default"] is True  # Legal: ticked
    rec = sessions.swap_question(db, sess, sq, "not_learnt", lock=True)
    db.commit()
    item = db.get(LearningPlanItem, item_id)
    assert item.status == LOCKED and rec.locked_plan_item_id == item_id
    assert "now marked Not taught yet" in rec.message
    assert _row(sess, rec.position).question.plan_item_id != item_id
    # the next study day avoids it
    clock.set_today(TUESDAY + timedelta(days=1))
    nxt = sessions.get_or_create_today(db)
    db.commit()
    assert nxt.id != sess.id and nxt.questions
    assert all(x.question.plan_item_id != item_id for x in nxt.questions)


def test_lock_is_never_silent_and_defaults_follow_the_subject(db):
    sess = _today(db)
    controls = sessions.swap_controls(db, sess)
    maths = _rows(sess, "MATHS")[0]
    assert controls[maths.id]["lock"]["default"] is False  # Maths subtopics: unticked
    course = [x for x in _rows(sess, "ENGLISH") if x.question.category != "unseen"]
    for x in course:
        assert controls[x.id]["lock"]["default"] is True  # English course topics: ticked
    for x in _passage_rows(sess):
        assert controls[x.id]["lock"] is None  # an unseen passage is not a topic taught first
    statuses = _statuses(db)
    sessions.swap_question(db, sess, maths, "not_learnt", lock=False)
    sessions.swap_question(db, sess, _rows(sess, "LEGAL")[0], "different", lock=True)  # lock only applies to "not learnt"
    db.commit()
    assert _statuses(db) == statuses  # no plan item changed
    assert all(r.locked_plan_item_id is None for r in db.execute(select(SessionSwap)).scalars())


# -------------------------------------------------------------- passage sets ---
def test_an_english_reading_set_swaps_as_a_whole_for_an_unread_passage(db):
    sess = _today(db)
    rows = _passage_rows(sess)
    assert len(rows) >= 2
    old_ids = [x.question_id for x in rows]
    old_stims = {s.id for s in rows[0].question.stimulus.reading_set()}
    positions = [x.position for x in rows]
    old_minutes = sw.unit_for(sess, rows[0]).minutes
    rec = sessions.swap_question(db, sess, rows[-1], "different")  # any question of the set swaps the set
    db.commit()
    assert rec.outcome == "replaced" and sorted(rec.from_question_ids) == sorted(old_ids)
    new = _passage_rows(sess)
    assert [x.position for x in new] == positions and len(new) == len(rows)
    stims = {s.id for x in new for s in x.question.stimulus.reading_set()}
    assert not stims & old_stims
    assert len({x.question.stimulus_id for x in new}) == 1  # one passage per day
    ctx = build_context(db, TUESDAY)
    assert not any(s in ctx.stimulus_last_read for s in stims)  # unread
    assert abs(sw.unit_for(sess, new[0]).minutes - old_minutes) <= max(8.0, 0.6 * old_minutes)
    assert "passage" in rec.message and sess.explanation["lines"][1].startswith("English:")
    title = new[0].question.stimulus.title
    assert title in sess.explanation["lines"][1]  # "Why these questions?" names the new text


def test_not_learnt_passage_comes_back_as_a_different_kind_of_text(db):
    sess = _today(db)
    rows = _passage_rows(sess)
    form = rows[0].question.stimulus.form
    rec = sessions.swap_question(db, sess, rows[0], "not_learnt")
    db.commit()
    assert rec.outcome == "replaced" and rec.details["from_form"] == form
    assert _passage_rows(sess)[0].question.stimulus.form != form
    assert f"({form.lower()})" in rec.message


def test_a_passage_set_with_an_answer_cannot_be_swapped(db):
    sess = _today(db)
    rows = _passage_rows(sess)
    assessment.submit(db, rows[0].question, "A detailed answer about the imagery and its effect.", sq=rows[0], time_seconds=60)
    db.commit()
    with pytest.raises(sessions.SwapRefused, match="passage"):
        sessions.swap_question(db, sess, rows[1], "different")
    assert sessions.swap_controls(db, sess)[rows[1].id]["can"] is False


# ------------------------------------------------------------ no replacement ---
def test_without_a_suitable_replacement_the_question_is_removed_and_the_reason_given(db):
    sess = _today(db, bank=False)
    legal = db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()
    in_session = {x.question_id for x in sess.questions}
    for q in db.execute(select(Question).where(Question.subject_id == legal.id)).scalars():
        if q.id not in in_session:
            q.approved = False  # nothing else exists for Legal Studies
    db.commit()
    n, minutes = len(sess.questions), sess.expected_minutes
    sq = _rows(sess, "LEGAL")[0]
    orig_id, pos, q_min = sq.question_id, sq.position, sq.question.estimated_minutes
    before = _counts(db)
    rec = sessions.swap_question(db, sess, sq, "different")
    db.commit()
    db.refresh(sess)
    assert rec.outcome == "removed" and rec.to_question_ids == [] and rec.from_question_ids == [orig_id]
    assert len(sess.questions) == n - 1 and orig_id not in {x.question_id for x in sess.questions}
    assert [x.position for x in sess.questions] == list(range(1, n))
    assert sess.expected_minutes == pytest.approx(minutes - q_min, abs=0.2)
    assert rec.message.startswith(f"Removed Q{pos}") and "no suitable replacement" in rec.message
    assert "no other Legal Studies questions" in rec.message
    assert _counts(db) == before
    assert sessions.progress(sess)["n_total"] == n - 1


def test_no_similar_length_gives_the_closest_available_reason(db):
    sess = _today(db, bank=False)
    sq = _rows(sess, "ENGLISH")
    course = [x for x in sq if x.question.category != "unseen"][0]
    eng = db.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    for q in db.execute(select(Question).where(Question.subject_id == eng.id, Question.category != "unseen")).scalars():
        if q.id != course.question_id:
            q.estimated_minutes = 40.0  # every other course task is far longer
    db.commit()
    rec = sessions.swap_question(db, sess, course, "different")
    db.commit()
    assert rec.outcome == "removed"  # a 40-minute task is not "a similar length" to an 11-minute one
    assert "no new English question takes a similar time" in rec.message and "closest left takes about 40 minutes" in rec.message
    assert rec.details["facts"]["counts"]["rules"] > 0


# -------------------------------------------------------------------- refusals ---
def test_answered_or_skipped_questions_cannot_be_swapped(db):
    sess = _today(db)
    m = _rows(sess, "MATHS")
    assessment.submit(db, m[0].question, "1", sq=m[0], time_seconds=30)
    assessment.submit(db, m[1].question, "", sq=m[1], skipped=True)
    db.commit()
    with pytest.raises(sessions.SwapRefused, match="already answered"):
        sessions.swap_question(db, sess, m[0], "different")
    with pytest.raises(sessions.SwapRefused, match="skipped"):
        sessions.swap_question(db, sess, m[1], "different")
    controls = sessions.swap_controls(db, sess)
    assert controls[m[0].id]["can"] is False and controls[m[2].id]["can"] is True
    assert db.execute(select(func.count()).select_from(SessionSwap)).scalar_one() == 0


def test_finished_session_and_pending_photo_refuse(db):
    sess = _today(db, bank=False)
    sq = _rows(sess, "MATHS")[0]
    db.add(WorkingPhoto(question_id=sq.question_id, session_question_id=sq.id, filename="x.jpg", page=1))
    db.commit()
    with pytest.raises(sessions.SwapRefused, match="photo"):
        sessions.swap_question(db, sess, sq, "different")
    sessions.close_session(db, sess)
    db.commit()
    with pytest.raises(sessions.SwapRefused, match="finished"):
        sessions.swap_question(db, sess, _rows(sess, "LEGAL")[0], "different")
    assert sessions.swap_controls(db, sess) == {}


def test_a_draft_can_be_swapped_and_is_discarded(db):
    sess = _today(db, bank=False)
    sq = _rows(sess, "LEGAL")[0]
    sessions.save_draft(db, sq, "half an answer", 120)
    db.commit()
    assert sessions.swap_controls(db, sess)[sq.id]["draft"] is True
    rec = sessions.swap_question(db, sess, sq, "different")
    db.commit()
    row = _row(sess, rec.position)
    assert rec.outcome == "replaced"
    assert row.status == "pending" and row.draft_text is None and row.time_spent_seconds == 0


# ------------------------------------------------------------------ the routes ---
def _open_today(client):
    loc = client.get("/today", follow_redirects=False).headers["location"]
    return loc, int(loc.rsplit("/", 1)[1])


def test_json_endpoint_and_no_js_form_fallback(client, db):
    loc, sid = _open_today(client)
    page = client.get(loc).text
    assert page.count("data-swap-form") >= 8 and "Swap — I haven&#39;t learnt this yet" in page
    assert "Swap — give me a different one" in page and "Swap this passage" in page
    r = client.post(f"{loc}/q/1/swap", data={"reason": "different", "back": "session"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] and j["outcome"] == "replaced" and j["positions"] == [1] and j["questions"][0]["subject"] == "MATHS"
    assert j["redirect"] == f"/session/{sid}?swapped={j['swap_id']}#swap-note"
    # plain form post (no JavaScript): redirect, then the page says what happened and lists the swap
    r = client.post(f"{loc}/q/2/swap", data={"reason": "not_learnt", "back": "session"}, follow_redirects=False)
    assert r.status_code == 303 and "swapped=" in r.headers["location"]
    page = client.get(r.headers["location"]).text
    assert 'id="swap-note"' in page and "Swaps you made" in page and "Swapped in" in page
    # from the question page: back to the same position, with the notice
    r = client.post(f"{loc}/q/3/swap", data={"reason": "different", "back": "question"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/session/{sid}/q/3?swapped=")
    assert client.get(r.headers["location"]).status_code == 200


def test_endpoint_refusals_and_bad_input(client, db):
    from app.models import Question as Q

    loc, sid = _open_today(client)
    db.expire_all()
    sq = db.execute(select(SessionQuestion).where(SessionQuestion.session_id == sid, SessionQuestion.position == 1)).scalar_one()
    q = db.get(Q, sq.question_id)
    assessment.submit(db, q, "1", sq=sq, time_seconds=30)
    db.commit()
    r = client.post(f"{loc}/q/1/swap", data={"reason": "different"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 409 and "already answered" in r.json()["error"]
    r = client.post(f"{loc}/q/2/swap", data={"reason": "bored"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400 and not r.json()["ok"]
    r = client.post(f"{loc}/q/99/swap", data={"reason": "different"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 400
    r = client.post(f"{loc}/q/1/swap", data={"reason": "different"})  # plain form: the usual error page
    assert r.status_code == 400 and "already answered" in r.text
    db.expire_all()
    assert db.execute(select(func.count()).select_from(SessionSwap)).scalar_one() == 0


def test_cross_site_swap_is_blocked(client, db):
    loc, sid = _open_today(client)
    db.expire_all()
    statuses = _statuses(db)
    r = client.post(f"{loc}/q/1/swap", data={"reason": "not_learnt", "lock": "1"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post(f"{loc}/q/1/swap", data={"reason": "not_learnt", "lock": "1"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    db.expire_all()
    assert db.execute(select(func.count()).select_from(SessionSwap)).scalar_one() == 0
    assert _statuses(db) == statuses


def test_swap_control_partial_for_the_question_page(db):
    from app.routes.common import templates

    sess = _today(db)
    controls = sessions.swap_controls(db, sess)
    tpl = templates.env.get_template("_swap_control.html")
    legal = _rows(sess, "LEGAL")[0]
    html = tpl.render(s=sess, sq=legal, swap=controls[legal.id])
    assert f'action="/session/{sess.id}/q/{legal.position}/swap"' in html
    assert 'name="back" value="question"' in html and 'name="lock" value="1" checked' in html
    maths = _rows(sess, "MATHS")[0]
    html = tpl.render(s=sess, sq=maths, swap=controls[maths.id])
    assert 'name="lock" value="1" >' in html or ('name="lock"' in html and "checked" not in html)
    passage = _passage_rows(sess)[-1]
    html = tpl.render(s=sess, sq=passage, swap=controls[passage.id])
    assert "Swap this passage" in html and 'name="lock"' not in html
    rec = sessions.swap_question(db, sess, legal, "different")
    db.commit()
    html = tpl.render(s=sess, sq=_row(sess, rec.position), swap=None, swap_notice=rec)
    assert 'id="swap-note"' in html and "data-swap-form" not in html
    assessment.submit(db, maths.question, "1", sq=maths, time_seconds=30)
    db.commit()
    assert "data-swap-form" not in tpl.render(s=sess, sq=maths, swap=sessions.swap_controls(db, sess)[maths.id])


# ------------------------------------------------- rules that need a narrow bank ---
def _unseen_by_stimulus(db, sess) -> dict:
    eng = db.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    out: dict = {}
    for q in db.execute(select(Question).where(Question.subject_id == eng.id, Question.category == "unseen",
                                               Question.stimulus_id.is_not(None))).scalars():
        out.setdefault(q.stimulus_id, []).append(q)
    return out


def test_a_read_passage_is_never_the_replacement(db):
    sess = _today(db)
    rows = _passage_rows(sess)
    current = {s.id for s in rows[0].question.stimulus.reading_set()}
    by_stim = _unseen_by_stimulus(db, sess)
    other = next(sid for sid, qs in by_stim.items() if sid not in current and len(qs) >= len(rows)
                 and not qs[0].stimulus.paired_with_id and not qs[0].stimulus.paired_by)
    _only_candidates(db, sess, "ENGLISH", {q.id for q in by_stim[other]})
    unit = sw.unit_for(sess, rows[0])
    assert {s.question.stimulus_id for s in sw.find_replacement(db, unit, "different", TUESDAY).items} == {other}
    # the student read that passage 20 days ago (inside the unseen-passage cooldown)
    past = DailySession(session_date=TUESDAY - timedelta(days=20), status="completed", session_number=0)
    db.add(past)
    db.flush()
    db.add(SessionQuestion(session_id=past.id, question_id=by_stim[other][0].id, subject_code="ENGLISH", position=1, status="submitted"))
    db.flush()
    rep = sw.find_replacement(db, unit, "different", TUESDAY)
    assert rep.items == [] and "has been read" in rep.why_none


def test_not_learnt_passage_never_comes_back_in_the_same_form(db):
    sess = _today(db)
    rows = _passage_rows(sess)
    form = rows[0].question.stimulus.form
    current = {s.id for s in rows[0].question.stimulus.reading_set()}
    keep = {q.id for sid, qs in _unseen_by_stimulus(db, sess).items() if sid not in current and qs[0].stimulus.form == form
            for q in qs}
    assert keep
    _only_candidates(db, sess, "ENGLISH", keep)
    unit = sw.unit_for(sess, rows[0])
    rep = sw.find_replacement(db, unit, "not_learnt", TUESDAY)
    assert rep.items == [] and f"every unread passage left is {form.lower()}" in rep.why_none
    assert sw.find_replacement(db, unit, "different", TUESDAY).items  # the same form is fine for "a different one"


def test_legal_mix_rules_for_a_replacement():
    from types import SimpleNamespace as NS

    def q(t, stim=None):
        return NS(question_type=t, stimulus_id=stim)

    sa, mcq, ext = q("short_answer"), q("mcq"), q("extended")
    assert sw._legal_ok(q("short_answer"), sa, [mcq, sa])
    assert not sw._legal_ok(q("extended"), sa, [mcq, sa])  # an extended response only replaces an extended response
    assert sw._legal_ok(q("extended"), ext, [mcq, sa])
    assert not sw._legal_ok(q("stimulus", 7), sa, [q("stimulus", 5), sa])  # one scenario to read per day
    assert sw._legal_ok(q("stimulus", 5), sa, [q("stimulus", 5), sa])
    assert not sw._legal_ok(q("mcq"), sa, [mcq, sa])  # at most one multiple-choice question ...
    assert sw._legal_ok(q("mcq"), sa, [mcq, ext])  # ... two on an extended-response day
    assert sw._legal_ok(q("mcq"), mcq, [mcq, sa])  # an MCQ for an MCQ keeps the count


def test_locking_the_last_open_topic_says_the_subject_will_pause(db):
    sess = _today(db, bank=False)
    legal_items = [it for it in db.execute(select(LearningPlanItem)).scalars() if it.subject.code == "LEGAL"]
    sq = _rows(sess, "LEGAL")[0]
    for it in legal_items:
        if it.id != sq.question.plan_item_id and it.status != LOCKED:
            it.status = LOCKED  # every other Legal topic is already "Not taught yet"
    db.commit()
    rec = sessions.swap_question(db, sess, sq, "not_learnt", lock=True)
    db.commit()
    assert rec.outcome == "removed" and "No Legal Studies topic is open now" in rec.message
