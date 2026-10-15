"""Small JSON endpoints: health ping (platform) and maths preview (owner: maths)."""
from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from app.marking import maths as maths_marker

router = APIRouter()

PREVIEW_KINDS = {"num", "expr", "antiderivative", "set", "interval", "mcq", "parts"}


@router.get("/api/ping")
def ping():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse("hsc-companion 2027")


@router.post("/api/math-preview")
def math_preview(text: str = Form(""), kind: str = Form("expr"), var: str = Form("x")):
    """How a typed answer will be read, as LaTeX. Uses the locked-down parser (length-capped, no
    evaluation of names outside the whitelist) and never raises."""
    kind = kind if kind in PREVIEW_KINDS else "expr"
    var = var if var in ("x", "n", "t", "k") else "x"
    out = maths_marker.preview((text or "")[:maths_marker.MAX_RESPONSE_CHARS + 1], kind, var=var)
    if not out.get("ok") and not out.get("message"):
        out["message"] = "Keep typing… (e.g. 3x^2 - 2, sqrt(2)/2, e^(2x), 2pi/3)" if (text or "").strip() else ""
    return JSONResponse(out)


@router.post("/api/ai-test")
def ai_test():
    """Settings → Test connection: mark a tiny request with the configured provider."""
    from app.ai.factory import get_provider
    from app.db import SessionLocal
    from app.services import settings as st

    db = SessionLocal()
    try:
        settings = st.all_settings(db)
    finally:
        db.close()
    kind = (settings.get("ai_provider_override") or "").lower()
    if kind == "claude_code":
        from app.ai.claude_code_provider import check

        return JSONResponse(check())
    p = get_provider(settings)
    if not p.generative:
        return JSONResponse({"ok": False, "message": f"No AI provider is active ({getattr(p, 'reason', 'offline')})."})
    try:
        reply = p._complete("Reply with exactly: OK", "Say OK.")
    except Exception as exc:  # noqa: BLE001 - shown to the student
        return JSONResponse({"ok": False, "message": str(exc)[:300]})
    return JSONResponse({"ok": True, "message": f"Connected to {p.name} — reply: {reply.strip()[:40]}"})
