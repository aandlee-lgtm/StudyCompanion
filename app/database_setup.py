"""Create/upgrade the database with Alembic and seed it."""
from __future__ import annotations

from alembic import command
from alembic.config import Config as AlembicConfig

from app.config import BASE_DIR, config
from app.db import get_engine, init_engine, session_scope


def alembic_config(url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade(url: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        cfg = alembic_config(url)
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def prepare_database(url: str | None = None, seed: bool = True) -> None:
    url = url or config.sqlalchemy_url
    config.ensure_dirs()
    init_engine(url)
    upgrade(url)
    if seed:
        from app.services.seed import seed_all

        with session_scope() as db:
            seed_all(db)
