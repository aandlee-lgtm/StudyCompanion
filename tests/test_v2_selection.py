"""Focused tests for the v2 selection engine and daily sessions (selection package).

The longitudinal behaviour is asserted in ``tests/sim``; these tests pin each rule on its own."""
from __future__ import annotations

import time
from collections import Counter
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import DailySession, LearningPlanItem, Mastery, RevisionQueue
from app.selection.context import build_context, form_key, legal_format, verb_tier
from app.selection.engine import build_daily_selection, explain, subject_code
from app.selection.optimiser import Option, choose
from app.selection.scoring import EXCLUDED, FRESH, Scored, eligibility
from app.services import clock, sessions
from app.services import settings as st
from tests.conftest import TUESDAY, answer_correctly, plan_item

FRIDAY = TUESDAY + timedelta(days=3)


def _v2_bank(db):
    from tests.sim.harness import add_v2_like_bank

    add_v2_like_bank(db)
    db.commit()


def _counts(sess) -> dict:
    return dict(Counter(sq.subject_code for sq in sess.questions))


# ------------------------------------------------------------------ optimiser ---
def _opt(subject, value, minutes, qid):
    q = SimpleNamespace(id=qid, estimated_minutes=minutes)
    return Option(subject, [Scored(q, value, {}, "learning", "")], value, minutes)


def test_optimiser_meets_the_window_by_the_cheapest_trade():
    """selection-01: the window is met by the option that costs the least value, and the trade is recorded."""
    options = {
        "MATHS": [_opt("MATHS", 5.0, 30, 1), _opt("MATHS", 4.9, 40, 2)],
        "ENGLISH": [_opt("ENGLISH", 3.0, 25, 3), _opt("ENGLISH", 1.0, 35, 4)],
        "LEGAL": [_opt("LEGAL", 2.0, 20, 5)],
    }
    chosen, facts = choose(options, (90, 80, 95), {"MATHS": (30, 42), "ENGLISH": (25, 35), "LEGAL": (18, 28)})
    assert chosen["MATHS"].ids == {2} and chosen["ENGLISH"].ids == {3}
    assert facts["in_window"] and facts["total"] == 85
    assert facts["displaced"]["MATHS"]["out"] == [1] and facts["displaced"]["MATHS"]["value_cost"] == 0.1


def test_optimiser_never_trades_a_much_better_set_for_a_few_minutes():
    options = {"MATHS": [_opt("MATHS", 8.0, 30, 1), _opt("MATHS", 4.0, 40, 2)], "ENGLISH": [_opt("ENGLISH", 3.0, 25, 3)],
               "LEGAL": [_opt("LEGAL", 2.0, 20, 4)]}
    chosen, facts = choose(options, (90, 80, 95), {})
    assert chosen["MATHS"].ids == {1} and not facts["in_window"]


# ------------------------------------------------------- exact repeats (hard) ---
def test_exact_repeat_before_revision_date_is_never_fresh(db):
    """selection-03 / adaptive-04: an attempted question is fresh again only when its revision date
    has arrived AND a different question on the skill was attempted since."""
    ctx = build_context(db, TUESDAY)
    sel = build_daily_selection(db, ctx)
    q = next(s.question for s in sel.items if subject_code(s.question) == "MATHS")
    ex = SimpleNamespace(last_seen=TUESDAY - timedelta(days=6), next_revision_date=TUESDAY + timedelta(days=4), score_history=[0.4])
    ctx.exposure[q.id] = ex
    tier, kind = eligibility(ctx, q, item_alternatives=3)
    assert tier > FRESH and kind == "repeat"
    ex.next_revision_date = TUESDAY - timedelta(days=1)  # due, but nothing different practised since
    assert eligibility(ctx, q, item_alternatives=3)[0] > FRESH
    ctx.item_attempt_dates[q.plan_item_id] = [(TUESDAY - timedelta(days=2), q.id + 10_000)]
    assert eligibility(ctx, q, item_alternatives=3) == (FRESH, "due")
    ex.last_seen = TUESDAY - timedelta(days=1)  # never on consecutive study days
    assert eligibility(ctx, q, item_alternatives=3)[0] == EXCLUDED
    ex.last_seen, ex.next_revision_date = TUESDAY - timedelta(days=20), TUESDAY + timedelta(days=10)
    assert eligibility(ctx, q, item_alternatives=3) == (1, "ladder")  # fallback rung (a), only when nothing fresh is left


def test_seeded_day_has_no_exact_repeat_before_its_revision_date(db):
    _v2_bank(db)
    seen: dict[int, date] = {}
    for k in range(4):
        d = TUESDAY + timedelta(days=k)
        clock.set_today(d)
        sess = sessions.get_or_create_today(db)
        for sq in sess.questions:
            e = sessions.exposure_for(db, sq.question_id)
            if e is not None and e.next_revision_date:
                assert e.next_revision_date <= d, (d, sq.question_id)
            assert sq.question_id not in seen
            seen[sq.question_id] = d
        answer_correctly(db, sess, fraction=0.0)


# --------------------------------------------------------------- set shape ---
def test_v2_bank_day_shape(db):
    """One passage with distinct marks; Legal daily format rules; one question per Maths form."""
    _v2_bank(db)
    sess = sessions.get_or_create_today(db)
    assert _counts(sess) == {"MATHS": 5, "ENGLISH": 3, "LEGAL": 3}
    eng = [sq.question for sq in sess.questions if sq.subject_code == "ENGLISH" and sq.question.category == "unseen"]
    units = {tuple(s.id for s in q.stimulus.reading_set()) for q in eng}
    assert len(units) == 1 and len({q.marks for q in eng}) == len(eng)
    legal = [sq.question for sq in sess.questions if sq.subject_code == "LEGAL"]
    fmts = Counter(legal_format(q) for q in legal)
    assert fmts["mcq"] <= (2 if fmts["extended"] else 1)
    assert max(verb_tier(q) for q in legal) >= 2
    forms = Counter(form_key(sq.question) for sq in sess.questions if sq.subject_code == "MATHS")
    assert max(forms.values()) <= 2
    assert sessions.get_or_create_today(db).id == sess.id  # persisted, never regenerated


def test_read_passage_is_not_unseen_again(db):
    """selection-04: the stimulus is the unit of freshness."""
    _v2_bank(db)
    units = []
    for k in range(3):
        clock.set_today(TUESDAY + timedelta(days=k))
        sess = sessions.get_or_create_today(db)
        stim = next(sq.question.stimulus for sq in sess.questions if sq.subject_code == "ENGLISH" and sq.question.category == "unseen")
        units.append(tuple(s.id for s in stim.reading_set()))
        answer_correctly(db, sess)
    assert len(set(units)) == 3
    assert "today's text is" in " ".join(sess.explanation["lines"])


def test_weights_act_on_topic_choice(db):
    """selection-05: stage-1 weights decide which topics get the revision slots."""
    weak = {"Y11-TRIG", "Y11-PROB"}
    for it in db.execute(select(LearningPlanItem)).scalars():
        if it.is_assumed_knowledge and it.subject.code == "MATHS":
            db.add(Mastery(plan_item_id=it.id, mastery=0.2 if it.code in weak else 0.95, attempts=6))
    db.commit()

    def older_items(weights):
        st.set_(db, "selection_weights", weights)
        ctx = build_context(db, TUESDAY)
        sel = build_daily_selection(db, ctx)
        return {ctx.plan[s.question.plan_item_id].code for s in sel.items if s.bucket == "older"}

    heavy = older_items({"current": 0.1, "weakness": 0.8, "spaced": 0.05, "coverage": 0.0, "novelty": 0.0,
                         "difficulty": 0.05, "source": 0.0})
    assert heavy and heavy <= weak


def test_light_mode_profile(db):
    sess = sessions.get_or_create_today(db)
    light = sessions.rebuild(db, sess, "light")
    assert light.id == sess.id and light.session_number == sess.session_number
    assert _counts(light) == {"MATHS": 3, "ENGLISH": 2, "LEGAL": 2}
    assert light.expected_minutes <= 50.5
    assert not any(legal_format(sq.question) == "extended" for sq in light.questions)


def test_exam_mode_has_no_foundation_maths(db):
    _v2_bank(db)
    st.set_(db, "mode", "exam")
    sess = sessions.get_or_create_today(db)
    assert all((sq.question.difficulty or 2) >= 2 for sq in sess.questions if sq.subject_code == "MATHS")
    assert sess.explanation["timed"] is True


# ---------------------------------------------------------- Legal plans ---
def test_extended_response_plan_rotates_topics(db):
    from app.selection.legal import extended_plan

    clock.set_today(FRIDAY)
    ctx = build_context(db, FRIDAY)
    ctx.sessions_before = 0
    assert not extended_plan(ctx)["due"]  # too early in the year
    ctx.sessions_before = 12
    plan = extended_plan(ctx)
    assert plan["due"] and plan["rotation"]
    crime = plan_item(db, "LS-CRIME")
    ctx.legal_history = [{"date": FRIDAY - timedelta(days=21), "type": "extended", "item": crime.id, "qid": 1,
                          "stimulus_id": None, "verb": "Evaluate", "marks": 15}]
    plan = extended_plan(ctx)
    assert plan["rotation"][0] != crime.id  # the topic not yet written on comes first
    ctx.legal_history[0]["date"] = FRIDAY - timedelta(days=2)
    assert not extended_plan(ctx)["due"]
    thursday = build_context(db, FRIDAY, session_date=FRIDAY - timedelta(days=1))
    thursday.sessions_before = 12
    assert not extended_plan(thursday)["due"]  # Term 4: Fridays only


def test_extended_rotation_groups_sub_areas_under_their_topic(db):
    """Legal sub-areas (LS-CRIME-TRIAL ...) are plan items too: an essay on a Crime sub-area counts
    for Crime, so the next extended response is on Human rights, wherever its question is filed."""
    from app.models import LearningPlanItem
    from app.selection.legal import extended_plan, pick_legal, topic_roots
    from app.selection.pool import Pool

    crime, hr = plan_item(db, "LS-CRIME"), plan_item(db, "LS-HR")
    subs = {}
    for parent, code in ((crime, "LS-CRIME-TRIAL"), (hr, "LS-HR-ENFORCE")):
        it = LearningPlanItem(subject_id=parent.subject_id, code=code, title=code, position=parent.position + 1,
                              status=parent.status, active=True)
        db.add(it)
        db.flush()
        subs[code] = it
    from app.models.common import ORIGIN_GENERATED
    from app.services import question_bank as qb

    src = qb.get_or_create_source(db, "Selection test bank (LEGAL)", organisation="test", subject_id=hr.subject_id,
                                  source_type="generated", tier=4)
    qb.create_question(db, subject_code="LEGAL", source_id=src.id, plan_item_id=subs["LS-HR-ENFORCE"].id, topic_id=hr.topic_id,
                       question_text="Evaluate the effectiveness of enforcement mechanisms for one human right (synthetic test).",
                       marks=15, question_type="extended", directive_verb="Evaluate", difficulty=3, category="core",
                       historical_or_generated=ORIGIN_GENERATED, model_answer="Synthetic model answer.", mapping_reason="test")
    db.flush()
    clock.set_today(FRIDAY)
    ctx = build_context(db, FRIDAY)
    roots = topic_roots(ctx)
    assert roots[subs["LS-CRIME-TRIAL"].id] == crime.id and roots[subs["LS-HR-ENFORCE"].id] == hr.id and roots[crime.id] == crime.id
    ctx.sessions_before = 12
    ctx.legal_history = [{"date": FRIDAY - timedelta(days=35), "type": "extended", "item": subs["LS-CRIME-TRIAL"].id, "qid": 1,
                          "stimulus_id": None, "verb": "Evaluate", "marks": 15}]
    plan = extended_plan(ctx)
    assert plan["due"] and plan["rotation"][0] == hr.id and set(plan["rotation"]) >= {crime.id, hr.id}
    assert subs["LS-CRIME-TRIAL"].id not in plan["rotation"]
    options, facts = pick_legal(ctx, Pool(db, ctx, "LEGAL"), 3)
    assert facts["extended"]["topic"] == hr.id
    best = max(options, key=lambda o: o.value)
    assert any(legal_format(s.question) == "extended" and topic_roots(ctx)[s.question.plan_item_id] == hr.id for s in best.items)
    db.rollback()


# ---------------------------------------------------------- missed days ---
def _setup_on(db, d):
    st.set_(db, "setup_completed_on", d.isoformat())
    db.commit()


def test_no_phantom_missed_days_before_setup(db):
    st.set_(db, "year12_start_date", (TUESDAY - timedelta(days=30)).isoformat())
    _setup_on(db, TUESDAY)
    sessions.get_or_create_today(db)
    assert not db.execute(select(DailySession).where(DailySession.status == "missed")).scalars().all()


def test_missed_choice_comes_before_todays_set(db, client):
    _setup_on(db, TUESDAY)
    answer_correctly(db, sessions.get_or_create_today(db))
    clock.set_today(TUESDAY + timedelta(days=2))  # Wednesday missed
    r = client.get("/today")
    assert r.status_code == 200 and "Before today's session" in r.text and "You missed 1 session" in r.text
    db.expire_all()
    assert sessions.get_session(db, clock.today()) is None  # nothing built yet
    r = client.post("/today/missed", data={"action": "skip"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/session/")
    db.expire_all()
    wed = sessions.get_session(db, TUESDAY + timedelta(days=1))
    assert wed.status == "skipped" and len(sessions.get_session(db, clock.today()).questions) == 11
    assert client.get("/today", follow_redirects=False).status_code == 303  # decided once


def test_catch_up_replaces_slots_and_is_idempotent(db):
    _setup_on(db, TUESDAY)
    answer_correctly(db, sessions.get_or_create_today(db), fraction=0.0)  # creates revision items
    thu = TUESDAY + timedelta(days=2)
    clock.set_today(thu)
    sessions.record_missed(db, thu)
    notice = sessions.missed_notice(db, thu)
    assert notice and notice["catch_up_names"]
    sess = sessions.resolve_missed(db, thu, "catch_up")
    assert len(sess.questions) == 11  # nothing extra
    flagged = [sq for sq in sess.questions if "catch_up" in (sq.score_breakdown or {}).get("flags", [])]
    assert 1 <= len({sq.question.plan_item_id for sq in flagged}) <= 3
    assert any("Catch-up" in line for line in sess.explanation["lines"])
    dues = sorted((r.id, r.due_date) for r in db.execute(select(RevisionQueue)).scalars())
    sessions.resolve_missed(db, thu, "catch_up")  # a second click changes nothing
    assert sorted((r.id, r.due_date) for r in db.execute(select(RevisionQueue)).scalars()) == dues
    assert len(sessions.get_session(db, thu).questions) == 11


def test_resumed_day_stays_open_and_shares_nothing_with_today(db):
    _setup_on(db, TUESDAY)
    answer_correctly(db, sessions.get_or_create_today(db))
    thu = TUESDAY + timedelta(days=2)
    clock.set_today(thu)
    sessions.record_missed(db, thu)
    wed = sessions.resolve_missed(db, thu, "resume")
    assert wed.session_date == TUESDAY + timedelta(days=1) and len(wed.questions) == 11
    sessions.record_missed(db, thu)  # Today is opened again the same day
    assert wed.status == "generated" and sessions.missed_notice(db, thu) is None
    today = sessions.get_or_create_today(db)
    assert not {q.question_id for q in wed.questions} & {q.question_id for q in today.questions}
    assert [s.session_number for s in (sessions.get_session(db, TUESDAY), wed, today)] == [1, 2, 3]
    clock.set_today(thu + timedelta(days=1))  # left untouched: not offered again
    sessions.record_missed(db, thu + timedelta(days=1))
    assert wed.status == "skipped"


# ------------------------------------------------------------------ timer ---
def test_timer_counts_active_time_only(db, monkeypatch):
    sess = sessions.get_or_create_today(db)
    t0 = datetime(2026, 10, 13, 9, 0, 0)
    now = {"t": t0}
    monkeypatch.setattr(sessions, "utcnow", lambda: now["t"])
    sessions.start_timer(db, sess)
    for k in range(1, 5):  # four heartbeats 30 s apart
        now["t"] = t0 + timedelta(seconds=30 * k)
        sessions.heartbeat(db, sess)
    assert sess.elapsed_seconds == 120
    now["t"] += timedelta(hours=9)  # laptop left open overnight
    out = sessions.heartbeat(db, sess)
    assert out["elapsed"] == 120 + sessions.HEARTBEAT_CREDIT
    assert "without activity" in (out["note"] or "")
    sessions.pause_timer(db, sess, "hidden")
    frozen = sessions.elapsed(sess)
    now["t"] += timedelta(hours=2)
    assert sessions.elapsed(sess) == frozen and sess.pause_note.startswith("Paused while")
    sess.elapsed_seconds = 10 ** 6
    assert sessions.elapsed(sess) == sessions.time_cap(sess)


def test_heartbeat_and_timer_routes(db, client):
    sess = sessions.get_or_create_today(db)
    db.commit()
    r = client.post(f"/session/{sess.id}/timer", data={"action": "start"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.json()["running"] is True
    r = client.post(f"/session/{sess.id}/heartbeat")
    assert r.status_code == 200 and "elapsed" in r.json()
    r = client.post(f"/session/{sess.id}/timer", data={"action": "pause", "reason": "idle"}, headers={"X-Requested-With": "fetch"})
    assert r.json()["running"] is False and "Paused automatically" in r.json()["note"]


# ------------------------------------------------------- history and close ---
def test_close_unfinished_session_and_history(db, client):
    from app.services import assessment

    sess = sessions.get_or_create_today(db)
    for sq in sess.questions[:4]:
        assessment.submit(db, sq.question, sq.question.model_answer or "1", sq=sq, confidence="unsure", time_seconds=60)
    db.commit()
    clock.set_today(TUESDAY + timedelta(days=1))
    assert [u.id for u in sessions.unfinished(db, clock.today())] == [sess.id]
    r = client.post(f"/session/{sess.id}/close", follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    assert db.get(DailySession, sess.id).status == "closed"
    page = client.get("/sessions")
    assert page.status_code == 200 and "Closed early" in page.text


def test_streak_counts_substantial_days(db):
    sess = sessions.get_or_create_today(db)
    assert not sessions.counts_for_streak(db, sess)
    sess.elapsed_seconds = 61 * 60
    assert sessions.counts_for_streak(db, sess)


# ------------------------------------------------------------ explanation ---
def test_explanation_reports_true_accuracy(db):
    sess = sessions.get_or_create_today(db)
    answer_correctly(db, sess, fraction=0.0)
    clock.set_today(TUESDAY + timedelta(days=1))
    ctx = build_context(db, clock.today())
    sel = build_daily_selection(db, ctx)
    reasons = " ".join(s.reason for s in sel.items)
    text = " ".join(explain(ctx, sel)["lines"])
    assert "Mathematics:" in text and "English:" in text and "Legal Studies" in text
    assert "correctly" in reasons or "averaged" in reasons or "Revision" in reasons
    assert "mastery" not in reasons.lower()


# ------------------------------------------------------------ performance ---
def test_generation_is_fast_with_a_large_bank(db):
    """selection-20: a bank of 3,000+ questions is planned well under a second."""
    import random

    from app.services import question_bank as qb
    from tests.sim.harness import _words

    _v2_bank(db)
    rng = random.Random(3)
    items = [i for i in db.execute(select(LearningPlanItem)).scalars() if i.status != "LOCKED"]
    src = qb.get_or_create_source(db, "Performance bank", organisation="test", source_type="generated", tier=4)
    for k in range(3000):
        it = items[k % len(items)]
        qb.create_question(db, subject_code=it.subject.code, source_id=src.id, question_text=f"Perf {k} " + _words(rng, 16),
                           marks=rng.choice([2, 3, 4, 5]), question_type="short_answer", difficulty=rng.choice([1, 2, 3]),
                           topic_id=it.topic_id, plan_item_id=it.id, category="course" if it.subject.code == "ENGLISH" else "core",
                           historical_or_generated="generated", mapping_reason="performance test")
    db.commit()
    build_daily_selection(db, build_context(db, TUESDAY))  # warm caches
    t = time.perf_counter()
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    assert time.perf_counter() - t < 2.0  # about 0.1 s on a laptop; generous for CI
    assert len(sel.items) == 11


# ------------------------------------------------------------------ phases ---
def test_phases_make_the_year_more_exam_like(db):
    """selection-22: phases come from progress; later phases time sessions and prefer exam-style work."""
    from app.selection.phases import phase_for, timed_today

    s = st.all_settings(db)
    assert [phase_for(p, s).name for p in (0.05, 0.4, 0.8, 0.95)] == ["companion", "consolidation", "trials", "final"]
    trials = phase_for(0.8, s)
    assert timed_today(trials, 4, [0, 1, 2, 3, 4]) and not timed_today(trials, 2, [0, 1, 2, 3, 4])
    # late in the year (Friday in Term 3): the session is timed and says why
    day = date(2027, 8, 6)
    assert day.weekday() == 4
    clock.set_today(day)
    ctx = build_context(db, day)
    assert ctx.phase.name == "trials" and ctx.profile.timed
    sel = build_daily_selection(db, ctx)
    lines = " ".join(explain(ctx, sel)["lines"])
    assert "Trial-preparation phase" in lines and "timed session" in lines


def test_exam_style_bonus_prefers_multipart_questions(db):
    from app.models import Question
    from app.selection.phases import PHASES
    from app.selection.scoring import question_score

    _v2_bank(db)
    ctx = build_context(db, TUESDAY)
    multi = db.execute(select(Question).where(Question.question_text.like("(a)%"))).scalars().first()
    assert multi is not None
    base, _ = question_score(ctx, multi, "MATHS", "fresh")
    ctx.phase = PHASES["trials"]
    later, _ = question_score(ctx, multi, "MATHS", "fresh")
    assert later > base


# -------------------------------------------------------------- bank health ---
def test_bank_health_uses_the_engines_rules(db):
    from app.selection.health import bank_health

    _v2_bank(db)
    h = bank_health(db, TUESDAY)
    assert h["ENGLISH"]["passages_left"] >= 25 and h["ENGLISH"]["status"] == "ok"
    assert h["LEGAL"]["fresh_by_format"]["stimulus"] >= 10 and h["LEGAL"]["fresh_by_format"]["extended"] >= 6
    assert h["MATHS"]["learning_items"] and all(i["fresh"] > 0 for i in h["MATHS"]["learning_items"])
    assert all(h[c]["status"] in ("ok", "low", "empty") and h[c]["text"] for c in ("MATHS", "ENGLISH", "LEGAL"))
    sess = sessions.get_or_create_today(db)
    answer_correctly(db, sess)
    after = bank_health(db, TUESDAY + timedelta(days=1))
    # one passage was read today: exactly one fewer unread passage, whatever else changed
    assert after["ENGLISH"]["passages_left"] == h["ENGLISH"]["passages_left"] - 1
    legal_served = sum(1 for sq in sess.questions if sq.subject_code == "LEGAL")
    assert after["LEGAL"]["fresh"] + after["LEGAL"]["fresh_by_format"]["extended"] <= (
        h["LEGAL"]["fresh"] + h["LEGAL"]["fresh_by_format"]["extended"] - legal_served + 1)


def test_bank_health_flags_a_learning_item_without_questions_or_template(db, client):
    from app.models import Question
    from app.selection.health import bank_health
    from app.services import maths_templates

    item = plan_item(db, "1A")
    for q in db.execute(select(Question).where(Question.plan_item_id == item.id)).scalars():
        q.approved = False
    db.commit()
    saved = maths_templates.TEMPLATES.pop("1A", None)
    try:
        h = bank_health(db, TUESDAY)
        row = next(i for i in h["MATHS"]["learning_items"] if i["code"] == "1A")
        assert row["fresh"] == 0 and row["empty"] and row["low"] and not row["template"]
        assert h["MATHS"]["status"] == "empty" and "1A" in h["MATHS"]["action"]
        r = client.get("/api/selection/bank-health")
        assert r.status_code == 200 and r.json()["MATHS"]["status"] == "empty"
        page = client.get("/sessions")
        assert page.status_code == 200 and "Question bank" in page.text and "1A" in page.text
    finally:
        if saved is not None:
            maths_templates.TEMPLATES["1A"] = saved
    h = bank_health(db, TUESDAY)  # with its template back, the item keeps itself supplied
    row = next(i for i in h["MATHS"]["learning_items"] if i["code"] == "1A")
    assert row["template"] and not row["low"]


def test_learning_item_without_questions_is_named(db):
    from app.models import Question

    item = plan_item(db, "1A")
    for q in db.execute(select(Question).where(Question.plan_item_id == item.id)).scalars():
        q.approved = False
    from app.services import maths_templates

    saved = maths_templates.TEMPLATES.pop("1A", None)
    try:
        db.flush()
        ctx = build_context(db, TUESDAY)
        sel = build_daily_selection(db, ctx)
        text = " ".join(sel.notes) + " ".join(explain(ctx, sel)["lines"])
        assert "1A" in text and "no practice questions" in text
        assert any("current-learning Mathematics slots" in n for n in sel.notes)
    finally:
        if saved is not None:
            maths_templates.TEMPLATES["1A"] = saved
        db.rollback()
