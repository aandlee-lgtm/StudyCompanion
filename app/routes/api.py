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
