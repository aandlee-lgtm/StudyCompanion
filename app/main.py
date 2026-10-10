"""FastAPI application factory."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_DIR, config
from app.database_setup import prepare_database

log = logging.getLogger("hsc")


def create_app(database_url: str | None = None, seed: bool = True) -> FastAPI:
    prepare_database(database_url, seed=seed)
    app = FastAPI(title="HSC Companion 2027", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    config.renders_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=config.renders_dir), name="media")

    from app.routes import api, attempts, curriculum, dashboard, errors, legal, practice, progress, questions, review, settings_routes, setup, today

    for module in (dashboard, setup, today, practice, attempts, api, review, progress, errors, curriculum, questions, legal, settings_routes):
        app.include_router(module.router)

    @app.middleware("http")
    async def first_run_redirect(request: Request, call_next):
        path = request.url.path
        if not path.startswith(("/setup", "/static", "/media", "/api", "/backup")):
            from app.db import SessionLocal
            from app.services import settings as st

            db = SessionLocal()
            try:
                done = st.get(db, "setup_complete")
            finally:
                db.close()
            if not done:
                return RedirectResponse("/setup", status_code=303)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        from app.routes.common import render_error

        return render_error(request, str(exc))

    return app
