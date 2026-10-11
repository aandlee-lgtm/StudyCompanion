"""English Advanced: per-question marking metadata, deterministic checks and GUIDED
SELF-MARKING (owner: english-logic).

Offline (no AI provider) the app does not pretend to mark English. After submitting, the
student ticks the question's checklist next to the model answer; the mark is derived from the
ticks (whole marks), then capped by deterministic checks the student cannot argue with:
quotations verified against the passage, evidence from both texts in a paired set, relevance
to this text, and length relative to the mark value. Everything is labelled as self-marked.

Per-question data lives in ``Question.solution`` (see ``meta``):
  response_type, demand, skill_tags, criteria (mark ladder), checklist, next_steps, plan,
  suggested_words, text_complexity, model_source, model_status.
Questions without authored data (e.g. imported papers) get a generic ladder and checklist
built from the marks, directive verb and response type."""
from __future__ import annotations

import math
import re

from app.ai.schemas_english import ALL_ERRORS, ANALYTICAL_ERRORS, CRAFT_ERRORS  # noqa: F401
from app.marking import quotes
from app.services.assessment.common import MARKS_EXPECTATION, VERBS

RESPONSE_TYPES = ("analytical", "comparative", "imaginative", "discursive", "persuasive", "reflective", "rewrite")
CRAFT_TYPES = ("imaginative", "discursive", "persuasive", "reflective", "rewrite")
DEMANDS = ("identify", "explain", "analyse", "compare", "evaluate", "synthesise")


# Suggested length for analytical answers by marks: a guide, never a target (english-13/16).
WORD_RANGES = {1: (15, 40), 2: (40, 80), 3: (70, 130), 4: (100, 180), 5: (150, 250), 6: (200, 350)}
POINTS = {1: "one accurate point", 2: "one point with evidence", 3: "one developed point (or two brief ones)", 4: "two developed points",
          5: "two or three developed points plus a judgement or comparison", 6: "a thesis and three developed points"}

TECHNIQUE_TERMS = re.compile(r"\b(metaphor|simile|imagery|image|personification|juxtaposition|irony|ironic|tone|symbol\w*|motif|repetition|"
                             r"alliteration|rhetorical|enjambment|rhyme|contrast|listing|fragment|syntax|allusion|hyperbole|understatement|"
                             r"oxymoron|caesura|sibilance|assonance|anaphora|first[- ]person|second[- ]person|direct address|dialogue|"
                             r"juxtapos\w*|characteris\w*|narrat\w*|stanza|couplet|declarative|imperative|cumulative)\b", re.I)


# ------------------------------------------------------------------ metadata ---


def word_range(marks: int, response_type: str = "analytical", suggested: list | tuple | None = None) -> tuple[int, int]:
    if suggested and len(suggested) == 2:
        return int(suggested[0]), int(suggested[1])
    if marks in WORD_RANGES:
        return WORD_RANGES[marks]
    return 50 * marks, 70 * marks


def estimate_minutes(marks: int, response_type: str = "analytical", suggested: list | tuple | None = None) -> float:
    """Composition time comes from the word target (about 20 words a minute drafting plus planning);
    analytical answers from the mark value (english-04)."""
    if response_type in CRAFT_TYPES and suggested and len(suggested) == 2:
        return float(round(int(suggested[1]) / 20 + (2 if response_type in ("reflective", "rewrite") else 3)))
    return round(1.75 * marks + 0.5, 1)


def text_scope(question: str, n_texts: int, verb: str | None = None) -> list[int]:
    """Which texts of a reading set a question is about: [0], [1] or [0, 1] (Text 1 = the main text)."""
    if n_texts < 2:
        return [0]
    t = (question or "").lower()
    one = re.search(r"\btext (1|one)\b", t)
    two = re.search(r"\btext (2|two)\b", t)
    if (one and two) or re.search(r"\bboth texts\b|\bthe two texts\b|\bthese texts\b|\beach text\b|\bboth\b", t) or (verb or "").lower() == "compare":
        return [0, 1]
    if one:
        return [0]
    if two:
        return [1]
    return [0, 1]


def ladder_text(ladder: list[dict]) -> str:
    """The ladder as the plain 'N marks: …' lines stored in ``Question.marking_guideline``."""
    rows = []
    for e in sorted(normalise_ladder(ladder), key=lambda e: -e["mark"]):
        span = f"{e['low']}–{e['mark']}" if e.get("low") is not None else str(e["mark"])
        rows.append(f"{span} mark{'s' if e['mark'] != 1 or e.get('low') is not None else ''}: {e['descriptor']}")
    return "\n".join(rows)


def parse_ladder(text: str | None) -> list[dict]:
    """'4 marks: …' / '1-2 marks: …' lines, or NESA-style rows ending in a mark or range."""
    out: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip(" •-\t")
        if not line:
            continue
        m = re.match(r"(\d+)\s*(?:[-–]\s*(\d+))?\s*marks?\s*[:.\-–]\s*(.+)$", line, re.I)
        if m:
            lo, hi, desc = int(m.group(1)), int(m.group(2) or m.group(1)), m.group(3)
        else:
            m = re.match(r"(.+?)\s+(\d+)(?:\s*[-–]\s*(\d+))?\s*$", line)
            if not m or len(m.group(1)) < 12:
                continue
            desc, lo, hi = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
            lo, hi = min(lo, hi), max(lo, hi)
        e = {"mark": hi, "descriptor": desc.strip()}
        if lo != hi:
            e["low"] = lo
        out.append(e)
    return sorted(out, key=lambda e: -e["mark"])


def normalise_ladder(criteria) -> list[dict]:
    if isinstance(criteria, str):
        return parse_ladder(criteria)
    out = []
    for c in criteria or []:
        if isinstance(c, dict) and "mark" in c:
            e = {"mark": int(c["mark"]), "descriptor": str(c.get("descriptor", "")).strip()}
            if c.get("low") is not None and int(c["low"]) != e["mark"]:
                e["low"] = int(c["low"])
            out.append(e)
        elif isinstance(c, str):
            out.extend(parse_ladder(c))
    return sorted(out, key=lambda e: -e["mark"])


def generic_ladder(marks: int, verb: str | None, response_type: str) -> list[dict]:
    v = (verb or "respond").lower()
    if response_type in CRAFT_TYPES:
        scale = [(1.0, "Skilful, purposeful control of form, voice and language; vivid, specific detail; a structure that shapes the reader's response"
                       + ("; the reflection explains deliberate choices and their effects" if response_type != "rewrite" else "")),
                 (0.75, "Effective control of form and language for purpose, with some well-chosen detail and a clear structure"),
                 (0.5, "Sound attempt with some control of language; detail is general or the purpose is uneven"),
                 (0.25, "Limited control; mostly tells rather than shows; little sense of purpose")]
    else:
        scale = [(1.0, f"Does what '{v}' asks: {MARKS_EXPECTATION.get(min(marks, 6), MARKS_EXPECTATION[6])}"),
                 (0.8, "Well-developed response with relevant, integrated evidence and clear analysis of how meaning is shaped"),
                 (0.6, "Sound response with relevant evidence and some analysis of how meaning is shaped"),
                 (0.4, "Some explanation with limited evidence; tends to describe or retell"),
                 (0.2, "Identifies a relevant point or feature with little explanation")]
    out: list[dict] = []
    for mark in range(marks, 0, -1):
        frac = mark / marks
        desc = scale[-1][1] if mark == 1 else next((d for f, d in scale if frac >= f - 1e-9), scale[-1][1])
        if out and out[-1]["descriptor"] == desc:
            out[-1]["low"] = mark  # same descriptor as the level above: shown as a range
            continue
        out.append({"mark": mark, "descriptor": desc})
    return out


def generic_checklist(marks: int, verb: str | None, response_type: str, paired: bool, has_text: bool, question: str = "") -> list[str]:
    v = (verb or "").lower()
    if response_type in CRAFT_TYPES:
        items = {
            "imaginative": ["Uses specific, sensory detail that implies feeling rather than naming it",
                            "Keeps point of view and tense deliberately controlled throughout",
                            "Has a purposeful structure (e.g. withheld information, a turn, a resonant ending)",
                            "Has a distinctive, consistent voice"],
            "discursive": ["Explores the idea from more than one angle without forcing a single conclusion",
                           "Moves between personal anecdote and broader reflection", "Uses a conversational but crafted voice",
                           "Has a structure that develops the thinking rather than listing points"],
            "persuasive": ["Has a clear position that the audience cannot miss", "Uses audience-aware rhetoric (inclusive address, concession, rhetorical question)",
                           "Supports claims with specific examples", "Ends with a memorable call or reframing"],
            "reflective": ["Names the specific craft choice made", "Explains the intended effect on the reader",
                           "Links the choice to the purpose of the piece", "Uses precise metalanguage"],
            "rewrite": ["Shows the feeling through action, physical detail or setting instead of naming it",
                        "Avoids stating the emotion directly", "Explains how each choice creates the effect"],
        }[response_type]
        if response_type != "reflective" and re.search(r"reflection|reflect|explain (your|the) choice", question or "", re.I):
            items.append("The reflection names a deliberate choice, its effect, and how it serves the purpose")
        return items
    out = [f"Does exactly what the question asks ('{verb or 'answer'}'{': ' + VERBS[v] if v in VERBS else ''})"]
    if has_text:
        n = 1 if marks <= 3 else (2 if marks <= 5 else 3)
        out.append(f"Uses at least {n} short quotation{'s' if n > 1 else ''} from the text, quoted exactly and woven into sentences")
    out.append("For each piece of evidence, names the technique or feature AND explains its effect on meaning")
    if marks >= 4:
        out.append(f"Has {POINTS.get(min(marks, 6))}, each linked back to the question")
    if v in ("evaluate", "assess", "discuss", "to what extent"):
        out.append("Makes a clear judgement (e.g. 'highly effective because…') and justifies it")
    if paired or v == "compare" or response_type == "comparative":
        out.append("Discusses BOTH texts and shows at least one similarity AND one difference")
    if marks >= 5:
        out.append("Has a clear thesis or line of argument sustained to the end")
    return out


def generic_next_steps(ladder: list[dict]) -> dict[str, str]:
    asc = sorted(ladder, key=lambda e: e["mark"])
    out = {}
    for i, e in enumerate(asc[:-1]):
        nxt = asc[i + 1]
        for m in range(e.get("low", e["mark"]), e["mark"] + 1):
            out[str(m)] = f"To reach {nxt.get('low', nxt['mark'])} marks: {nxt['descriptor'][0].lower() + nxt['descriptor'][1:]}"
    if asc:
        out.setdefault("0", f"To earn a first mark: {asc[0]['descriptor'][0].lower() + asc[0]['descriptor'][1:]}")
    return out


def default_demand(verb: str | None) -> str:
    v = (verb or "").lower()
    return {"identify": "identify", "outline": "identify", "describe": "identify", "explain": "explain", "analyse": "analyse", "compare": "compare",
            "evaluate": "evaluate", "assess": "evaluate", "discuss": "evaluate", "compose": "synthesise", "synthesise": "synthesise"}.get(v, "explain")


def meta(q, paired: bool | None = None) -> dict:
    """Normalised English marking metadata for a question (authored data, else generic)."""
    sol = dict(q.solution or {})
    rt = sol.get("response_type") or ("imaginative" if (q.directive_verb or "").lower() == "compose" else
                                      ("comparative" if (q.directive_verb or "").lower() == "compare" else "analytical"))
    n_texts = len(q.stimulus.reading_set()) if q.stimulus else 0
    scope = [i for i in (sol.get("texts") or text_scope(q.question_text, n_texts, q.directive_verb)) if i < max(n_texts, 1)] or [0]
    if paired is None:
        paired = n_texts > 1 and len(scope) > 1
    has_text = bool(q.stimulus and (q.stimulus.body or "").strip())
    ladder = normalise_ladder(sol.get("criteria")) or (parse_ladder(q.marking_guideline) if q.marking_guideline else [])
    ladder = [e for e in ladder if 0 < e["mark"] <= q.marks] or generic_ladder(q.marks, q.directive_verb, rt)
    checklist = [str(c).strip() for c in (sol.get("checklist") or sol.get("guidance") or []) if str(c).strip()]
    authored = bool(sol.get("checklist") or sol.get("guidance"))
    if not checklist:
        checklist = generic_checklist(q.marks, q.directive_verb, rt, paired, has_text, q.question_text)
    next_steps = {str(k): str(v) for k, v in (sol.get("next_steps") or {}).items() if v}
    for k, v in generic_next_steps(ladder).items():
        next_steps.setdefault(k, v)
    return {
        "response_type": rt, "craft": rt in CRAFT_TYPES, "demand": sol.get("demand") or default_demand(q.directive_verb),
        "skill_tags": list(sol.get("skill_tags") or []), "ladder": ladder, "checklist": checklist, "checklist_authored": authored,
        "next_steps": next_steps, "plan": sol.get("plan"), "suggested_words": list(word_range(q.marks, rt, sol.get("suggested_words"))),
        "text_complexity": sol.get("text_complexity"), "model_source": sol.get("model_source") or ("app_authored" if q.model_answer else None),
        "model_status": sol.get("model_status"), "paired": paired, "has_text": has_text, "module": sol.get("module"),
        "texts": scope if n_texts > 1 else [0], "n_texts": n_texts, "form": sol.get("form") or (q.stimulus.form if q.stimulus else None),
    }


def level_for(ladder: list[dict], mark: float) -> dict | None:
    m = int(round(mark))
    for e in ladder:
        if e.get("low", e["mark"]) <= m <= e["mark"]:
            return e
    return None


# --------------------------------------------------------- deterministic checks ---


def reading_texts(q) -> list[str]:
    return [s.body or "" for s in q.stimulus.reading_set()] if q.stimulus else []


def response_segments(response: str, checks: list[quotes.QuoteCheck]) -> list[dict]:
    """The response split into plain text and quotations marked found/not found (for highlighting)."""
    text = quotes.display_text(response)
    segs, pos = [], 0
    for c in checks:
        i = text.find(c.quote, pos)
        if i < 0:
            continue
        if i > pos:
            segs.append({"t": text[pos:i]})
        segs.append({"t": c.quote, "q": "ok" if c.found else "bad", "note": "Found in the text" if c.found else c.note})
        pos = i + len(c.quote)
    if pos < len(text):
        segs.append({"t": text[pos:]})
    return segs


def checks(q, response: str, m: dict) -> dict:
    """Deterministic, explainable checks on a response. Caps limit the self-mark; warnings teach."""
    texts = reading_texts(q)
    words = len((response or "").split())
    lo, hi = m["suggested_words"]
    marks = q.marks
    qc = quotes.verify_quotes(response or "", texts) if texts else []
    summ = quotes.summary(qc)
    unquoted = [quotes.unquoted_phrases(response or "", t) for t in texts]
    rel = quotes.relevance(response or "", texts, q.question_text) if texts else None
    warnings: list[dict] = []

    def warn(code, msg, cap=None):
        warnings.append({"code": code, "message": msg, "cap": cap})

    if words < 5:
        warn("empty", "The response is too short to earn marks.", 0)
    elif words < 0.4 * lo:
        warn("short", f"At {words} words this is very short for a {marks}-mark question (a typical answer is about {lo}–{hi} words). "
                      f"Short answers rarely develop enough to go above {math.ceil(marks / 2)}.", math.ceil(marks / 2))
    elif words > 2.5 * hi:
        warn("long", f"At {words} words this is long for {marks} marks. Markers reward development and precision, not length; "
                     f"in an exam this would cost you time on other questions.")
    if texts and not m["craft"]:
        evidence_texts = set(summ["texts"]) | {i for i, n in enumerate(unquoted) if n}
        if summ["verified"] == 0 and not any(unquoted) and words >= 5:
            cap = 1 if marks <= 2 else max(1, marks // 2)
            lead = ("None of your quotations was found in the text exactly as written, so the answer has no verified evidence."
                    if summ["unverified"] else "No quotation or wording from the passage was found in your answer.")
            warn("no_evidence", f"{lead} Textual evidence is essential: without it the answer cannot go above {cap}/{marks}.", cap)
        elif summ["verified"] == 0 and any(unquoted):
            warn("unmarked_evidence", "You use the passage's wording but without quotation marks. Mark quotations clearly so the marker sees your evidence.")
        if summ["unverified"]:
            bad = [c for c in qc if not c.found]
            warn("misquote", f"{len(bad)} quotation{'s' if len(bad) > 1 else ''} not found in the text exactly as written: "
                             + "; ".join(f"“{c.quote}” — {c.note}" for c in bad[:4]) + " Quote accurately: misquotation weakens your evidence.")
        if rel is not None and rel < 0.15 and summ["verified"] == 0 and words >= 5:
            warn("off_text", "This answer may not address this text: very few of its words relate to the passage or the question. "
                             "If you wrote about another text by mistake, it cannot earn more than 1 mark here.", 1)
        scope = set(m.get("texts") or [0])
        if len(texts) > 1 and len(scope) == 1 and evidence_texts and not (evidence_texts & scope):
            want, got = ("Text 1", "Text 2") if 0 in scope else ("Text 2", "Text 1")
            warn("wrong_text", f"The question asks about {want}, but your evidence comes from {got}. Quote from {want}.", 1)
        if m["paired"] and len(texts) > 1 and len(evidence_texts) == 1 and words >= 5:
            only = "Text 1" if 0 in evidence_texts else "Text 2"
            cap = max(1, marks // 2)
            warn("one_text", f"Your evidence comes only from {only}. A comparison needs evidence from BOTH texts; "
                             f"an answer that deals with one text is capped at {cap}/{marks}.", cap)
    caps = [w["cap"] for w in warnings if w["cap"] is not None]
    return {"words": words, "quotes": [c.as_dict() for c in qc], "quote_summary": summ, "unquoted_phrases": sum(unquoted),
            "relevance": rel, "warnings": warnings, "cap": min(caps) if caps else None,
            "segments": response_segments(response or "", qc), "paragraphs": len([p for p in re.split(r"\n\s*\n", response or "") if p.strip()]),
            "technique_terms": len(TECHNIQUE_TERMS.findall(response or ""))}


# ------------------------------------------------------------- self-marking ---


def derive_mark(marks: int, n_items: int, ticked: int, cap: int | None) -> tuple[int, int]:
    """(raw mark from ticks, final mark after caps). Whole marks; all items ticked = full marks."""
    if n_items <= 0:
        return 0, 0
    raw = int(math.floor(marks * ticked / n_items + 0.5))
    raw = max(0, min(marks, raw))
    final = raw if cap is None else min(raw, cap)
    return raw, final


def item_category(text: str, response_type: str, response: str = "") -> str:
    t = text.lower()
    if response_type in CRAFT_TYPES:
        if "reflect" in t:
            return "reflection not linked to purpose"
        if re.search(r"tense|point of view|\bpov\b", t):
            return "uncontrolled tense or point of view"
        if re.search(r"structure|turn|ending|withh", t):
            return "structure lacks purpose"
        if re.search(r"show|naming|name the|telling|state the emotion|imply", t):
            return "telling not showing"
        return "generic or clichéd detail"
    if re.search(r"compar|both texts|text 1|text 2|similarit|differen", t):
        return "poor comparison"
    if re.search(r"judg|evaluat|effective|to what extent|weigh", t):
        return "limited evaluation"
    if re.search(r"thesis|line of argument|overall (view|reading)|synthesi", t):
        return "weak thesis"
    if re.search(r"quot|evidence", t) and not re.search(r"explain|analys|effect", t):
        return "insufficient textual evidence"
    if re.search(r"explain|analys|effect|suggest|how|shape|reveal", t):
        return "technique identification without analysis" if TECHNIQUE_TERMS.search(response or "") else "descriptive response"
    return "descriptive response"


def element_rows(*, mark_text: str, marks: int, level: str, criteria: list[dict], outcomes: str, well: list[str], prevented: list[str],
                 dims: dict[str, str], next_level: str, actions: list[str]) -> list[dict]:
    """The 18 feedback elements of spec section 7, always in the same numbered order so a missing
    element is visible as 'Not assessed' rather than silently absent."""
    na = "Not assessed"
    rows = [("Mark awarded", mark_text), ("Maximum", f"{marks} marks"), ("Estimated performance level", level or na),
            ("Relevant criteria", criteria), ("Syllabus outcomes", outcomes or na), ("What was done well", well or [na]),
            ("What prevented a higher mark", prevented or ["Nothing significant."]),
            ("Quality of textual evidence", dims.get("textual evidence") or na), ("Quality of analysis", dims.get("analysis") or na),
            ("Understanding of form", dims.get("form") or na), ("Understanding of language", dims.get("language") or na),
            ("Quality of argument", dims.get("argument") or na), ("Structure", dims.get("structure") or na),
            ("Expression", dims.get("expression") or na), ("Precision", dims.get("precision") or na),
            ("Sophistication of interpretation", dims.get("sophistication") or na),
            ("What a marker expects at the next level", next_level or na), ("Concrete actions", actions or [na])]
    return [{"n": i + 1, "title": t, "value": v} for i, (t, v) in enumerate(rows)]
