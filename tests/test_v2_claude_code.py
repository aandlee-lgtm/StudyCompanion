"""'Use my Claude subscription' provider: runs the local Claude Code program (faked here)."""
from __future__ import annotations

import json
import stat

import pytest

from app.ai.base import AIError
from app.ai.claude_code_provider import ClaudeCodeProvider, check
from app.ai.schemas import WorkingReading


def _fake(tmp_path, payload: dict, name="claude"):
    script = tmp_path / name
    script.write_text("#!/bin/sh\necho '" + json.dumps(payload).replace("'", "") + "'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_returns_result_text_and_validates_json(tmp_path):
    p = ClaudeCodeProvider(_fake(tmp_path, {"type": "result", "subtype": "success", "is_error": False,
                                            "result": '{"legible": true, "final_answer": "x = 3"}'}))
    r = p.complete_json("sys", "user", WorkingReading)
    assert r.final_answer == "x = 3"
    r2 = p.complete_json("sys", "user", WorkingReading, images=[("image/jpeg", b"\xff\xd8jpeg")])  # photos path
    assert r2.legible


def test_not_signed_in_and_limit_messages(tmp_path):
    p = ClaudeCodeProvider(_fake(tmp_path, {"subtype": "success", "is_error": True, "result": "Invalid API key · Please run /login"}))
    with pytest.raises(AIError, match="not signed in"):
        p._complete("s", "u")
    q = ClaudeCodeProvider(_fake(tmp_path, {"subtype": "success", "is_error": True, "result": "Claude usage limit reached"}, "c2"))
    with pytest.raises(AIError, match="usage limit"):
        q._complete("s", "u")


def test_missing_install_reports_cleanly(monkeypatch):
    monkeypatch.setattr("app.ai.claude_code_provider.find_claude", lambda: None)
    assert check()["installed"] is False
    with pytest.raises(AIError):
        ClaudeCodeProvider()


def test_factory_falls_back_offline_when_not_installed(monkeypatch):
    from app.ai import factory

    monkeypatch.setattr("app.ai.claude_code_provider.find_claude", lambda: None)
    p = factory.get_provider({"ai_provider_override": "claude_code"})
    assert p.name == "offline" and "not installed" in p.reason
