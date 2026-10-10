"""Create/upgrade the database and (re)apply seed data. Safe to run repeatedly.

    python scripts/seed_syllabus.py
"""
import _bootstrap  # noqa: F401

from app.config import config
from app.database_setup import prepare_database

if __name__ == "__main__":
    prepare_database(seed=True)
    print(f"Database ready at {config.db_path}")
