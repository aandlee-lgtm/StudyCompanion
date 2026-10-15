"""Choose the AI provider: 'anthropic' (Claude), 'openai' (any OpenAI-compatible API) or
'offline'. Selected by HSC_AI_PROVIDER in .env, or overridden in Settings."""
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


def _model(settings: dict, kind: str) -> str | None:
    model = settings.get("ai_model_override") or config.ai_model
    if kind == "anthropic" and model and not model.startswith("claude"):
        return None  # an OpenAI model name left in .env: use the Anthropic default instead
    if kind == "openai" and model and model.startswith("claude"):
        return "gpt-4o"
    return model


def get_provider(settings: dict | None = None) -> AIProvider:
    if _test_provider is not None:
        return _test_provider
    settings = settings or {}
    kind = (settings.get("ai_provider_override") or config.ai_provider or "offline").lower()
    if kind == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider, credentials_present

        if not credentials_present():
            return OfflineProvider(reason="ANTHROPIC_API_KEY is not set")
        try:
            return AnthropicProvider(model=_model(settings, kind), effort=settings.get("ai_effort") or "high")
        except AIError as exc:
            return OfflineProvider(reason=str(exc))
    if kind == "claude_code":  # the student's Claude subscription, via Claude Code on this Mac
        from app.ai.claude_code_provider import ClaudeCodeProvider

        try:
            return ClaudeCodeProvider()
        except AIError as exc:
            return OfflineProvider(reason=str(exc))
    if kind == "openai":
        try:
            from app.ai.openai_compat import OpenAICompatibleProvider

            return OpenAICompatibleProvider(model=_model(settings, kind) or "gpt-4o", base_url=config.openai_base_url)
        except AIError:
            return OfflineProvider(reason="OPENAI_API_KEY is not set")
    return OfflineProvider()


def status(settings: dict | None = None) -> dict:
    settings = settings or {}
    p = get_provider(settings)
    kind = (settings.get("ai_provider_override") or config.ai_provider or "offline").lower()
    key_present = {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "claude_code": True,  # no key: uses the Claude Code sign-in
    }.get(kind, False)
    return {
        "provider": p.name,
        "configured": kind,
        "generative": p.generative,
        "model": getattr(p, "model", None),
        "api_key_present": key_present,
        "reason": getattr(p, "reason", None),
    }
