"""Back up or restore the database.

    python scripts/backup.py                 # create data/backups/hsc-companion-backup-<time>.zip
    python scripts/backup.py --out ~/Dropbox # create it somewhere else (recommended: outside the project)
    python scripts/backup.py --restore file.zip
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from app.config import config
from app.database_setup import prepare_database
from app.db import session_scope
from app.services import backup
from app.services import settings as st


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--restore", type=Path)
    a = ap.parse_args()
    prepare_database(seed=False)
    if a.restore:
        safety = backup.restore_backup(a.restore)
        print(f"Restored {a.restore}. Previous data saved as {safety}.")
        return
    with session_scope() as db:
        s = st.all_settings(db)
    out = backup.create_backup(config.db_path, a.out, s)
    print(f"Backup written to {out}")


if __name__ == "__main__":
    main()
