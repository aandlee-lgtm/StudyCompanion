"""OpenAI-compatible chat-completions provider (OpenAI, gateways, local servers)."""
from __future__ import annotations

import base64
import os

import httpx

from app.ai.base import AIError, AIProvider


class OpenAICompatibleProvider(AIProvider):
    name = "openai"
    vision = True  # the server must support image input (e.g. gpt-4o); otherwise the request fails cleanly

    def __init__(self, model: str, base_url: str, api_key: str | None = None, timeout: float = 120.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise AIError("OPENAI_API_KEY is not set")

    def _complete(self, system: str, user: str, images: list[tuple[str, bytes]] | None = None) -> str:
        content: str | list[dict] = user
        if images:
            content = [{"type": "image_url", "image_url": {"url": f"data:{t};base64,{base64.b64encode(d).decode('ascii')}"}}
                       for t, d in images] + [{"type": "text", "text": user}]
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise AIError(f"AI request failed: {exc}") from exc
