"""Protection for a web app that lives on the student's own computer.

Any website the student visits could otherwise send requests to http://127.0.0.1:8000:
- cross-site form posts (CSRF) that change settings, restore a backup or submit answers;
- DNS-rebinding, where a hostile domain resolves to 127.0.0.1 and reads pages.

Rules: the Host header must name this computer (or a host explicitly allowed for LAN use), and
state-changing requests must come from this app's own pages (Sec-Fetch-Site / Origin / Referer).
Requests without any of those headers (scripts, tests) are allowed; browsers always send them."""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.config import config

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _hostname(netloc: str) -> str:
    netloc = (netloc or "").strip().lower()
    if netloc.startswith("["):
        return netloc.split("]")[0] + "]"
    return netloc.rsplit(":", 1)[0] if netloc.count(":") == 1 else netloc


def host_allowed(host_header: str) -> bool:
    host = _hostname(host_header)
    allowed = LOCAL_HOSTS | set(config.allowed_hosts)
    if config.host not in ("127.0.0.1", "localhost", "0.0.0.0", "::"):
        allowed.add(config.host.lower())
    return host in allowed


def same_origin(request: Request) -> bool:
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site in ("same-origin", "none")
    host = request.headers.get("host", "")
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            if value == "null":
                return False
            return urlsplit(value).netloc.lower() == host.lower()
    return True  # non-browser client


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not host_allowed(request.headers.get("host", "")):
            return PlainTextResponse("This address is not allowed. Open the app at http://127.0.0.1:8000", status_code=400)
        if request.method in UNSAFE_METHODS and not same_origin(request):
            return PlainTextResponse("Request blocked: it did not come from HSC Companion's own pages.", status_code=403)
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response
