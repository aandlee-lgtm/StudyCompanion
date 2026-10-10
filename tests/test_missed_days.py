from datetime import timedelta

from sqlalchemy import select

from app.models import DailySession
from app.services import clock, sessions
from tests.conftest import TUESDAY, answer_correctly


def test_missed_day_does_not_accumulate(db):
    s = sessions.get_or_create_today(db)  # Tuesday
    answer_correctly(db, s)
    clock.set_today(TUESDAY + timedelta(days=2))  # skip Wednesday, open Thursday
    thu = sessions.get_or_create_today(db)
    db.commit()
    wed = db.execute(select(DailySession).where(DailySession.session_date == TUESDAY + timedelta(days=1))).scalar_one()
    assert wed.status == "missed" and not wed.questions
    assert len(thu.questions) == 11  # not 22


def test_missed_session_actions(db):
    clock.set_today(TUESDAY + timedelta(days=2))
    sessions.get_or_create_today(db)
    missed = db.execute(select(DailySession).where(DailySession.status == "missed")).scalars().all()
    assert missed
    m = missed[0]
    sessions.resume_missed(db, m)
    assert m.status == "generated" and len(m.questions) == 11
    other = db.execute(select(DailySession).where(DailySession.status == "missed")).scalars().all()
    if other:
        sessions.skip_missed(db, other[0])
        assert other[0].status == "skipped"


def test_move_revision_forward(db):
    from app.models import RevisionQueue

    s = sessions.get_or_create_today(db)
    answer_correctly(db, s, fraction=0.0)  # creates early revision items
    clock.set_today(TUESDAY + timedelta(days=2))
    sessions.get_or_create_today(db)
    wed = db.execute(select(DailySession).where(DailySession.session_date == TUESDAY + timedelta(days=1))).scalar_one()
    n = sessions.move_revision_forward(db, wed)
    assert n > 0 and wed.status == "skipped"
    assert all(r.due_date <= clock.today() for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "open")).scalars()
               if r.priority > 0.8)


def test_weekend_has_no_session(db, client):
    clock.set_today(TUESDAY + timedelta(days=4))  # Saturday
    assert sessions.get_or_create_today(db) is None
    db.commit()
    r = client.get("/today")
    assert "No session scheduled today" in r.text
