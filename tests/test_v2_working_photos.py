"""Photos of handwritten working: validation, storage, attaching to attempts, AI reading, backups."""
from __future__ import annotations

import io
import json
import zipfile

import pytest
from PIL import Image
from sqlalchemy import select

from app.ai import factory
from app.ai.offline import OfflineProvider
from app.models import Attempt, Question, WorkingPhoto
from app.services import working_photos as wp
from tests.fakes import FakeProvider


def _photo(size=(1200, 900), color=(240, 240, 235), fmt="JPEG", exif_orientation=None, mode="RGB") -> bytes:
    img = Image.new(mode, size, color if mode == "RGB" else (*color, 128))
    img.paste((20, 20, 20) if mode == "RGB" else (20, 20, 20, 255), (100, 100, 400, 140))  # a "line of writing"
    out = io.BytesIO()
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        exif[0x010F] = "Apple"  # camera make: must not survive
        kwargs["exif"] = exif
    img.save(out, fmt, **kwargs)
    return out.getvalue()


def _maths_q(db) -> Question:
    from app.models import LearningPlanItem, Subject

    return db.scalars(select(Question).join(LearningPlanItem, Question.plan_item_id == LearningPlanItem.id)
                      .join(Subject, LearningPlanItem.subject_id == Subject.id)
                      .where(Subject.code == "MATHS")).first()


# ------------------------------------------------------------------ normalise ---
def test_normalise_rotates_and_strips_metadata():
    jpeg, w, h = wp.normalise(_photo(exif_orientation=6))  # 6 = rotate 90°: a portrait page stored sideways
    img = Image.open(io.BytesIO(jpeg))
    assert img.format == "JPEG" and (w, h) == img.size == (900, 1200)
    assert not img.getexif()  # no camera/location metadata kept


def test_normalise_downsizes_and_flattens_transparency():
    jpeg, w, h = wp.normalise(_photo(size=(4000, 3000), fmt="PNG", mode="RGBA"))
    img = Image.open(io.BytesIO(jpeg))
    assert img.mode == "RGB" and max(img.size) == wp.STORE_EDGE and (w, h) == img.size


@pytest.mark.parametrize("data,needle", [
    (b"", "empty"),
    (b"%PDF-1.7 not an image", "isn't a photo"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "isn't a photo"),
    (b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64, "HEIC"),
])
def test_normalise_rejects_non_photos(data, needle, monkeypatch):
    monkeypatch.setattr(wp, "_convert_with_sips", lambda d: None)
    with pytest.raises(wp.PhotoError, match=needle):
        wp.normalise(data)


def test_normalise_rejects_tiny_and_oversized(monkeypatch):
    with pytest.raises(wp.PhotoError, match="too small"):
        wp.normalise(_photo(size=(30, 30)))
    monkeypatch.setattr(wp, "MAX_UPLOAD_BYTES", 1000)
    with pytest.raises(wp.PhotoError, match="larger than"):
        wp.normalise(_photo())


def test_decompression_bomb_refused(monkeypatch):
    monkeypatch.setattr(wp, "MAX_PIXELS", 100_000)
    with pytest.raises(wp.PhotoError, match="too large"):
        wp.normalise(_photo(size=(1000, 1000)))


def test_heic_converted_with_sips_when_available(monkeypatch):
    monkeypatch.setattr(wp, "_convert_with_sips", lambda d: _photo())
    jpeg, w, h = wp.normalise(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG" and (w, h) == (1200, 900)


# ------------------------------------------------------------------ routes ---
def test_upload_list_view_delete(client, db):
    q = _maths_q(db)
    r = client.post("/api/working-photos", data={"question_id": q.id},
                    files=[("files", ("page1.jpg", _photo(), "image/jpeg")), ("files", ("page2.png", _photo(fmt="PNG"), "image/png"))])
    assert r.status_code == 200, r.text
    photos = r.json()["photos"]
    assert [p["page"] for p in photos] == [1, 2] and not any(p["attached"] for p in photos)
    assert (wp.config.working_dir / db.get(WorkingPhoto, photos[0]["id"]).filename).exists()

    img = client.get(photos[0]["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"

    again = client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("page1.jpg", _photo(), "image/jpeg"))])
    assert len(again.json()["photos"]) == 2  # the same photo is not added twice

    listing = client.get(f"/api/working-photos?question_id={q.id}").json()
    assert len(listing["photos"]) == 2

    gone = client.delete(f"/api/working-photos/{photos[0]['id']}")
    assert gone.status_code == 200 and [p["id"] for p in gone.json()["photos"]] == [photos[1]["id"]]
    assert client.get(photos[0]["url"]).status_code == 404


def test_upload_reports_bad_files_and_limit(client, db):
    q = _maths_q(db)
    bad = client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert bad.status_code == 400 and "isn't a photo" in bad.json()["errors"][0]
    for i in range(wp.MAX_PHOTOS):
        client.post("/api/working-photos", data={"question_id": q.id},
                    files=[("files", (f"p{i}.jpg", _photo(color=(30 + 35 * i, 120, 200)), "image/jpeg"))])
    over = client.post("/api/working-photos", data={"question_id": q.id},
                       files=[("files", ("extra.jpg", _photo(color=(10, 200, 10)), "image/jpeg"))])
    assert "up to" in over.json()["errors"][0] and len(over.json()["photos"]) == wp.MAX_PHOTOS


def test_cross_site_upload_blocked(client, db):
    q = _maths_q(db)
    r = client.post("/api/working-photos", data={"question_id": q.id}, headers={"Sec-Fetch-Site": "cross-site"},
                    files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    assert r.status_code == 403


def test_photos_attach_to_submitted_attempt_and_are_kept(client, db):
    q = _maths_q(db)
    client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    a = Attempt(question_id=q.id, response_text="2", mark_possible=q.marks)
    db.add(a)
    db.flush()
    attached = wp.attach_pending(db, a)
    db.commit()
    assert len(attached) == 1 and wp.for_attempt(db, a.id)[0].id == attached[0].id
    assert wp.pending(db, q.id, None) == []
    r = client.delete(f"/api/working-photos/{attached[0].id}")
    assert r.status_code == 409


def test_read_needs_a_vision_provider(client, db):
    q = _maths_q(db)
    client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    factory.set_test_provider(OfflineProvider())
    r = client.post("/api/working-photos/read", data={"question_id": q.id})
    assert r.status_code == 409 and "Settings" in r.json()["error"]


def test_read_transcribes_with_ai(client, db):
    q = _maths_q(db)
    client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("p.jpg", _photo(size=(3000, 2000)), "image/jpeg"))])
    fake = FakeProvider(default={"legible": True, "final_answer": "x = 3", "working_text": "2x + 1 = 7\n2x = 6\nx = 3",
                                 "unclear": [], "notes": ""})
    factory.set_test_provider(fake)
    r = client.post("/api/working-photos/read", data={"question_id": q.id})
    assert r.status_code == 200, r.text
    assert r.json()["reading"]["final_answer"] == "x = 3"
    (media_type, data), = fake.images[0]
    assert media_type == "image/jpeg" and max(Image.open(io.BytesIO(data)).size) == wp.SEND_EDGE
    assert "Do not solve the question" in fake.prompts[0] and q.question_text[:40] in fake.prompts[0]
    db.expire_all()
    assert wp.pending(db, q.id, None)[0].reading["final_answer"] == "x = 3"


def test_read_rejects_invalid_ai_output(client, db):
    q = _maths_q(db)
    client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    factory.set_test_provider(FakeProvider(replies=["not json", "still not json"]))
    r = client.post("/api/working-photos/read", data={"question_id": q.id})
    assert r.status_code == 502


def test_marking_with_images_sends_photos_and_instructions():
    from tests.fakes import marking_json

    fake = FakeProvider(replies=[marking_json(mark=2, possible=3)])
    ctx = {"question": "Solve 2x + 1 = 7", "response": "x = 4", "subject": "MATHS", "subject_name": "Mathematics Advanced",
           "marks": 3, "model_answer": "x = 3"}
    res = fake.mark_response(ctx, images=[("image/jpeg", b"jpegbytes")])
    assert res.mark_awarded == 2 and fake.images[0] == [("image/jpeg", b"jpegbytes")]
    assert "photo(s) of handwriting" in fake.prompts[0]


def test_text_only_provider_refuses_images():
    from app.ai.base import AIUnavailable

    class TextOnly(FakeProvider):
        vision = False

    with pytest.raises(AIUnavailable):
        TextOnly(default={}).read_working({"question": "q"}, [("image/jpeg", b"x")])


# ------------------------------------------------------------------ backups ---
def test_backup_includes_and_restores_photos(client, db, data_dir):
    from app.services.backup import create_backup, restore_backup

    q = _maths_q(db)
    client.post("/api/working-photos", data={"question_id": q.id}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    photo = wp.pending(db, q.id, None)[0]
    path = wp.path_for(photo)
    original = path.read_bytes()
    db.close()
    backup = create_backup(db_path=data_dir / "test.db", out_dir=data_dir / "backups")
    with zipfile.ZipFile(backup) as z:
        assert f"working/{photo.filename}" in z.namelist()
    path.unlink()
    restore_backup(backup, db_path=data_dir / "test.db")
    assert path.read_bytes() == original


def test_reading_schema_limits():
    from app.ai.schemas import WorkingReading

    r = WorkingReading.model_validate({"part_answers": {f"p{i}": "x" * 900 for i in range(30)}, "final_answer": "1"})
    assert len(r.part_answers) == 12 and all(len(v) == 400 for v in r.part_answers.values())
    assert json.loads(r.model_dump_json())["final_answer"] == "1"


# ------------------------------------------------------------- answer flow ---
def _session_maths(client, db):
    import re
    r = client.get("/today", follow_redirects=True)
    for link in sorted(set(re.findall(r'href="(/session/\d+/q/\d+)"', r.text))):
        page = client.get(link).text
        if "data-photos" in page:
            qid = int(re.search(r'data-qid="(\d+)"', page).group(1))
            sq = re.search(r'data-sq="(\d*)"', page).group(1)
            return link, qid, sq
    pytest.skip("no maths question in today's session")


def test_photo_on_maths_question_is_kept_with_the_answer_and_shown(client, db):
    link, qid, sq = _session_maths(client, db)
    client.post("/api/working-photos", data={"question_id": qid, "sq_id": sq}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    r = client.post(link + "/submit", data={"answer": "12345", "working": "my steps", "confidence": "unsure", "time_seconds": "30"},
                    follow_redirects=True)
    assert r.status_code == 200
    db.expire_all()
    a = db.scalars(select(Attempt).where(Attempt.question_id == qid)).first()
    photos = wp.for_attempt(db, a.id)
    assert len(photos) == 1 and wp.pending_any(db, qid) == []
    page = client.get(link).text
    assert "Your working" in page and f"/working-photos/{photos[0].id}" in page and "my steps" in page


def test_photos_reach_ai_method_marking(client, db):
    from tests.fakes import marking_json

    link, qid, sq = _session_maths(client, db)
    q = db.get(Question, qid)
    if q.marks < 2:
        pytest.skip("1-mark question: no method marks")
    client.post("/api/working-photos", data={"question_id": qid, "sq_id": sq}, files=[("files", ("p.jpg", _photo(), "image/jpeg"))])
    fake = FakeProvider(default=json.loads(marking_json(mark=1, possible=q.marks)))
    factory.set_test_provider(fake)
    client.post(link + "/submit", data={"answer": "12345", "working": "", "confidence": "unsure", "time_seconds": "30"})
    assert any(imgs for imgs in fake.images), "the photo should be sent with the marking request"
