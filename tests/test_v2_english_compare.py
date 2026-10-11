"""Point-by-point comparison of the student's own response with what the question needed
(owner request 2026-10-11; english-logic)."""
import html as htmllib
import json

from sqlalchemy import select

from app.ai import factory
from app.models import Attempt, Question
from app.services import assessment
from app.services import english_compare as ec
from app.services.assessment import english
from tests.fakes import FakeProvider, marking_json

FERRY_Q = "Explain how the narrator's response to the comment about the wharf reveals their relationship with their mother."
WEAK = ("The narrator agrees with her mother. The wharf 'looked brighter than ever' which shows the mother is confused. "
        "It is about memory and family.")


def _q(db, text=FERRY_Q):
    return db.execute(select(Question).where(Question.question_text == text)).scalar_one()


# ------------------------------------------------------------------ text tools ---


def test_sentences_are_verbatim_substrings():
    text = 'She waits. The wharf "looked brighter." Then\nshe stops! Why? It ends'
    parts = ec.sentences(text)
    assert parts == ["She waits.", 'The wharf "looked brighter."', "Then", "she stops!", "It ends"] or all(p in text for p in parts)
    assert all(p in text for p in parts)


def test_is_verbatim_is_strict_about_words_but_not_typography():
    resp = "The narrator’s choice — to agree — is “easier” than asking.\nShe protects her mother."
    assert ec.is_verbatim("The narrator's choice - to agree - is \"easier\" than asking", resp)
    assert ec.is_verbatim("she protects her mother.", resp)
    assert ec.is_verbatim("The narrator's choice ... than asking", resp)
    assert not ec.is_verbatim("The narrator's decision to agree", resp)  # a paraphrase is not a quotation
    assert not ec.is_verbatim("her mother", resp)  # too short to identify a sentence


def test_closest_sentence_and_misquote_trimmed_to_the_text():
    sents = ["The narrator agrees with her mother.", "The wharf looked brighter.", "It is about memory."]
    assert ec.closest("Explains the relationship with the mother", sents)[0] == sents[0]
    assert ec.closest("Comments on the weather in winter", sents)[0] is None
    assert ec.text_wording("looked brighter than ever", ["Mum said the wharf looked brighter, because they had painted it."]) == "looked brighter"
    assert ec.as_task("Explains what this shows") == "explain what this shows" and ec.as_task("A clear thesis") is None


# --------------------------------------------------------------------- offline ---


def test_pending_marking_shows_the_closest_sentence_for_each_item(db):
    q = _q(db)
    a = assessment.submit(db, q, WEAK)
    hints = a.feedback.payload["english"]["hints"]
    assert len(hints) == len(q.solution["checklist"])
    assert all(h == "" or h in WEAK for h in hints) and any(hints)


def test_offline_comparison_is_built_from_the_ticks(db):
    q = _q(db)
    a = assessment.submit(db, q, WEAK)
    english.apply_guided_self_mark(db, a, [0])
    p = a.feedback.payload
    items = p["comparison_items"]
    assert p["comparison_source"] == "self_mark" and p["comparison"]
    gaps = [i for i in items if i["status"] != "met"]
    met = [i for i in items if i["status"] == "met"]
    checklist = q.solution["checklist"]
    # every unticked item is compared, every ticked one is shown as done
    assert {i["point"] for i in gaps if i["source"] == "self_mark"} == set(checklist[1:])
    assert [i["point"] for i in met] == [checklist[0]]
    for i in items:
        assert i["student_text"] == "" or i["student_text"] in WEAK  # their own words, never invented
    for i in gaps:
        assert i["issue"] and i["why"] and i["try"]
    # the misquotation comes first, with their sentence rewritten using the text's real wording
    mq = items[0]
    assert mq["source"] == "check" and "looked brighter than ever" in mq["issue"]
    assert mq["try_kind"] == "rewrite" and "'looked brighter'" in mq["try"] and "than ever" not in mq["try"]
    # an authored next step for this question is used as the 'try this' (or alongside a rewrite)
    steps = set(q.solution["next_steps"].values())
    assert any(i["try"] in steps or i["next_step"] in steps for i in gaps)


def test_full_ticks_leave_only_what_was_done(db):
    q = _q(db)
    resp = ("The narrator agrees that the wharf 'looked brighter' although 'They had not' painted it. Agreeing was 'easier than asking what "
            "else she was remembering wrongly', which shows a protective relationship.")
    a = assessment.submit(db, q, resp)
    english.apply_guided_self_mark(db, a, list(range(len(q.solution["checklist"]))))
    items = a.feedback.payload["comparison_items"]
    assert items and all(i["status"] == "met" for i in items)


# -------------------------------------------------------------------------- AI ---


def _ai_reply(q, items, mark=1):
    reply = json.loads(marking_json(mark, q.marks))
    reply["comparison_items"] = items
    reply["dimensions"] = {k: "ok" for k in ("textual evidence", "analysis", "form", "language", "argument", "structure", "expression",
                                             "precision", "sophistication")}
    reply["improvements"] = ["a", "b"]
    return reply


def test_ai_comparison_items_must_quote_the_student_verbatim(db):
    q = _q(db)
    items = [
        {"point": "Explain the relationship", "student_quote": "It is about memory and family.", "status": "weak",
         "issue": "Names a topic, not a relationship", "why_it_matters": "2 marks need an explanation",
         "try_this": "Agreeing shields her mother, yet the narrator privately fears how far the lapses go."},
        {"point": "Use the narrator's reason", "student_quote": "The narrator refuses to agree with her mother.", "status": "weak",
         "issue": "invented", "why_it_matters": "x", "try_this": "y"},
        {"point": "Quote accurately", "student_quote": "The wharf 'looked brighter than ever' which shows", "status": "weak",
         "issue": "Misquoted", "why_it_matters": "Accuracy", "try_this": "The wharf 'looked brighter in the rain', which shows a gap."},
    ]
    p = FakeProvider(default=_ai_reply(q, items))
    factory.set_test_provider(p)
    a = assessment.submit(db, q, WEAK)
    fb = a.feedback.payload
    assert "POINT-BY-POINT COMPARISON" in p.prompts[0] and "student_quote" in p.prompts[0]
    kept = fb["comparison_items"]
    assert [i["point"] for i in kept] == ["Explain the relationship", "Quote accurately"]
    assert fb["comparison_dropped"] == 1 and fb["comparison_source"] == "ai"
    assert kept[0]["try_kind"] == "rewrite" and kept[0]["why"] == "2 marks need an explanation"
    assert kept[1]["try_unverified"] == ["looked brighter in the rain"]  # an invented passage quotation in 'try this' is flagged
    assert all(c["student_quote"] != "The narrator refuses to agree with her mother." for c in fb["result"]["comparison_items"])
    assert len(p.prompts) == 1  # a valid comparison needs no re-ask


def test_ai_comparison_with_no_valid_items_is_re_asked_once(db):
    q = _q(db)
    bad = [{"point": "Explain", "student_quote": "Words the student never wrote at all.", "status": "weak", "issue": "x", "why_it_matters": "y",
            "try_this": "z"}]
    patch = {"comparison_items": [{"point": "Explain the relationship", "student_quote": "The narrator agrees with her mother.",
                                   "status": "weak", "issue": "Says what, not why", "why_it_matters": "Explain verbs need reasons",
                                   "try_this": "The narrator agrees with her mother, which protects her from noticing the lapse."}]}
    p = FakeProvider(replies=[json.dumps(_ai_reply(q, bad)), json.dumps(patch)])
    factory.set_test_provider(p)
    a = assessment.submit(db, q, WEAK)
    fb = a.feedback.payload
    assert len(p.prompts) == 2 and "comparison_items" in p.prompts[1]
    assert [i["student_text"] for i in fb["comparison_items"]] == ["The narrator agrees with her mother."]
    assert "comparison_items" not in fb["english"]["not_assessed"]


def test_ai_comparison_still_missing_is_not_assessed(db):
    q = _q(db)
    p = FakeProvider(default=_ai_reply(q, []))
    factory.set_test_provider(p)
    a = assessment.submit(db, q, WEAK)
    assert "comparison_items" in a.feedback.payload["english"]["not_assessed"] and a.feedback.payload["comparison_items"] == []


# ----------------------------------------------------------------------- pages ---


def test_feedback_page_leads_with_the_comparison_and_retry_is_prefilled(client, db):
    q = _q(db)
    client.post(f"/practice/{q.id}/submit", data={"answer": WEAK, "time_seconds": "60"})
    page = htmllib.unescape(client.get(f"/practice/{q.id}").text)
    assert "Your closest sentence" in page and "It is about memory and family." in page
    a = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    client.post(f"/english/attempt/{a.id}/self-mark", data={"tick": ["0"], "back": f"/practice/{q.id}"})
    page = htmllib.unescape(client.get(f"/practice/{q.id}").text)
    i_cmp, i_marks = page.index("Your response compared with what this question needed"), page.index("Marks and criteria")
    assert i_cmp < i_marks and page.index("Mark awarded") > i_marks
    assert "You wrote" in page and "Why it matters for the mark" in page and "Try rewriting your sentence" in page
    assert "The wharf 'looked brighter' which shows the mother is confused." in page  # their sentence, correctly quoted
    retry = htmllib.unescape(client.get(f"/practice/{q.id}?retry=1").text)
    assert "Work from your feedback" in retry and f">{WEAK}</textarea>" in retry
