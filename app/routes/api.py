"""Small JSON endpoints: health ping (platform) and maths preview (owner: maths)."""
from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from app.marking import maths as maths_marker

router = APIRouter()


@router.get("/api/ping")
def ping():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse("hsc-companion 2027")


@router.post("/api/math-preview")
def math_preview(text: str = Form("")):
    import sympy as sp

    raw = text.replace("+ C", "").replace("+C", "").replace("+ c", "")
    try:
        return JSONResponse({"ok": True, "latex": sp.latex(maths_marker.parse(raw))})
    except Exception:
        return JSONResponse({"ok": False, "message": "Keep typing… (e.g. 3x^2 - 2, sqrt(2)/2, e^(2x), 2pi/3)"})

