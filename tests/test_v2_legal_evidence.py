"""v2 legal-logic: evidence bank structure, edit form, verification dialog and history (legal-18/19)."""
from __future__ import annotations

from sqlalchemy import select

from app.models import LegalEvidence
from app.models.legal_logic import LegalEvidenceCheck
from app.services import clock
from app.services import legal_evidence as le


def _item(db, title="Bail Act 2013 (NSW)"):
    return db.execute(select(LegalEvidence).where(LegalEvidence.title == title)).scalar_one()


def test_classify_source_uses_dot_boundaries():
    assert le.classify_source("https://www.legislation.nsw.gov.au/view/html/inforce/current/act-2013-026") == ("primary", "high")
    assert le.classify_source("https://legislation.gov.au.example.com/x")[0] != "primary"
    assert le.classify_source("https://fakeun.org/report") == ("commentary", "unrated")
    assert le.classify_source("https://www.abc.net.au/news")[0] == "journalism"


def test_bank_page_grouped_with_counts_and_filters(db, client):
    page = client.get("/legal-evidence")
    assert page.status_code == 200
    assert "needs verification" in page.text and "re-check due" in page.text
    assert "The nature and development of human rights" in page.text or "Promoting and enforcing human rights" in page.text
    assert "law reform" in page.text  # every type is listed with its count, even an empty one
    only = client.get("/legal-evidence?state=verified")
    assert "No items match." in only.text  # nothing is verified on a fresh install
    assert client.get("/legal-evidence/999999").status_code == 404
    assert client.post("/legal-evidence/999999/delete").status_code == 404


def test_verification_dialog_requires_every_check_and_records_history(db, client):
    ev = _item(db)
    page = client.get(f"/legal-evidence/{ev.id}")
    assert page.status_code == 200 and "Verify against the source" in page.text and "Version you read" in page.text
    r = client.post(f"/legal-evidence/{ev.id}/verify", data={"title_year": 1, "jurisdiction": 1}, follow_redirects=False)
    assert "Confirm%20every%20point" in r.headers["location"]
    r = client.post(f"/legal-evidence/{ev.id}/verify", data={"title_year": 1, "jurisdiction": 1, "summary": 1, "current": 1},
                    follow_redirects=False)
    assert "as%20at" in r.headers["location"]  # legislation needs the version read
    db.expire_all()
    assert _item(db).last_verified_date is None
    r = client.post(f"/legal-evidence/{ev.id}/verify", data={"title_year": 1, "jurisdiction": 1, "summary": 1, "current": 1,
                                                             "version_as_at": "as at 1 Oct 2026", "note": "s 17 checked",
                                                             "corrected_summary": "Corrected summary of the Act."}, follow_redirects=False)
    assert "Verified" in r.headers["location"]
    db.expire_all()
    ev = _item(db)
    assert ev.last_verified_date == clock.today() and ev.version_as_at == "as at 1 Oct 2026" and ev.summary == "Corrected summary of the Act."
    hist = db.execute(select(LegalEvidenceCheck).where(LegalEvidenceCheck.evidence_id == ev.id)).scalars().all()
    assert len(hist) == 1 and hist[0].summary_corrected and hist[0].note == "s 17 checked" and all(hist[0].checklist.values())
    assert "Verification history" in client.get(f"/legal-evidence/{ev.id}").text
    assert "verified" in client.get("/legal-evidence?state=verified").text and ev.title in client.get("/legal-evidence?state=verified").text


def test_edit_form_updates_structure_and_resets_verification_when_facts_change(db, client):
    ev = _item(db)
    le.mark_verified(db, ev)
    db.commit()
    data = {"title": ev.title, "item_type": "legislation", "date": ev.date or "2013", "jurisdiction": ev.jurisdiction, "issue": "Bail",
            "summary": ev.summary, "source": ev.source, "source_url": ev.source_url or "", "status": "in_force",
            "sub_area": "LS-CRIME-INVESTIGATION", "aliases": "Bail Act, NSW Bail Act", "issue_tags": "bail, remand"}
    r = client.post(f"/legal-evidence/{ev.id}/edit", data=data, follow_redirects=False)
    assert r.status_code == 303 and "Saved" in r.headers["location"] and "verifying%20again" not in r.headers["location"]
    db.expire_all()
    ev = _item(db)
    assert ev.aliases == ["Bail Act", "NSW Bail Act"] and ev.issue_tags == ["bail", "remand"] and ev.last_verified_date is not None
    r = client.post(f"/legal-evidence/{ev.id}/edit", data={**data, "summary": "A changed summary."}, follow_redirects=False)
    assert "verifying%20again" in r.headers["location"]
    db.expire_all()
    assert _item(db).last_verified_date is None
    r = client.post(f"/legal-evidence/{ev.id}/edit", data={**data, "title": "  "}, follow_redirects=False)
    assert "cannot%20be%20empty" in r.headers["location"]
    # deleting keeps nothing behind, including the history
    eid = ev.id
    client.post(f"/legal-evidence/{eid}/delete")
    db.expire_all()
    assert db.execute(select(LegalEvidence).where(LegalEvidence.id == eid)).scalar_one_or_none() is None
    assert not db.execute(select(LegalEvidenceCheck).where(LegalEvidenceCheck.evidence_id == eid)).scalars().all()


def test_add_form_with_structure_and_check(db, client):
    # (an item the seeded bank does not have yet: the merged v2 content already includes the Queensland Act)
    form = {"title": "Disability Discrimination Act 1992 (Cth)", "item_type": "legislation", "date": "1992",
            "jurisdiction": "Commonwealth", "summary": "Commonwealth anti-discrimination statute.",
            "aliases": "Disability Discrimination Act", "status": "in_force", "sub_area": "LS-HR-ENFORCE",
            "version_as_at": "as at 1 Oct 2026", "verified": 1}
    r = client.post("/legal-evidence/add", data=form, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    ev = _item(db, "Disability Discrimination Act 1992 (Cth)")
    assert ev.aliases == ["Disability Discrimination Act"] and ev.status == "in_force" and ev.sub_area == "LS-HR-ENFORCE"
    assert ev.last_verified_date == clock.today() and len(le.history(db, ev)) == 1
    # adding the same title again is refused (citations are matched by exact title)
    r = client.post("/legal-evidence/add", data={**form, "title": "disability discrimination act 1992 (cth)"}, follow_redirects=False)
    assert r.status_code == 400 and "already in the evidence bank" in r.text
    db.expire_all()
    assert len(db.execute(select(LegalEvidence).where(LegalEvidence.title.ilike("disability discrimination act 1992%"))).scalars().all()) == 1


def test_recheck_due_notice_and_currency_line_helpers(db, client):
    from datetime import timedelta

    from app.models import Question, Subject
    from app.routes.legal import legal_currency_line, legal_evidence_due

    ev = _item(db)
    le.mark_verified(db, ev, clock.today() - timedelta(days=200))  # legislation re-check interval is 90 days
    db.commit()
    assert legal_evidence_due() == 1
    assert "1 item due for re-check" in client.get("/").text
    leg = db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()
    q = next(q for q in db.execute(select(Question).where(Question.subject_id == leg.id)).scalars()
             if q.model_answer and "Bail Act 2013" in q.model_answer)
    line = legal_currency_line(q.id)
    assert line.startswith("Current information checked") and "re-check due: Bail Act 2013 (NSW)" in line
    assert legal_currency_line(None) == ""
