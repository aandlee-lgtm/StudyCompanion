"""Guided self-marking, deterministic checks, AI provenance and why-lost ladders for English (english-logic)."""
import json

from sqlalchemy import select

from app.ai import factory
from app.models import Attempt, ErrorJournal, Question
from app.services import assessment
from app.services.assessment import english
from tests.fakes import FakeProvider, marking_json

FERRY_Q = "Explain how the narrator's response to the comment about the wharf reveals their relationship with their mother."
STRONG = ("The narrator agrees that the wharf 'looked brighter' although 'They had not' painted it. Agreeing was 'easier than asking what "
          "else she was remembering wrongly', which shows a protective relationship: the narrator shields the mother while privately "
          "fearing how far her memory lapses extend.")
OFF_TOPIC = ("Hamlet's soliloquy shows his paralysis and indecision about revenge and mortality, and his grief for his father makes him "
             "delay, which the audience finds frustrating but very human throughout the play.")


def _q(db, text=FERRY_Q):
    return db.execute(select(Question).where(Question.question_text == text)).scalar_one()


def _paired_compare(db):
    return next(q for q in db.execute(select(Question).where(Question.category == "unseen")).scalars()
                if q.stimulus and len(q.stimulus.reading_set()) > 1 and (q.directive_verb or "").lower() == "compare")


def test_offline_submission_waits_for_guided_self_marking(db):
    q = _q(db)
    a = assessment.submit(db, q, STRONG)
    p = a.feedback.payload
    assert p["pending_mark"] and p["guided"] and a.mark_awarded == 0
    assert p["english"]["checklist"] == q.solution["checklist"]
    assert p["english"]["checks"]["quote_summary"]["verified"] == 3 and p["english"]["checks"]["cap"] is None
    assert "Not marked yet" in p["label"] and p["model_answer_source"].startswith("Written for this question by HSC Companion")
    assert not db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).scalars().all()
    assert "Mark your answer first" in english.why_lost(q, p, a)


def test_mark_is_derived_from_ticks(db):
    q = _q(db)  # 2 marks, 3 checklist items
    a = assessment.submit(db, q, STRONG)
    g = english.apply_guided_self_mark(db, a, [0, 1, 2])
    assert g["final"] == 2 and a.mark_awarded == 2
    p = a.feedback.payload
    assert p["self_marked"] and not p["pending_mark"] and p["english"]["self"]["ticked"] == [0, 1, 2]
    assert [r["n"] for r in p["english"]["elements"]] == list(range(1, 19))
    assert p["english"]["elements"][0]["value"].startswith("2 / 2")
    g = english.apply_guided_self_mark(db, a, [0])  # changing the ticks changes the mark
    assert g["final"] == 1 and a.mark_awarded == 1
    assert a.marking_method == "self"


def test_unticked_items_go_to_the_journal_with_their_own_description(db):
    q = _q(db)
    a = assessment.submit(db, q, STRONG)
    english.apply_guided_self_mark(db, a, [0, 1])
    db.flush()
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).scalars().all()
    assert rows and all(r.description.startswith("Not yet in your answer:") for r in rows)
    assert q.solution["checklist"][2] in rows[0].description


def test_caps_cannot_be_ticked_away(db):
    q = _q(db)
    a = assessment.submit(db, q, OFF_TOPIC)
    ck = a.feedback.payload["english"]["checks"]
    codes = {w["code"] for w in ck["warnings"]}
    assert {"no_evidence", "off_text"} <= codes and ck["cap"] == 1
    g = english.apply_guided_self_mark(db, a, [0, 1, 2])
    assert g["raw"] == 2 and g["final"] == 1 and g["cap_reasons"]


def test_misquotation_is_flagged_with_the_real_wording(db):
    q = _q(db)
    a = assessment.submit(db, q, "The narrator says the wharf 'looked much brighter', which shows they protect their mother from the truth.")
    ck = a.feedback.payload["english"]["checks"]
    assert ck["quote_summary"]["unverified"] == 1
    bad = [s for s in ck["segments"] if s.get("q") == "bad"]
    assert bad and bad[0]["t"] == "looked much brighter"
    assert any(w["code"] == "misquote" for w in ck["warnings"])


def test_comparison_with_one_text_is_capped(db):
    q = _paired_compare(db)
    first = q.stimulus.reading_set()[0].body
    phrase = " ".join(first.split()[3:8])
    a = assessment.submit(db, q, f"Text 1 shows '{phrase}', which suggests the city hides its labour. " * 3)
    ck = a.feedback.payload["english"]["checks"]
    assert any(w["code"] == "one_text" for w in ck["warnings"]) and ck["cap"] <= q.marks // 2


def test_self_mark_route_and_preview(client, db):
    q = _q(db)
    a = assessment.submit(db, q, STRONG)
    db.commit()
    r = client.post(f"/english/attempt/{a.id}/self-mark/preview", data={"tick": ["0", "1"]})
    assert r.status_code == 200 and r.json()["mark"] == 1
    r = client.post(f"/english/attempt/{a.id}/self-mark", data={"tick": ["0", "1", "2"], "back": f"/practice/{q.id}#feedback"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/practice/{q.id}#feedback"
    db.expire_all()
    assert db.get(Attempt, a.id).mark_awarded == 2
    r = client.post(f"/english/attempt/{a.id}/self-mark", data={"tick": ["0"], "back": "https://evil.example"}, follow_redirects=False)
    assert r.headers["location"].startswith("/practice/")


def test_feedback_page_shows_guided_marking_then_18_elements(client, db):
    q = _q(db)
    client.post(f"/practice/{q.id}/submit", data={"answer": STRONG, "time_seconds": "60"})
    html = client.get(f"/practice/{q.id}").text
    assert "Mark your answer" in html and 'name="tick"' in html and "looked brighter" in html
    a = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    client.post(f"/english/attempt/{a.id}/self-mark", data={"tick": ["0", "1"], "back": f"/practice/{q.id}"})
    html = client.get(f"/practice/{q.id}").text
    for title in ("Mark awarded", "Relevant criteria", "Quality of textual evidence", "Sophistication of interpretation", "Concrete actions"):
        assert title in html
    assert "Not assessed offline" in html and "Self-marked" in html


def test_why_lost_uses_the_question_ladder_and_next_step(db):
    q = _q(db)
    a = assessment.submit(db, q, STRONG)
    english.apply_guided_self_mark(db, a, [0])
    text = english.why_lost(q, a.feedback.payload, a)
    assert "1-mark level" in text and q.solution["next_steps"]["1"] in text
    assert "2 marks" in text and "\n\n" in text


def test_ai_marking_keeps_the_vetted_model_and_whole_marks(db):
    q = _q(db)
    reply = json.loads(marking_json(1.5, 2, model_answer="A brand new AI model answer that should never replace the vetted one."))
    reply["errors"] = [{"category": "Analysis lacks depth", "description": "Names the reason without explaining it"}]
    p = FakeProvider(default=reply)
    factory.set_test_provider(p)
    a = assessment.submit(db, q, STRONG)
    fb = a.feedback.payload
    assert a.mark_awarded == 2.0  # 1.5 -> whole marks
    assert fb["model_answer"] == q.model_answer and "HSC Companion" in fb["model_answer_source"]
    assert "REFERENCE BAND 6 RESPONSE" in p.prompts[0] and "WHAT A STRONG ANSWER" in p.prompts[0] and "MARK-SCALING" in p.prompts[0]
    assert "whole marks" in p.prompts[0].lower() and '"outcomes": []' in p.prompts[0]
    assert [r["n"] for r in fb["english"]["elements"]] == list(range(1, 19))
    assert fb["result"]["errors"][0]["category"] in ("technique identification without analysis", "descriptive response", "other")


def test_ai_reply_missing_elements_is_re_asked_once_then_not_assessed(db):
    q = _q(db)
    thin = {"mark_awarded": 1, "mark_possible": 2}
    patch = {"performance_level": "Band 4 standard", "strengths": ["Uses the narrator's reason"], "next_level": "Explain the relationship"}
    p = FakeProvider(replies=[json.dumps(thin), json.dumps(patch)])
    factory.set_test_provider(p)
    a = assessment.submit(db, q, STRONG)
    fb = a.feedback.payload
    assert len(p.prompts) == 2 and "left out" in p.prompts[1]
    assert fb["result"]["performance_level"] == "Band 4 standard"
    assert "dimensions" in fb["english"]["not_assessed"]
    rows = {r["title"]: r["value"] for r in fb["english"]["elements"]}
    assert rows["Expression"] == "Not assessed"


def test_ai_model_with_invented_quotation_is_rejected_and_good_one_cached(db):
    q = next(x for x in db.execute(select(Question).where(Question.category == "unseen")).scalars())
    q.model_answer = None
    q.solution = {**q.solution, "model_status": None, "model_source": None}
    db.flush()
    body = q.stimulus.reading_set()[0].body
    real = " ".join(body.split()[2:6])
    factory.set_test_provider(FakeProvider(default=json.loads(marking_json(1, q.marks, model_answer="It says 'a sentence never written here'."))))
    a = assessment.submit(db, q, "An answer.")
    assert a.feedback.payload["english"]["ai_model_rejected"] and q.model_answer is None
    factory.set_test_provider(FakeProvider(default=json.loads(marking_json(1, q.marks, model_answer=f"The text says '{real}', which matters."))))
    assessment.submit(db, q, "Another answer.")
    assert q.model_answer.startswith("The text says") and q.solution["model_source"] == "ai_generated"
    assert q.solution["model_status"] == "unreviewed"


def test_craft_task_is_routed_to_craft_criteria(db):
    q = next(x for x in db.execute(select(Question).where(Question.category == "course")).scalars()
             if (x.solution or {}).get("response_type") == "imaginative")
    p = FakeProvider(default=json.loads(marking_json(3, q.marks)))
    factory.set_test_provider(p)
    assessment.submit(db, q, "The suitcase sat by the door. Nobody touched it. " * 10)
    assert "Craft of Writing" in p.prompts[0] and "Never ask for quotations" in p.prompts[0]
    assert "telling not showing" in p.prompts[0]
