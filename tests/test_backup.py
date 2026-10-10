import zipfile

import pytest
from sqlalchemy import func, select

from app.config import config
from app.models import Attempt, Question
from app.services import assessment, backup


def test_backup_and_restore_roundtrip(db, data_dir):
    q = db.execute(select(Question).where(Question.answer.is_not(None))).scalars().first()
    assessment.submit(db, q, "1")
    db.commit()
    n_attempts = db.execute(select(func.count(Attempt.id))).scalar_one()
    qid, source_title = q.id, q.source.title
    db_path = data_dir / "test.db"
    zip_path = backup.create_backup(db_path, data_dir / "bk", {"timezone": "Australia/Sydney"})
    assert backup.validate_backup(zip_path)["app"] == "hsc-companion-2027"
    # more work after the backup
    assessment.submit(db, q, "2")
    db.commit()
    db.close()
    config.data_dir = data_dir
    safety = backup.restore_backup(zip_path, db_path)
    assert safety is not None and safety.exists()
    from app.db import SessionLocal

    s = SessionLocal()
    assert s.execute(select(func.count(Attempt.id))).scalar_one() == n_attempts
    q2 = s.get(Question, qid)
    assert q2.source.title == source_title  # attribution survives
    s.close()


def test_restore_rejects_foreign_zip(tmp_path):
    bad = tmp_path / "x.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(ValueError):
        backup.validate_backup(bad)


def test_csv_export(db):
    q = db.execute(select(Question).where(Question.answer.is_not(None))).scalars().first()
    assessment.submit(db, q, "1")
    csv_text = backup.attempts_csv(db)
    assert "marks_awarded" in csv_text and q.source.title in csv_text
