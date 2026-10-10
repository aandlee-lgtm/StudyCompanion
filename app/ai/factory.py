from __future__ import annotations

import os

from app.ai.base import AIError, AIProvider
from app.ai.offline import OfflineProvider
from app.config import config

_test_provider: AIProvider | None = None


def set_test_provider(p: AIProvider | None) -> None:
    """Tests inject a fake provider here."""
    global _test_provider
    _test_provider = p


def get_provider(settings: dict | None = None) -> AIProvider:
    if _test_provider is not None:
        return _test_provider
    settings = settings or {}
    kind = (settings.get("ai_provider_override") or config.ai_provider or "offline").lower()
    model = settings.get("ai_model_override") or config.ai_model
    if kind == "openai":
        try:
            from app.ai.openai_compat import OpenAICompatibleProvider

            return OpenAICompatibleProvider(model=model, base_url=config.openai_base_url)
        except AIError:
            return OfflineProvider(reason="OPENAI_API_KEY is not set")
    return OfflineProvider()


def status(settings: dict | None = None) -> dict:
    p = get_provider(settings)
    return {
        "provider": p.name,
        "generative": p.generative,
        "model": getattr(p, "model", None),
        "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "reason": getattr(p, "reason", None),
    }
