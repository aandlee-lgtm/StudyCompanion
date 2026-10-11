"""v2 adaptive: revision page (adaptive-18), revision sets, error-journal page and patterns panel (adaptive-11/12)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models import Attempt, ErrorJournal, LearningPlanItem, RevisionQueue, RevisionSet
from app.models.common import LEARNED, LOCKED
from app.services import assessment, clock, error_journal, revision
from tests.conftest import TUESDAY
from tests.test_v2_adaptive import maths_qs, open_items, right


def _learned(db, q):
    item = db.get(LearningPlanItem, q.plan_item_id)
    item.status = LEARNED
    db.commit()
    return item


def test_review_page_sections_evidence_and_practise_now(client, db):
    qs = maths_qs(db, n=6)
    _learned(db, qs[0])
    assessment.submit(db, qs[0], "987654", confidence="confident")
    db.commit()
    item = open_items(db, qs[0])[0]
    clock.set_today(item.due_date)
    page = client.get("/review").text
    assert "Due now" in page and "Two-month recycles" in page and "Exact repeats" in page and "Completed revision" in page
    assert "Last result 0%" in page and "counted answers correct" in page and f"/review/{item.id}/practise" in page
    r = client.get(f"/review/{item.id}/practise", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/practice/")
    picked = int(r.headers["location"].rsplit("/", 1)[1])
    assert picked != qs[0].id  # a revisit asks for a different question
    # answering it serves the item and shows its outcome under Completed revision
    from app.models import Question

    q = db.get(Question, picked)
    client.post(f"/practice/{picked}/submit", data={"answer": right(q), "confidence": "confident", "time_seconds": "60"})
    db.expire_all()
    assert db.get(RevisionQueue, item.id).status == "done"
    page = client.get("/review").text
    assert "100% — fixed" in page


def test_practise_now_never_serves_a_locked_skill_and_explains(client, db):
    qs = maths_qs(db, n=3)
    assessment.submit(db, qs[0], "987654", confidence="confident")
    db.commit()
    item = open_items(db, qs[0])[0]
    db.get(LearningPlanItem, qs[0].plan_item_id).status = LOCKED
    db.commit()
    r = client.get(f"/review/{item.id}/practise", follow_redirects=False)
    assert r.status_code == 303 and "none=" in r.headers["location"]
    page = client.get(r.headers["location"]).text
    assert "No suitable question is available" in page


def test_learning_topic_items_are_set_apart(client, db):
    qs = maths_qs(db, n=3)
    db.get(LearningPlanItem, qs[0].plan_item_id).status = "LEARNING"
    db.commit()
    assessment.submit(db, qs[0], "987654", confidence="confident")
    db.commit()
    data = revision.review_page(db, TUESDAY + timedelta(days=5))
    assert data["sections"]["learning"] and not data["sections"]["due"]


def test_revision_set_picks_distinct_due_questions_and_completes(client, db):
    from tests.test_v2_adaptive import subject_qs

    codes = ["1A", "1B", "1C", "2A"]
    from tests.conftest import plan_item

    firsts = []
    for code in codes:
        it = plan_item(db, code)
        it.status = LEARNED
        q = next((q for q in subject_qs(db, "MATHS", plan_item_id=it.id) if q.answer is not None and q.question_type != "mcq"), None)
        if q is None:
            continue
        assessment.submit(db, q, "987654", confidence="confident")
        firsts.append(q)
    db.commit()
    clock.set_today(TUESDAY + timedelta(days=3))
    r = client.post("/review/set", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/review/set/")
    s = db.execute(select(RevisionSet)).scalars().one()
    qids = [i["question_id"] for i in s.items]
    assert 1 <= len(qids) <= 5 and len(set(qids)) == len(qids)
    assert not set(qids) & {q.id for q in firsts}
    page = client.get(r.headers["location"]).text
    assert "Revision set" in page and "Start" in page
    from app.models import Question

    for qid in qids:
        q = db.get(Question, qid)
        client.post(f"/practice/{qid}/skip", data={"time_seconds": "5"}) if q.answer is None else \
            client.post(f"/practice/{qid}/submit", data={"answer": right(q), "confidence": "confident", "time_seconds": "30"})
    db.expire_all()
    client.get(r.headers["location"])
    db.expire_all()
    assert db.get(RevisionSet, s.id).status == "completed"


def _journal(db, qs, tag="sign error", n=3):
    for i, q in enumerate(qs[:n]):
        clock.set_today(TUESDAY + timedelta(days=i))
        a = assessment.submit(db, q, "987654", confidence="confident")
        error_journal.add_entries(db, a, q, "MATHS", [{"category": "careless error", "topic_tag": tag, "description": f"Dropped a negative in step {i + 1}."}],
                                  TUESDAY + timedelta(days=i), "deterministic")
    db.commit()


def test_errors_page_patterns_panel_and_practise_this(client, db):  # adaptive-12
    qs = maths_qs(db, n=6)
    _learned(db, qs[0])
    _journal(db, qs)
    page = client.get("/errors").text
    assert "Patterns" in page and "Sign error: 3 in the last 14 days" in page and "Practise this" in page and "Show examples" in page
    r = client.get("/errors/practise", params={"subject": "MATHS", "key": "sign error"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/practice/")
    assert int(r.headers["location"].rsplit("/", 1)[1]) not in {q.id for q in qs[:3]}
    examples = client.get("/errors", params={"key": "sign error"}).text
    assert examples.split("<h2>Entries")[1].count("Dropped a negative") == 3


def test_errors_page_shows_local_study_date_tags_and_resolution(client, db):  # adaptive-11
    qs = maths_qs(db, n=6)
    _journal(db, qs, n=1)
    e = db.execute(select(ErrorJournal).where(ErrorJournal.topic_tag == "sign error")).scalars().first()
    page = client.get("/errors").text
    assert TUESDAY.strftime("%d %b") in page and "sign error" in page and "careless error" in page
    client.post(f"/errors/{e.id}/resolve")
    db.expire_all()
    e = db.get(ErrorJournal, e.id)
    assert e.resolved and e.resolved_on is not None and not e.auto_resolved
    e.auto_resolved = True
    db.commit()
    page = client.get("/errors", params={"show_resolved": 1}).text
    assert "resolved automatically on" in page


def test_errors_page_paginates_with_full_counts(client, db):
    qs = maths_qs(db, n=2)
    a = assessment.submit(db, qs[0], "987654", confidence="confident")
    items = [{"category": "careless error", "topic_tag": None, "description": f"Entry {i}."} for i in range(60)]
    error_journal.add_entries(db, a, qs[0], "MATHS", items, TUESDAY, "deterministic")
    db.commit()
    total = db.execute(select(ErrorJournal).where(ErrorJournal.resolved.is_(False))).scalars().all()
    page = client.get("/errors").text
    assert f"{len(total)} open entries" in page and "Next page" in page
    page2 = client.get("/errors", params={"page": 2}).text
    assert "Previous page" in page2


def test_attempt_rows_exist(db):  # sanity: helpers used above rely on counted attempts
    qs = maths_qs(db, n=1)
    assessment.submit(db, qs[0], right(qs[0]), confidence="confident")
    db.commit()
    assert db.execute(select(Attempt)).scalars().first().counts_for_mastery
