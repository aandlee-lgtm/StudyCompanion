"""The Anthropic provider: request shape, refusal handling and JSON validation (no network)."""
import json
from types import SimpleNamespace

import pytest

from app.ai.anthropic_provider import DEFAULT_MODEL, FALLBACK_BETA, AnthropicProvider
from app.ai.base import AIError
from tests.fakes import marking_json


class FakeMessages:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        return r


def make(replies, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    p = AnthropicProvider()
    fake = FakeMessages(replies)
    p.client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    return p, fake


def reply(text, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, stop_details=None, content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])


def test_marking_round_trip_and_request_shape(monkeypatch):
    p, fake = make([reply(marking_json(3, 4))], monkeypatch)
    r = p.mark_response({"subject": "ENGLISH", "subject_name": "English Advanced", "marks": 4, "question": "Q", "response": "R"})
    assert r.mark_awarded == 3
    call = fake.calls[0]
    assert call["model"] == DEFAULT_MODEL and call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["output_config"]["effort"] == "high" and "thinking" not in call


def test_refusal_raises_ai_error(monkeypatch):
    p, _ = make([reply("", stop="refusal")], monkeypatch)
    with pytest.raises(AIError):
        p._complete("s", "u")


def test_invalid_json_is_retried_then_rejected(monkeypatch):
    p, fake = make([reply("not json"), reply(json.dumps({"mark_awarded": 9, "mark_possible": 4}))], monkeypatch)
    with pytest.raises(AIError):
        p.mark_response({"subject": "ENGLISH", "subject_name": "English Advanced", "marks": 4, "question": "Q", "response": "R"})
    assert len(fake.calls) == 2


def test_factory_falls_back_to_offline_without_key(monkeypatch):
    from app.ai import factory

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    p = factory.get_provider({"ai_provider_override": "anthropic"})
    assert p.name == "offline" and "ANTHROPIC_API_KEY" in p.reason
