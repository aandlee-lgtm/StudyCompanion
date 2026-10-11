"""Anthropic (Claude) provider, using the official `anthropic` Python SDK.

Credentials are resolved by the SDK from the environment (ANTHROPIC_API_KEY, or an
`ant auth login` profile) — never stored in the database or the source tree.

Defaults: model `claude-opus-5-5` (thinking is always on for this model; depth is set with
`output_config.effort`, which defaults to "high" here because marking is intelligence-sensitive),
and server-side refusal fallbacks (`fallbacks="default"`), so a request a safety classifier
declines is re-run on a fallback model inside the same call instead of failing."""
from __future__ import annotations

import base64
import logging
import os

from app.ai.base import AIError, AIProvider

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(AIProvider):
    name = "anthropic"
    vision = True

    def __init__(self, model: str | None = None, effort: str = "high", timeout: float = 600.0):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
            raise AIError("The 'anthropic' package is not installed") from exc
        self._sdk = anthropic
        self.model = model or DEFAULT_MODEL
        self.effort = effort
        try:
            self.client = anthropic.Anthropic(timeout=timeout, max_retries=2)
        except Exception as exc:  # no credentials resolvable
            raise AIError(f"Anthropic client could not be created: {exc}") from exc

    def _complete(self, system: str, user: str, images: list[tuple[str, bytes]] | None = None) -> str:
        sdk = self._sdk
        content: str | list[dict] = user
        if images:
            content = []
            for i, (media_type, data) in enumerate(images, 1):
                content.append({"type": "text", "text": f"Photo {i} of {len(images)}:"})
                content.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                            "data": base64.b64encode(data).decode("ascii")}})
            content.append({"type": "text", "text": user})
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": self.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except sdk.AuthenticationError as exc:
            raise AIError("The Anthropic API key was rejected (check ANTHROPIC_API_KEY)") from exc
        except sdk.NotFoundError as exc:
            raise AIError(f"Model '{self.model}' was not found") from exc
        except sdk.RateLimitError as exc:
            raise AIError("Rate limited by the Anthropic API; try again shortly") from exc
        except sdk.APIStatusError as exc:
            raise AIError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except sdk.APIConnectionError as exc:
            raise AIError("Could not reach the Anthropic API (network)") from exc
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise AIError(f"The model declined this request{f' ({category})' if category else ''}")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise AIError(f"Empty response (stop reason: {response.stop_reason})")
        return text


def credentials_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
