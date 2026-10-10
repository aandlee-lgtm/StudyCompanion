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
