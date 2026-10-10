"""Application configuration, loaded from environment variables (and .env if present).

API keys are only ever read from the environment; nothing secret is stored in the database
or in the source tree.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional: python-dotenv
    from dotenv import load_dotenv

    # The installed desktop app keeps its .env in the data folder (HSC_DATA_DIR); a source
    # checkout uses the project folder. Real environment variables always take precedence.
    if os.environ.get("HSC_DATA_DIR"):
        load_dotenv(Path(os.environ["HSC_DATA_DIR"]) / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover - dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("HSC_DATA_DIR", BASE_DIR / "data")).resolve())
    host: str = field(default_factory=lambda: os.environ.get("HSC_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("HSC_PORT", "8000")))
    ai_provider: str = field(default_factory=lambda: os.environ.get("HSC_AI_PROVIDER", "offline").lower())
    ai_model: str | None = field(default_factory=lambda: os.environ.get("HSC_AI_MODEL") or None)
    # Extra host names allowed in the Host header (only needed for deliberate LAN/tablet access).
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(
        h.strip().lower() for h in os.environ.get("HSC_ALLOWED_HOSTS", "").split(",") if h.strip()))
    openai_base_url: str = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    database_url: str | None = field(default_factory=lambda: os.environ.get("HSC_DATABASE_URL"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "hsc_companion.db"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or f"sqlite:///{self.db_path}"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    def resolve_data_file(self, stored: str | None) -> Path | None:
        """Find a stored PDF/render path even if the data folder moved (e.g. restored on another Mac)."""
        if not stored:
            return None
        p = Path(stored)
        if p.exists():
            return p
        for folder in (self.sources_dir, self.renders_dir):
            candidate = folder / p.name
            if candidate.exists():
                return candidate
        return None

    def api_key_present(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.backups_dir, self.sources_dir, self.renders_dir):
            d.mkdir(parents=True, exist_ok=True)


config = Config()
