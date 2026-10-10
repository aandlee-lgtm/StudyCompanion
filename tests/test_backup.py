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


def test_backup_includes_imported_files_and_blocks_zip_slip(db, data_dir):
    (data_dir / "sources").mkdir(exist_ok=True)
    (data_dir / "sources" / "paper.pdf").write_bytes(b"%PDF-1.4 test")
    zip_path = backup.create_backup(data_dir / "test.db", data_dir / "bk", {})
    with zipfile.ZipFile(zip_path) as z:
        assert "sources/paper.pdf" in z.namelist()
    # a hostile member name must not be written outside the data folder
    evil = data_dir / "evil.zip"
    with zipfile.ZipFile(zip_path) as src, zipfile.ZipFile(evil, "w") as z:
        for n in src.namelist():
            z.writestr(n, src.read(n))
        z.writestr("sources/../../escaped.txt", "x")
    db.close()
    backup.restore_backup(evil, data_dir / "test.db")
    assert not (data_dir.parent / "escaped.txt").exists()
    assert (data_dir / "sources" / "paper.pdf").exists()


def test_auto_backup_once_per_day_and_pruned(db, data_dir):
    out = data_dir / "auto"
    first = backup.auto_backup(data_dir / "test.db", out, today="20261013")
    assert first is not None and first.exists()
    assert backup.auto_backup(data_dir / "test.db", out, today="20261013") is None  # same day: skip
    for d in range(14, 30):
        backup.auto_backup(data_dir / "test.db", out, today=f"202610{d}")
    assert len(list(out.glob("hsc-companion-auto-*.zip"))) == backup.AUTO_KEEP
