"""Template rendering and shared helpers for routes."""
from __future__ import annotations

import html
import re
from datetime import date, datetime

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.ai.factory import status as ai_status
from app.config import APP_DIR
from app.models.common import ORIGIN_LABELS

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

NAV = [("/", "Dashboard"), ("/today", "Today"), ("/review", "Revision"), ("/progress", "Progress"), ("/errors", "Error journal"),
       ("/curriculum", "Learning plan"), ("/questions", "Questions"), ("/legal-evidence", "Legal evidence"), ("/settings", "Settings")]
SUBJECT_NAMES = {"MATHS": "Mathematics Advanced", "ENGLISH": "English Advanced", "LEGAL": "Legal Studies"}
SUBJECT_SHORT = {"MATHS": "Maths", "ENGLISH": "English", "LEGAL": "Legal"}


def paras(text: str | None) -> Markup:
    """Escape, then turn blank-line-separated text into paragraphs and single newlines into <br>."""
    if not text:
        return Markup("")
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        out.append("<p>" + html.escape(block).replace("\n", "<br>") + "</p>")
    return Markup("\n".join(out))


def fmt_date(d: date | datetime | None, fmt: str = "%a %d %b %Y") -> str:
    return d.strftime(fmt) if d else "—"


def minutes(m: float | None) -> str:
    if m is None:
        return "—"
    m = round(m)
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


templates.env.filters.update(paras=paras, fdate=fmt_date, minutes=minutes)


def _answer_display(q):
    from app.services.assessment import answer_display

    return answer_display(q)


templates.env.globals['answer_display'] = _answer_display
templates.env.globals.update(NAV=NAV, SUBJECT_NAMES=SUBJECT_NAMES, SUBJECT_SHORT=SUBJECT_SHORT, ORIGIN_LABELS=ORIGIN_LABELS)


def _subject_codes() -> dict[int, str]:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Subject

    db = SessionLocal()
    try:
        return {s.id: s.code for s in db.execute(select(Subject)).scalars()}
    finally:
        db.close()


def render(request: Request, template_name: str, **ctx) -> HTMLResponse:
    ctx.setdefault("active", request.url.path)
    ctx.setdefault("codes", _subject_codes())
    ctx.setdefault("ai", ai_status())
    return templates.TemplateResponse(request, template_name, ctx)


def render_error(request: Request, message: str, status_code: int = 400) -> HTMLResponse:
    resp = render(request, "error.html", message=message)
    resp.status_code = status_code
    return resp
