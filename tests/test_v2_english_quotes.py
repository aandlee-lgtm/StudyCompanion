"""Quotation verification (english-07) and the seeded model answers' quotations."""
import json

import pytest

from app.marking import quotes
from app.services.seed import SEED_DIR

PASSAGE = ("So when people in this room talk about 'improving' the river — and I know some of you will — I want you to ask: "
           "improving it for whom? For the river?\nOr for the postcard?")


def test_extracts_double_single_and_curly_quotes_but_not_apostrophes():
    text = "The mother's 'broken city', the “jewel box” and \"it's cold\"; the writer's tone isn't 'Text 1'."
    assert quotes.extract_quotes(text) == ["broken city", "jewel box", "it's cold"]


def test_verifies_typography_insensitively():
    checks = quotes.verify_quotes("She asks ‘Improving it for whom?’ and “For the river? Or for the postcard?”", PASSAGE)
    assert [c.found for c in checks] == [True, True]


def test_wrong_word_form_is_not_found_and_closest_is_suggested():
    (c,) = quotes.verify_quotes("The speaker questions 'improvement' of the river.", PASSAGE)
    assert not c.found and c.closest == "improving" and "improving" in c.note


def test_ellipsis_slash_and_brackets():
    poem = "From the lookout the city is a jewel box,\nall glitter and no hinges.\nYou cannot see from here\nthe hands that wipe the glass"
    ok = quotes.verify_quotes("'a jewel box, / all glitter' and 'From the lookout ... no hinges' and '[it] cannot see from here'", poem)
    assert all(c.found for c in ok)
    (bad,) = quotes.verify_quotes("'the hands that clean the glass'", poem)
    assert not bad.found and bad.closest and "wipe" in bad.closest


def test_paired_texts_report_which_text():
    checks = quotes.verify_quotes("'jewel box' and 'night shift'", ["The night shift begins.", "a jewel box"])
    assert [c.passage for c in checks] == [1, 0]
    assert quotes.summary(checks)["texts"] == [0, 1]


def test_unquoted_evidence_and_relevance():
    passage = "The city slid by in pieces: a crane, a church spire, the glass towers that turned the water into a second, broken city underneath."
    plain = "The glass towers turned the water into a second broken city underneath, which suggests memory is fractured."
    assert quotes.unquoted_phrases(plain, passage) >= 1
    off_topic = "Hamlet's soliloquy 'To be or not to be' reveals his paralysis and indecision about revenge and mortality."
    assert quotes.relevance(off_topic, passage, "Analyse how imagery represents memory") < 0.2
    assert quotes.relevance(plain, passage, "Analyse how imagery represents memory") > 0.4


def _sets_with_passages():
    """(label, model text, [passages]) for every seeded unseen question that has a model answer."""
    out = []
    v1 = json.loads((SEED_DIR / "questions_english.json").read_text(encoding="utf-8"))
    st = {s["key"]: s for s in v1["stimuli"]}
    for s in v1["stimuli"]:
        texts = [s["body"]] + ([st[s["pair"]]["body"]] if s.get("pair") else []) + [v["body"] for v in st.values() if v.get("pair") == s["key"]]
        for q in s.get("questions", []):
            out.append((f"v1:{s['key']}:{q['marks']}", q["model"], texts))
    path = SEED_DIR / "english_sets.json"
    if path.exists():
        for s in json.loads(path.read_text(encoding="utf-8"))["sets"]:
            texts = [s["body"]] + ([s["pair"]["body"]] if s.get("pair") else [])
            for q in s["questions"]:
                out.append((f"sets:{s['key']}:{q['marks']}", q["model"], texts))
    return out


@pytest.mark.parametrize("label,model,texts", _sets_with_passages(), ids=lambda v: v if isinstance(v, str) and ":" in v else "")
def test_every_seeded_model_quotation_is_verbatim(label, model, texts):
    bad = [c.as_dict() for c in quotes.verify_quotes(model, texts) if not c.found]
    assert not bad, f"{label}: {bad}"
