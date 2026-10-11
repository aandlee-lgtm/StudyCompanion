"""English Advanced parts of the structured marking prompt (owner: english-logic).

The shared prompt (``prompts.marking``) supplies the subject, question, stimulus, criteria and the
student's response. This module adds what calibrates an English mark (english-04/05/12/20):
response-type routing (analytical vs Craft of Writing), the mark-scaling expectation for this mark
value and verb, the app-authored mark ladder and checklist, the REFERENCE model (or response plan)
the AI must compare against instead of writing a new one, which text(s) of a paired set the
question is about, the allowed error categories, and the retry comparison."""
from __future__ import annotations

import json

from app.ai.schemas_english import ALL_ERRORS, ANALYTICAL_ERRORS, CRAFT_ERRORS, EnglishMarking

MARKING_SCHEMA = EnglishMarking  # used by AIProvider.mark_response for English (falls back to MarkingResult)

SCALING = {
    1: "one accurate point", 2: "one clear point supported by one piece of evidence, briefly explained",
    3: "a clear point with apt evidence and an explanation of its effect (or two briefer points)",
    4: "two developed points, each linking evidence to a technique or feature and explaining how it shapes meaning",
    5: "a sustained answer: two or three developed points, integrated evidence and an explicit judgement or comparison",
    6: "a structured mini-essay: a clear thesis, three developed points with integrated evidence and perceptive analysis of form and meaning",
}
CRAFT_FOCUS = {
    "imaginative": "purposeful control of form, point of view and tense; imagery and sensory detail that implies rather than states; "
                   "structure (withholding, the turn, a resonant ending); a distinctive voice",
    "discursive": "exploration of an idea from more than one angle; movement between anecdote and reflection; a crafted conversational voice; "
                  "a structure that develops the thinking",
    "persuasive": "a clear position; audience-aware rhetoric (inclusive address, concession, rhetorical questions); specific support; a memorable close",
    "reflective": "naming a specific craft choice, its intended effect on the reader and how it serves the purpose, in precise metalanguage",
    "rewrite": "showing rather than telling (action, physical detail, setting); no directly named emotion; an explanation of each choice",
}


COMPARISON_ITEM = {
    "point": "what the question needed (a checklist item or criterion, in plain words)",
    "student_quote": "ONE sentence (or clause of at least three words) copied EXACTLY from the student response; \"\" only if nothing in it attempts this point",
    "status": "missing | weak | met",
    "issue": "what is missing or weak in that sentence",
    "why_it_matters": "why this costs marks on THIS question at this mark value",
    "try_this": "a rewritten version of the student's sentence, in their voice, one level higher (or a short example sentence they can adapt); "
                "any quotation from the stimulus must be copied verbatim",
}
COMPARISON_RULE = (
    "POINT-BY-POINT COMPARISON (the most important part of the feedback; it is shown first): fill comparison_items with 3–6 items "
    "comparing THE STUDENT'S OWN RESPONSE with what this question needed (the checklist, the ladder and the reference). Order them by how "
    "many marks they cost. For each item quote the student's own sentence in student_quote EXACTLY as they wrote it — it is checked "
    "word for word against the response and an item whose quote is not found there is discarded. Say what is missing or weak, why it "
    "matters for the mark, and give try_this: their sentence rewritten one level higher (or a short example they can adapt). Include at "
    "most one item with status \"met\" to show what already works. Constructive, specific, never generic.")


def _english(ctx: dict) -> dict:
    return ctx.get("english") or {}


def shape_extra(ctx: dict) -> dict:
    e = _english(ctx)
    craft = e.get("craft")
    cats = CRAFT_ERRORS + ["insufficient textual evidence"] if craft else ANALYTICAL_ERRORS
    extra = {
        "errors": [{"category": "EXACTLY one of: " + " | ".join(cats), "description": "what went wrong in THIS response, quoting it"}],
        "criteria": [{"name": "criterion (from the ladder or checklist)", "judgement": "met/partly/not met",
                      "comment": "cite the phrase from the student response that justifies the judgement"}],
        "criterion_evidence": [{"criterion": "...", "student_phrase": "exact words from the student response", "judgement": "met/partly/not met"}],
        "comparison_points": {"what_model_does": "...", "descriptive_moments": "...", "evidence_integration": "...", "development": "...",
                              "expression": "...", "sophistication": "..."},
        "comparison_items": [COMPARISON_ITEM],
    }
    if e.get("reference_model") or e.get("plan"):
        extra["model_answer"] = "\"\" (empty: a reference response is supplied; do NOT write a new model)"
    if ctx.get("previous_attempt"):
        extra["improvement_since_last"] = {"addressed": ["weakness from the previous attempt now fixed"], "still_missing": ["..."], "new_issues": ["..."]}
    return extra


def marking_sections(ctx: dict) -> list[str]:
    e = _english(ctx)
    if not e:
        return []
    marks = int(ctx.get("marks") or 1)
    verb = ctx.get("directive_verb") or "respond"
    rt = e.get("response_type") or "analytical"
    out: list[str] = []
    if e.get("craft"):
        out.append(
            f"RESPONSE TYPE: Craft of Writing — {rt}. Judge it as a composition, NOT as an analytical essay. Reward {CRAFT_FOCUS.get(rt, CRAFT_FOCUS['imaginative'])}. "
            "Never ask for quotations from other texts (only a reflection discusses the student's own choices). "
            f"Suggested length about {e['suggested_words'][0]}–{e['suggested_words'][1]} words (a guide, not a target).")
    else:
        out.append(f"RESPONSE TYPE: {rt}. COGNITIVE DEMAND: {e.get('demand', 'analyse')}.")
        out.append(f"MARK-SCALING EXPECTATION: for a {marks}-mark '{verb}' question a marker expects {SCALING.get(min(marks, 6), SCALING[6])}. "
                   f"A typical answer is about {e['suggested_words'][0]}–{e['suggested_words'][1]} words; length alone earns nothing.")
    if e.get("ladder"):
        out.append("APP-AUTHORED MARK LADDER (not official NESA; place the response on it):\n"
                   + "\n".join(f"{x.get('low', x['mark'])}{'–' + str(x['mark']) if x.get('low') else ''} marks: {x['descriptor']}" for x in e["ladder"]))
    if e.get("checklist"):
        out.append("WHAT A STRONG ANSWER TO THIS QUESTION CONTAINS (checklist):\n" + "\n".join(f"- {c}" for c in e["checklist"]))
    if e.get("n_texts", 0) > 1:
        scope = e.get("texts") or [0, 1]
        about = "BOTH texts (Text 1 and Text 2): an answer with evidence from only one text cannot reach the top levels" if len(scope) > 1 else \
            f"Text {scope[0] + 1} only"
        out.append(f"PAIRED TEXTS: the stimulus contains Text 1 then Text 2. This question is about {about}.")
    if e.get("reference_model"):
        out.append("REFERENCE BAND 6 RESPONSE (app-authored for this question; its quotations are verified):\n<<<REFERENCE\n"
                   + e["reference_model"] + "\nREFERENCE>>>\nCompare the student's response with this reference. Do NOT write a new model "
                   "answer: return model_answer as an empty string.")
    elif e.get("plan"):
        out.append("REFERENCE BAND 6 RESPONSE PLAN (app-authored; contains no quotations):\n" + e["plan"]
                   + "\nUse it to judge the response. Do NOT write a model answer: return model_answer as an empty string.")
    elif not e.get("craft") and e.get("has_text"):
        out.append("No reference response exists: write a Band 6 model_answer for THIS question. Every quotation in it must be copied "
                   "verbatim from the stimulus (it will be checked word for word; an invented quotation makes the model unusable).")
    if not e.get("has_text") and not e.get("craft"):
        out.append("PRESCRIBED TEXT NOT SUPPLIED: the student quotes from their own copy. Do NOT invent quotations from the prescribed "
                   "text, and do not 'correct' a quotation you cannot verify; refer to moments and scenes instead.")
    if e.get("anchors"):
        out.append("ANCHOR RESPONSES WITH THEIR MARKS (for calibration):\n" + "\n".join(f"[{a['mark']}/{marks}] {a['text']}" for a in e["anchors"][:3]))
    out.append(COMPARISON_RULE)
    out.append(
        "ENGLISH MARKING RULES: award WHOLE marks only (no half marks, whatever the general instruction says). For each criterion judgement "
        "cite the phrase from the student response that justifies it. An answer that does not address this text earns 0–1. Quotations the "
        "student gives that are not in the stimulus are an accuracy error. Error categories must be EXACTLY one of: "
        + " | ".join(ALL_ERRORS) + ". Fill every dimension (" + ", ".join(
            ["textual evidence", "analysis", "form", "language", "argument", "structure", "expression", "precision", "sophistication"]) + ").")
    outcomes = ctx.get("outcome") or ""
    if not outcomes or "not yet imported" in outcomes or "not imported" in outcomes:
        out.append("SYLLABUS OUTCOMES: the official outcome codes have not been imported. Return \"outcomes\": [] — never invent outcome codes.")
    else:
        out.append(f"SYLLABUS OUTCOMES: use only: {outcomes}")
    if ctx.get("previous_attempt"):
        out.append("RETRY: this is a rewrite of the PREVIOUS ATTEMPT below. Fill improvement_since_last: which earlier weaknesses are now "
                   "addressed, which are still missing, and any new issues.")
    return out


def patch_prompt(ctx: dict, result: dict, missing: list[str]) -> str:
    """Re-ask for only the elements an English marking reply left out (english-06)."""
    shape = {"performance_level": "...", "strengths": ["..."], "weaknesses": ["..."], "next_level": "...", "improvements": ["...", "..."],
             "dimensions": {k: "..." for k in ("textual evidence", "analysis", "form", "language", "argument", "structure", "expression",
                                               "precision", "sophistication")},
             "comparison_points": {"what_model_does": "...", "descriptive_moments": "...", "evidence_integration": "...", "development": "...",
                                   "expression": "...", "sophistication": "..."},
             "improved_answer": "the student's answer lifted toward Band 6, keeping their ideas; quotations verbatim from the stimulus",
             "comparison_items": [COMPARISON_ITEM, "... 3 to 6 items; student_quote copied EXACTLY from the student response"]}
    want = {k: v for k, v in shape.items() if k in missing}
    return "\n\n".join([
        f"TASK: You marked this {ctx.get('subject_name', 'English Advanced')} response {result.get('mark_awarded')}/{ctx.get('marks')}, but your "
        f"reply left out: {', '.join(missing)}. Supply ONLY those elements, consistent with the mark you gave.",
        f"QUESTION:\n{ctx.get('question')}",
        f"STIMULUS:\n<<<STIMULUS\n{ctx.get('stimulus') or '(none)'}\nSTIMULUS>>>",
        f"STUDENT RESPONSE:\n<<<RESPONSE\n{ctx.get('response')}\nRESPONSE>>>",
        f"YOUR EARLIER FEEDBACK: {json.dumps({k: result.get(k) for k in ('strengths', 'weaknesses', 'criteria')}, ensure_ascii=False)[:2000]}",
        "Reply ONLY with JSON of this shape:\n" + json.dumps(want, indent=1, ensure_ascii=False),
    ])


def why_lost_prompt(ctx: dict) -> str:
    """'Why did I lose the mark?' for English with the passage, ladder, reference and next steps (english-12)."""
    return "\n\n".join([
        "TASK: Explain to a Year 12 student why their English answer did not receive full marks. Teach the principle; do NOT repeat the "
        "marking feedback list. Quote ONE of the student's own sentences and show it rewritten one level higher.",
        f"QUESTION ({ctx['marks']} marks, directive verb: {ctx.get('directive_verb') or '(none)'}):\n{ctx['question']}",
        f"STIMULUS:\n<<<STIMULUS\n{ctx.get('stimulus') or '(none)'}\nSTIMULUS>>>",
        "MARK LADDER:\n" + "\n".join(f"{x['mark']} marks: {x['descriptor']}" for x in ctx.get("ladder") or []),
        "AUTHORED NEXT STEPS BY MARK: " + json.dumps(ctx.get("next_steps") or {}, ensure_ascii=False),
        f"REFERENCE RESPONSE:\n{ctx.get('reference') or '(none)'}",
        f"MARK AWARDED: {ctx['mark']} / {ctx['marks']}",
        f"STUDENT RESPONSE:\n<<<RESPONSE\n{ctx['response']}\nRESPONSE>>>",
        'Reply ONLY with JSON: {"did_well_specific": "...", "gap_principle": "...", "passage_specific_next_step": "...", '
        '"example_sentence_upgrade": {"student_sentence": "exact sentence from the response", "upgraded": "..."}}',
    ])
