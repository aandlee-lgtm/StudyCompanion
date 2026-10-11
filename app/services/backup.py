"""Backup and restore. A backup is a .zip containing a consistent SQLite snapshot (made with
SQLite's online backup API), the settings as JSON and a manifest. Restore validates the zip,
saves a safety backup of the current database first, then replaces it."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.models import Attempt, Question, Subject

APP_ID = "hsc-companion-2027"
FORMAT_VERSION = 1


def _snapshot(db_path: Path, dest: Path) -> None:
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(dest))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


FILE_FOLDERS = ("sources", "renders", "working")  # imported PDFs, question/diagram renders, photos of working


def create_backup(db_path: Path | None = None, out_dir: Path | None = None, settings: dict | None = None,
                  include_files: bool = True) -> Path:
    db_path = db_path or config.db_path
    out_dir = out_dir or config.backups_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"hsc-companion-backup-{stamp}.zip"
    n = 1
    while out.exists():  # never overwrite an existing backup (e.g. the one being restored)
        n += 1
        out = out_dir / f"hsc-companion-backup-{stamp}-{n}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "hsc_companion.db"
        _snapshot(db_path, snap)
        manifest = {"app": APP_ID, "format": FORMAT_VERSION, "created": datetime.now().isoformat(timespec="seconds"), "database": "hsc_companion.db"}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "hsc_companion.db")
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("settings.json", json.dumps(settings or {}, indent=2, default=str))
            if include_files:
                data_dir = db_path.parent
                for folder in FILE_FOLDERS:
                    for f in sorted((data_dir / folder).glob("*")) if (data_dir / folder).is_dir() else []:
                        if f.is_file():
                            z.write(f, f"{folder}/{f.name}")
    return out


def validate_backup(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if not {"manifest.json", "hsc_companion.db"} <= names:
            raise ValueError("Not an HSC Companion backup (manifest or database missing).")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("app") != APP_ID:
            raise ValueError("This backup was not made by HSC Companion.")
        with tempfile.TemporaryDirectory() as tmp:
            z.extract("hsc_companion.db", tmp)
            con = sqlite3.connect(str(Path(tmp) / "hsc_companion.db"))
            try:
                ok = con.execute("PRAGMA integrity_check").fetchone()[0]
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                con.close()
            if ok != "ok" or "questions" not in tables or "attempts" not in tables:
                raise ValueError("The database inside the backup is damaged or incomplete.")
    return manifest


def restore_backup(path: Path, db_path: Path | None = None) -> Path:
    """Returns the path of the safety backup taken before restoring."""
    from app.db import get_engine, init_engine

    db_path = db_path or config.db_path
    validate_backup(path)
    safety = create_backup(db_path, config.backups_dir) if db_path.exists() else None
    get_engine().dispose()
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as tmp:
        z.extract("hsc_companion.db", tmp)
        _snapshot(Path(tmp) / "hsc_companion.db", db_path)
        # restore imported PDFs/renders; only plain file names inside the known folders (no zip-slip)
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 2 and parts[0] in FILE_FOLDERS and parts[1] and parts[1] not in (".", "..") and "\\" not in parts[1]:
                target = db_path.parent / parts[0] / parts[1]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
    init_engine(f"sqlite:///{db_path}")
    from app.database_setup import upgrade

    upgrade(f"sqlite:///{db_path}")  # bring older backups up to the current schema
    return safety


def attempts_csv(db: Session) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "subject", "question_id", "source", "question_number", "marks_awarded", "marks_possible", "attempt", "skipped",
                "confidence", "seconds", "marking_method"])
    subjects = {s.id: s.name for s in db.execute(select(Subject)).scalars()}
    for a, q in db.execute(select(Attempt, Question).join(Question, Attempt.question_id == Question.id).order_by(Attempt.submitted_at)).all():
        w.writerow([a.submitted_at.isoformat(timespec="seconds"), subjects[q.subject_id], q.id, q.source.title, q.question_number or "",
                    a.mark_awarded, a.mark_possible, a.attempt_number, a.skipped, a.confidence or "", a.time_seconds, a.marking_method])
    return buf.getvalue()


AUTO_PREFIX = "hsc-companion-auto-"
AUTO_KEEP = 14


def auto_backup(db_path: Path | None = None, out_dir: Path | None = None, today: str | None = None) -> Path | None:
    """Once per day, keep a dated safety copy (the 14 most recent are kept). Returns the new
    backup path, or None if today's already exists or there is no database yet."""
    db_path = db_path or config.db_path
    out_dir = out_dir or config.backups_dir
    if not db_path.exists():
        return None
    today = today or datetime.now().strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.glob(f"{AUTO_PREFIX}{today}*.zip")):
        return None
    made = create_backup(db_path, out_dir, include_files=False)
    target = out_dir / f"{AUTO_PREFIX}{today}.zip"
    made.rename(target)
    autos = sorted(out_dir.glob(f"{AUTO_PREFIX}*.zip"))
    for old in autos[:-AUTO_KEEP]:
        old.unlink(missing_ok=True)
    return target
