"""Local-app protections: Host header (DNS rebinding) and cross-site requests (CSRF)."""


def test_cross_site_post_is_blocked(client):
    r = client.post("/settings", data={"timezone": "UTC"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/settings", data={"timezone": "UTC"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_same_origin_post_is_allowed(client):
    r = client.post("/settings", data={"timezone": "Australia/Sydney"}, headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
                    follow_redirects=False)
    assert r.status_code == 303


def test_foreign_host_header_is_rejected(client):
    r = client.get("/", headers={"Host": "attacker.example:8000"})
    assert r.status_code == 400


def test_security_headers_present(client):
    r = client.get("/setup")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_wizard_sets_each_english_module_independently(db, client):
    from tests.conftest import plan_item

    the, tc, csl = plan_item(db, "EN-THE"), plan_item(db, "EN-TC"), plan_item(db, "EN-CSL")
    r = client.post("/setup", data={f"english_{the.id}": "LEARNED", f"english_{tc.id}": "LEARNING", f"english_{csl.id}": "LOCKED"},
                    follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    assert (plan_item(db, "EN-THE").status, plan_item(db, "EN-TC").status, plan_item(db, "EN-CSL").status) == ("LEARNED", "LEARNING", "LOCKED")


def test_every_state_changing_route_is_covered_by_the_csrf_middleware(client):
    """Integration check: every POST/PUT/PATCH/DELETE route of every package (swap, follow-up, English
    self-mark, Legal topics and evidence, working photos, ...) is refused cross-site."""
    import re

    unsafe = {"POST", "PUT", "PATCH", "DELETE"}

    def walk(items):  # FastAPI nests included routers (``original_router``)
        for r in items:
            inner = getattr(r, "original_router", None)
            if inner is not None:
                yield from walk(inner.routes)
            elif getattr(r, "methods", None):
                yield r

    routes = [r for r in walk(client.app.routes) if r.methods & unsafe]
    assert len(routes) > 30
    paths = {r.path for r in routes}
    for expected in ("/session/{sid}/q/{pos}/swap", "/attempt/{aid}/followup", "/english/attempt/{aid}/self-mark"):
        assert any(p.replace(" ", "") == expected or re.sub(r"\{[^}]+\}", "{}", p) == re.sub(r"\{[^}]+\}", "{}", expected)
                   for p in paths), expected
    for r in routes:
        path = re.sub(r"\{[^}]+\}", "1", r.path)
        for method in sorted((r.methods or set()) & unsafe):
            for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}):
                resp = client.request(method, path, headers=headers)
                assert resp.status_code == 403, (method, r.path, headers, resp.status_code)
