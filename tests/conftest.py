from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import factory  # noqa: E402
from app.config import config  # noqa: E402
from app.services import clock  # noqa: E402

MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", tmp_path)
    yield tmp_path
    clock.set_today(None)
    factory.set_test_provider(None)


@pytest.fixture()
def db(data_dir):
    """A fresh seeded database with setup completed and Year 12 starting Monday 12 Oct 2026."""
    from app.database_setup import prepare_database
    from app.db import SessionLocal
    from app.services import settings as st

    clock.set_today(TUESDAY)
    prepare_database(f"sqlite:///{data_dir / 'test.db'}")
    s = SessionLocal()
    st.set_(s, "setup_complete", True)
    st.set_(s, "year12_start_date", TUESDAY.isoformat())
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(f"sqlite:///{config.data_dir / 'test.db'}")
    return TestClient(app)


def plan_item(db, code):
    from sqlalchemy import select

    from app.models import LearningPlanItem

    return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one()


def subject_of(db, q):
    from app.models import Subject

    return db.get(Subject, q.subject_id).code


def answer_correctly(db, sess, fraction=1.0, confidence="confident"):
    """Answer every question in a session. Maths/MCQ deterministically; written via the
    offline estimate (or the injected provider)."""
    from app.services import assessment, sessions

    for sq in sess.questions:
        q = sq.question
        if q.answer and q.answer.get("type") == "set":
            resp = ", ".join(q.answer["values"]) if fraction >= 0.5 else "999"
        elif q.answer:
            resp = q.answer["value"] if fraction >= 0.5 else "999999"
        else:
            resp = (q.model_answer or "A detailed response 'quoted' that suggests and reveals meaning; overall highly effective.") if fraction >= 0.5 else "idk"
        assessment.submit(db, q, resp, sq=sq, confidence=confidence, time_seconds=60)
    sessions.maybe_complete(db, sess)
    db.commit()
