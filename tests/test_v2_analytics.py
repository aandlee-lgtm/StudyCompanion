"""Analytics v2 (owner: analytics): counted attempts, interpretation, readiness, summaries,
weekly/monthly reviews, dashboard, question bank health, historical coverage and page speed.

Most tests read one realistic five-week history (built once for the module with the real
session engine and ``assessment.submit``); tests that change data use a fresh database."""
from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import config
from app.services import clock

from analytics_history import build_history

WEEKS = 5


# ------------------------------------------------------------------ fresh database ---
def _first_session(db):
    from app.services import sessions

    clock.set_today(date(2026, 10, 13))
    return sessions.get_or_create_today(db)


def test_empty_database_pages_render_and_say_not_enough(db, client):
    from app.services import analytics

    r = analytics.readiness(db)
    assert r["enough"] is False and r["score"] is None
    assert "Not enough data yet" in r["summary"][0]
    rep = analytics.progress_report(db, "30")
    assert rep["insights"] == [] and "Not enough answers yet" in rep["interpretation"][0]
    for url in ("/", "/progress", "/progress?window=7", "/progress?window=all", "/progress?window=bogus", "/progress/week", "/progress/month"):
        resp = client.get(url)
        assert resp.status_code == 200, url
    assert "Not enough data" in client.get("/").text
    assert "Question bank health" in client.get("/").text


def test_only_counted_attempts_are_analysed(db):
    """Retries, same-day practice after the answer was seen and unmarked self-marks are left out."""
    from app.models import Attempt, AttemptFeedback
    from app.services import assessment
    from app.services.analytics_data import Dataset

    sess = _first_session(db)
    sq1, sq2 = sess.questions[0], sess.questions[1]
    assessment.submit(db, sq1.question, "12345", sq=sq1, time_seconds=60)
    assessment.submit(db, sq1.question, "12346", sq=sq1, time_seconds=60)  # retry: attempt 2
    assessment.submit(db, sq2.question, "", sq=sq2, time_seconds=20, skipped=True)
    assessment.submit(db, sq2.question, "after seeing the answer", time_seconds=30)  # practice, same day
    # an imported question waiting for its self-mark
    pending = Attempt(question_id=sess.questions[2].question_id, attempt_number=1, mark_awarded=0, mark_possible=3,
                      marking_method="self", submitted_at=datetime(2026, 10, 13, 10, 0))
    db.add(pending)
    db.flush()
    db.add(AttemptFeedback(attempt_id=pending.id, payload={"kind": "self_mark"}, error_categories=[]))
    db.commit()
    ds = Dataset(db)
    assert ds.attempts_total == 5
    assert sorted(f.question_id for f in ds.facts) == sorted([sq1.question_id, sq2.question_id])
    assert next(f for f in ds.facts if f.question_id == sq2.question_id).skipped


def test_dashboard_during_a_session(db, client):
    from app.services import assessment

    sess = _first_session(db)
    for sq in sess.questions[:2]:
        assessment.submit(db, sq.question, "12345", sq=sq, time_seconds=60)
        sq.status = "submitted"
    db.commit()
    page = client.get("/").text
    assert f"2 / {len(sess.questions)} questions" in page and "Continue" in page


def test_specification_example_maths_context_insight(db):
    """'Consistently strong at differentiation mechanics but lose marks when calculus is embedded
    in modelling questions' — fired from the data, with the numbers."""
    from app.services.analytics_data import Dataset, Fact
    from app.services.analytics_insights import APPLICATION_RE, insights

    ds = Dataset(db, today=date(2026, 11, 2))
    maths = [i for i in ds.items.values() if ds.subject_codes[i.subject_id] == "MATHS" and i.topic_id]
    mech = next(i for i in maths if "differentiation" in (i.title + ds.area_name(i.topic_id)).lower()
                and not APPLICATION_RE.search(i.title + " " + ds.area_name(i.topic_id)))
    app_item = next(i for i in maths if APPLICATION_RE.search(i.title + " " + ds.area_name(i.topic_id)))

    def fact(n, item, frac):
        return Fact(attempt_id=n, question_id=n, sq_id=None, subject="MATHS", day=date(2026, 10, 20) + timedelta(days=n % 10), mark=frac * 2,
                    possible=2, skipped=False, confidence="confident", seconds=120, method="deterministic", plan_item_id=item.id,
                    area_id=item.topic_id, difficulty=2, est_minutes=2, marks=2, qtype="working", verb=None, category=None, auto=True,
                    mcq=False, form=None, words=0, repeat=False)
    facts = [fact(n, mech, 1.0 if n % 8 else 0.5) for n in range(8)] + [fact(100 + n, app_item, 0.0 if n % 3 else 1.0) for n in range(6)]
    found = insights(ds, facts)
    ctx = [i for i in found if i.kind == "context"]
    assert ctx, [i.text for i in found]
    text = ctx[0].text
    assert "consistently strong" in text and "mechanics" in text and "worded or modelling problems" in text
    assert "94%" in text and "across 8 questions" in text and "33%" in text
    # too little data: no interpretation at all
    assert insights(ds, facts[:6]) == []


def test_historical_coverage_counts_unique_source_questions(db):
    from app.models import LearningPlanItem, Question, Source, Subject
    from app.models.common import APPROVAL_APPROVED, APPROVAL_PENDING
    from app.services.analytics_bank import historical_coverage

    item = db.execute(select(LearningPlanItem).where(LearningPlanItem.code == "1A")).scalar_one()
    subj = db.get(Subject, item.subject_id)
    before = next(c for c in historical_coverage(db) if c["topic_id"] == item.topic_id)
    src = Source(title="2023 HSC Mathematics Advanced", source_type="hsc_exam", tier=2, official=True)
    db.add(src)
    db.flush()

    def q(number, origin="HISTORICAL", approved=True, relevance="DIRECT"):
        db.add(Question(subject_id=subj.id, source_id=src.id, question_text="x", plan_item_id=item.id, topic_id=item.topic_id,
                        question_number=number, source_year=2023, historical_or_generated=origin, relevance_status=relevance,
                        approved=approved, approval_status=APPROVAL_APPROVED if approved else APPROVAL_PENDING))
    for n in ("11(a)", "11(b)", "Q11 (c)"):  # three parts of one question
        q(n)
    q("12")
    q("13", relevance="PARTIAL")
    q("14", approved=False)  # waiting for review
    db.commit()
    after = next(c for c in historical_coverage(db) if c["topic_id"] == item.topic_id)
    assert after["questions"] - before["questions"] == 3  # Q11 once, Q12, Q13
    assert after["score"] == pytest.approx(before["score"] + 0.8 + 0.8 + 0.4, abs=0.05)
    assert after["pending"] - before["pending"] == 1
    assert after["level"] in ("LIMITED", "MODERATE", "GOOD", "NONE")
    if after["level"] in ("LIMITED", "NONE"):
        assert after["actions"][0]["text"].startswith("Import the official NESA 2027 sample")
        assert "waiting for approval" in after["actions"][1]["text"]


def test_bank_health_lists_learning_items_without_questions(db):
    from app.models import LearningPlanItem, Question
    from app.services import analytics

    d = analytics.dashboard(db)
    assert set(d["bank"]) == {"MATHS", "ENGLISH", "LEGAL"}
    for b in d["bank"].values():
        assert b["headline"] and b["level"] in ("good", "warn", "bad")
    legal = d["bank"]["LEGAL"]
    assert legal["days"] == legal["fresh"] // legal["per_day"]
    # an English item marked LEARNING that has no questions at all
    with_q = {r for (r,) in db.execute(select(Question.plan_item_id).where(Question.plan_item_id.is_not(None))).all()}
    empty = next(i for i in db.execute(select(LearningPlanItem)).scalars()
                 if i.id not in with_q and i.subject.code in ("ENGLISH", "LEGAL"))  # e.g. a Legal option not chosen yet
    empty.active = True
    empty.status = "LEARNING"
    db.commit()
    names = analytics.dashboard(db)["bank"][empty.subject.code]["empty_learning"]
    assert any(empty.title in n for n in names)


# ------------------------------------------------------------------ five-week history ---
@pytest.fixture(scope="module")
def history(tmp_path_factory):
    from app.database_setup import prepare_database
    from app.db import SessionLocal
    from app.services import settings as st

    d = tmp_path_factory.mktemp("analytics_history")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "data_dir", d)
    clock.set_today(date(2026, 10, 12))
    prepare_database(f"sqlite:///{d / 'test.db'}")
    s = SessionLocal()
    st.set_(s, "setup_complete", True)
    st.set_(s, "year12_start_date", "2026-10-12")
    s.commit()
    h = build_history(s, weeks=WEEKS)
    yield {"db": s, "h": h, "dir": d}
    s.close()
    clock.set_today(None)
    mp.undo()


@pytest.fixture()
def hist(history, monkeypatch):
    monkeypatch.setattr(config, "data_dir", history["dir"])
    clock.set_today(history["h"].end)  # the last study day (a Friday)
    history["db"].expire_all()
    yield history
    clock.set_today(None)


def _hclient(hist):
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app(f"sqlite:///{hist['dir'] / 'test.db'}"))


def test_history_is_realistic(hist):
    h = hist["h"]
    assert h.end.weekday() == 4 and len(h.missed) == 3 and len(h.partial) == 1
    assert h.answered > 200


def test_readiness_is_explained_low_early_and_counted_only(hist):
    from app.services import analytics

    r = analytics.readiness(hist["db"])
    assert r["enough"] and r["score"] % 5 == 0
    assert 0 <= r["score"] <= 45, "five weeks into Year 12 most of the course is untaught: readiness must be low"
    assert r["coverage"] < 50
    assert r["score"] == pytest.approx(r["coverage"] * r["quality"] / 100, abs=5)
    assert "most of the course has not been assessed" in " ".join(r["summary"])
    assert "not a predicted HSC mark" in r["explanation"] and "first attempts" in r["explanation"]
    keys = {c["key"] for c in r["components"]}
    assert keys == {"recent", "hsc_difficulty", "unseen", "retention", "timed", "consistency"}
    assert sum(c["weight"] for c in r["components"]) == 100
    cons = next(c for c in r["components"] if c["key"] == "consistency")
    assert "study days" in cons["detail"]


def test_progress_numbers_and_specific_interpretations(hist):
    from app.services import analytics
    from app.services.analytics_data import Dataset

    db = hist["db"]
    ds = Dataset(db)
    rep = analytics.progress_report(db, "all", ds)
    assert rep["total_attempts"] == len(ds.facts)
    for code, sd in rep["subjects"].items():
        fs = [f for f in ds.facts if f.subject == code]
        assert sd["answers"] == len(fs)
        if fs:
            assert sd["average"] == round(100 * sum(f.frac for f in fs) / len(fs))
            assert sum(r["n"] for r in sd["difficulty"]) == len(fs)
    # the builder makes Crime strong and Human rights weak: the interpretation must say so, with numbers
    legal = [i for i in rep["insights"] if i["subject"] == "LEGAL" and i["kind"] == "topic-gap"]
    assert legal and "on Crime (" in legal[0]["text"] and "on Human rights (" in legal[0]["text"]
    for i in rep["insights"]:
        assert any(ch.isdigit() for ch in i["text"]) and i["basis"]
    weakest = [w["name"] for w in rep["weakest"]]
    assert any(w.startswith("Human rights") for w in weakest)  # a Human rights sub-area
    assert all(w["n"] >= 3 and w["pct"] < 60 for w in rep["weakest"])
    assert rep["coverage"] and {c["level"] for c in rep["coverage"]} <= {"GOOD", "MODERATE", "LIMITED", "NONE"}
    # windows narrow the data
    assert analytics.progress_report(db, "7", ds)["total_attempts"] < rep["total_attempts"]


def test_session_summary_marks_and_sections(hist):
    from app.models import DailySession
    from app.services import analytics, sessions

    db = hist["db"]
    sess = sessions.get_session(db, hist["h"].end)
    s = analytics.session_summary(db, sess)
    firsts = sessions.first_attempts(db, sess)
    subject_of = {sq.id: sq.subject_code for sq in sess.questions}
    for code, sd in s["subjects"].items():
        got = sum(a.mark_awarded for sq_id, a in firsts.items() if subject_of[sq_id] == code)
        assert sd["awarded"] == pytest.approx(got, abs=0.05)
    assert s["answered"] == s["total"] == len(sess.questions)
    for key in ("strength", "main_learning", "top_priority"):
        assert isinstance(s[key], str) and len(s[key]) > 20
    assert s["minutes"] > 0
    assert "listed under" not in s["main_learning"]
    # the partly done session reports what is left
    part = db.execute(select(DailySession).where(DailySession.session_date == hist["h"].partial[0])).scalar_one()
    ps = analytics.session_summary(db, part)
    assert ps["answered"] == 4 and ps["total"] == len(part.questions)


def test_weekly_review_counts(hist):
    from app.services import analytics

    db = hist["db"]
    h = hist["h"]
    w = analytics.weekly_review(db, h.end)
    week_days = [h.end - timedelta(days=i) for i in range(5)]
    assert w["sessions_total"] == 5
    assert w["sessions_completed"] == sum(1 for d in h.completed if d in week_days)
    assert w["is_friday_review"]
    for key in ("strongest_improvement", "persistent_weakness", "next_priority"):
        assert w[key]
    # a week with a missed day (study day index 8 is the Thursday of week 2)
    w2 = analytics.weekly_review(db, h.missed[0] + timedelta(days=1))
    assert w2["sessions_missed"] >= 1


def test_monthly_review_is_complete_and_interpreted(hist):
    from app.services import analytics

    m = analytics.monthly_review(hist["db"])
    for key in ("coverage", "mastery", "improvement", "weak", "response_quality", "time_management", "retention", "priorities"):
        assert m[key], key
    assert m["n_prev"] > 0
    assert all("→" in line for line in m["improvement"])
    assert any("Band 6 models" in line or "words" in line for line in m["response_quality"])


def test_dashboard_has_every_section(hist):
    from app.services import analytics

    d = analytics.dashboard(hist["db"])
    for key in ("session", "streak", "week", "plan_status", "revision", "weak", "improvement", "readiness", "bank", "insight"):
        assert key in d
    assert d["week"]["questions"] > 0 and d["week"]["minutes"] > 0
    assert set(d["plan_status"]) == {"MATHS", "ENGLISH", "LEGAL"}
    assert all(w["pct"] < 60 and w["n"] >= 3 for w in d["weak"])


def test_history_pages_render(hist):
    from app.models import DailySession

    c = _hclient(hist)
    db = hist["db"]
    friday = db.execute(select(DailySession).where(DailySession.session_date == hist["h"].end)).scalar_one()
    part = db.execute(select(DailySession).where(DailySession.session_date == hist["h"].partial[0])).scalar_one()
    pages = {
        "/": ["Subject status", "Weak areas", "Recent improvement", "Next topics", "Question bank health", "HSC readiness", "Streak"],
        "/progress": ["What the data says", "By difficulty", "Syllabus coverage", "Historical question coverage", "Quality factor"],
        "/progress?window=7": ["What the data says"],
        "/progress?window=all": ["What the data says"],
        "/progress/week": ["Strongest improvement", "Persistent weakness", "Next week", "Revision coming due"],
        "/progress/month": ["Suggested priorities", "Topic mastery", "Response quality", "Time management", "Revision retention"],
        f"/session/{friday.id}/summary": ["Today's strength", "Main learning", "Top priority", "Revision scheduled", "This week"],
        f"/session/{part.id}/summary": ["Session so far", "answered"],
    }
    for url, needles in pages.items():
        r = c.get(url)
        assert r.status_code == 200, url
        for n in needles:
            assert n in r.text, (url, n)


def test_pages_are_fast_with_3000_attempts(hist, tmp_path, monkeypatch):
    """Clone the history back in time until there are 3,000+ attempts: every page < 1 s."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    db_file = tmp_path / "test.db"
    src = sqlite3.connect(hist["dir"] / "test.db")
    con = sqlite3.connect(db_file)
    src.backup(con)  # a consistent copy, including pages still in the WAL file
    src.close()
    monkeypatch.setattr(config, "data_dir", tmp_path)
    cols = [r[1] for r in con.execute("pragma table_info(attempts)") if r[1] not in ("id", "submitted_at")]
    n = con.execute("select max(id) from attempts").fetchone()[0]
    k = 1
    while con.execute("select count(*) from attempts").fetchone()[0] < 3000:
        con.execute(f"insert into attempts (submitted_at, {','.join(cols)}) select datetime(submitted_at, '-{7 * WEEKS * k} days'), "
                    f"{','.join(cols)} from attempts where id <= ?", (n,))
        k += 1
    con.commit()
    total = con.execute("select count(*) from attempts").fetchone()[0]
    con.close()
    assert total >= 3000
    c = TestClient(create_app(f"sqlite:///{db_file}"))
    for url in ("/", "/progress", "/progress?window=all", "/progress/week", "/progress/month"):
        assert c.get(url).status_code == 200  # warm-up (template compilation, imports)
        t = time.perf_counter()
        r = c.get(url)
        elapsed = time.perf_counter() - t
        assert r.status_code == 200
        assert elapsed < 1.0, f"{url} took {elapsed:.2f}s with {total} attempts"
    from app.db import SessionLocal
    from app.models import Attempt
    from app.services.analytics_data import Dataset

    s = SessionLocal()
    try:
        assert s.execute(select(func.count(Attempt.id))).scalar_one() == total
        assert len(Dataset(s).facts) > 1000  # the clones count as first attempts on earlier days
    finally:
        s.close()
