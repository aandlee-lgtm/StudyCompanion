"""Claude through the student's own Claude subscription, using the Claude Code program installed
on this Mac (``claude -p``). No API key: Claude Code uses the sign-in stored by ``claude`` itself,
and usage counts against the subscription's allowance.

Photos (working) are written to a private temporary folder and Claude Code is allowed to read only
that folder."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.ai.base import AIError, AIProvider

CANDIDATES = (
    "~/.local/bin/claude", "~/.claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude",
    "~/.npm-global/bin/claude", "~/.volta/bin/claude",
)


def find_claude() -> str | None:
    """Apps opened from Finder get a minimal PATH, so look in the usual install places too."""
    found = shutil.which("claude")
    if found:
        return found
    for c in CANDIDATES:
        p = Path(c).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


class ClaudeCodeProvider(AIProvider):
    name = "claude_code"
    vision = True
    model = "Claude (your subscription, via Claude Code)"

    def __init__(self, binary: str | None = None, timeout: float = 300.0):
        self.binary = binary or find_claude()
        if not self.binary:
            raise AIError("Claude Code is not installed on this Mac (see Settings → AI marking)")
        self.timeout = timeout

    def _run(self, prompt: str, extra: list[str], cwd: str | None = None) -> str:
        cmd = [self.binary, "-p", prompt, "--output-format", "json", *extra]
        env = {**os.environ, "PATH": os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}
        env.pop("ANTHROPIC_API_KEY", None)  # use the subscription sign-in, never an API key left in the environment
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, cwd=cwd, env=env)
        except subprocess.TimeoutExpired as exc:
            raise AIError("Claude took too long to answer; try again") from exc
        except OSError as exc:
            raise AIError(f"Claude Code could not be started: {exc}") from exc
        out = (proc.stdout or "").strip()
        try:
            data = json.loads(out)
        except ValueError:
            err = (proc.stderr or out or "no output").strip().splitlines()[-1:] or ["no output"]
            raise AIError(f"Claude Code failed: {err[0][:200]}")
        if data.get("is_error") or data.get("subtype", "success") != "success":
            msg = str(data.get("result") or data.get("subtype") or "error")
            if "login" in msg.lower() or "auth" in msg.lower():
                msg = "Claude Code is not signed in — open Terminal, run 'claude' and log in with your Claude account"
            elif "limit" in msg.lower():
                msg = "Your Claude subscription's usage limit has been reached; the app will mark offline until it resets"
            raise AIError(msg[:300])
        text = data.get("result") or ""
        if not str(text).strip():
            raise AIError("Claude Code returned an empty answer")
        return str(text)

    def _complete(self, system: str, user: str, images: list[tuple[str, bytes]] | None = None) -> str:
        prompt = f"{system}\n\n{user}"
        if not images:
            return self._run(prompt, ["--max-turns", "1", "--disallowedTools", "Bash,Edit,Write,WebFetch,WebSearch,Read,Glob,Grep"])
        with tempfile.TemporaryDirectory(prefix="hsc-photos-") as tmp:
            names = []
            for i, (media_type, data) in enumerate(images, 1):
                ext = ".png" if "png" in media_type else ".jpg"
                f = Path(tmp) / f"photo{i}{ext}"
                f.write_bytes(data)
                names.append(str(f))
            prompt += ("\n\nThe student's photos are these image files, in order (read each one with the Read tool before answering): "
                       + ", ".join(names))
            return self._run(prompt, ["--max-turns", str(len(names) + 2), "--allowedTools", "Read", "--add-dir", tmp,
                                      "--disallowedTools", "Bash,Edit,Write,WebFetch,WebSearch"], cwd=tmp)


def check(binary: str | None = None) -> dict:
    """For Settings: is Claude Code installed and signed in? Sends one tiny request."""
    path = binary or find_claude()
    if not path:
        return {"ok": False, "installed": False, "message": "Claude Code was not found on this Mac."}
    try:
        reply = ClaudeCodeProvider(path, timeout=120)._complete("Reply with exactly: OK", "Say OK.")
    except AIError as exc:
        return {"ok": False, "installed": True, "path": path, "message": str(exc)}
    return {"ok": True, "installed": True, "path": path, "message": f"Connected — Claude replied: {reply.strip()[:40]}"}
