"""Integration: the v2 migration chain and the upgrade of a real v1 database.

``tests/fixtures/v1_database.sqlite.gz`` was built by the v1 app (commit e18d23d, revision 0001) with
two days of sessions answered in every subject (see tests/fixtures/make_v1_database.py)."""
from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import config
from app.database_setup import alembic_config, prepare_database

FIXTURE = Path(__file__).parent / "fixtures" / "v1_database.sqlite.gz"
CHAIN = ["0001", "0002_selection", "0003_working_photos", "0004_swap", "0005_followup", "0002_adaptive",
         "0002_english_logic", "0002_legal_logic", "0002_ingestion"]


def test_migrations_form_one_linear_chain():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    assert script.get_heads() == [CHAIN[-1]]
    assert [r.revision for r in reversed(list(script.walk_revisions()))] == CHAIN


def test_empty_database_upgrades_to_head(data_dir):
    url = f"sqlite:///{data_dir / 'empty.db'}"
    prepare_database(url, seed=False)
    eng = create_engine(url)
    with eng.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == CHAIN[-1]
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    eng.dispose()
    assert {"session_swaps", "feedback_questions", "practice_drafts", "exposure_events", "revision_sets",
            "legal_evidence_checks", "working_photos", "question_plan_items", "review_decisions"} <= tables


def test_v1_database_upgrades_keeping_data_and_seeding_v2_content(data_dir):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services.fingerprint import fingerprint

    db_file = data_dir / "hsc.db"
    with gzip.open(FIXTURE) as src, open(db_file, "wb") as dst:
        shutil.copyfileobj(src, dst)
    url = f"sqlite:///{db_file}"
    eng = create_engine(url)
    kept = ("attempts", "attempt_feedback", "daily_sessions", "session_questions", "error_journal", "question_exposure", "revision_queue", "mastery")
    with eng.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
        before = {t: c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in kept}
        attempts = c.execute(text("SELECT id, question_id, mark_awarded, response_text FROM attempts ORDER BY id")).all()
        payloads = dict(c.execute(text("SELECT attempt_id, payload FROM attempt_feedback")).all())
    eng.dispose()
    assert before["attempts"] > 10

    config.data_dir = data_dir
    prepare_database(url)
    eng = create_engine(url)
    with eng.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == CHAIN[-1]
        assert {t: c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in kept} == before
        assert c.execute(text("SELECT id, question_id, mark_awarded, response_text FROM attempts ORDER BY id")).all() == attempts
        after = dict(c.execute(text("SELECT attempt_id, payload FROM attempt_feedback")).all())
        assert {k: json.loads(v) for k, v in after.items()} == {k: json.loads(v) for k, v in payloads.items()}
        assert c.execute(text("SELECT value FROM settings WHERE key = 'student_name'")).scalar() == '"V1 Student"'
        subs = [r[0] for r in c.execute(text("SELECT code FROM learning_plan_items WHERE code LIKE 'LS-CRIME-%' OR code LIKE 'LS-HR-%'"))]
        assert len(subs) == 9  # Legal sub-areas as plan items (legal-09)
        assert c.execute(text("SELECT COUNT(*) FROM questions q JOIN learning_plan_items p ON p.id = q.plan_item_id "
                              "WHERE p.code IN ('LS-CRIME', 'LS-HR')")).scalar() == 0
        fps = {r[0] for r in c.execute(text("SELECT fingerprint FROM questions"))}
        titles = {r[0] for r in c.execute(text("SELECT title FROM legal_evidence"))}
    eng.dispose()
    seed = Path(__file__).resolve().parent.parent / "data" / "seed"
    for name, key in (("legal_v2.json", "questions"), ("english_course.json", "questions")):
        assert {fingerprint(q["text"]) for q in json.loads((seed / name).read_text())[key]} <= fps, name
    for s in json.loads((seed / "english_sets.json").read_text())["sets"]:
        assert {fingerprint(q["text"]) for q in s["questions"]} <= fps, s["key"]
    assert {i["title"] for i in json.loads((seed / "legal_evidence_v2.json").read_text())["items"]} <= titles

    client = TestClient(create_app(url))
    for path in ("/", "/session/1", "/session/2", "/errors", "/review", "/curriculum", "/legal-evidence"):
        assert client.get(path).status_code == 200, path
    for pos in range(1, 12):  # v1 feedback payloads render on the v2 question page
        r = client.get(f"/session/1/q/{pos}")
        if r.status_code == 404:
            break
        assert r.status_code == 200 and "Something went wrong" not in r.text, pos
