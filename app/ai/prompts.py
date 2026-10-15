"""Structured prompts. Each prompt states the subject, syllabus context, question, marks,
directive verb, any official marking guideline, performance-band information and the exact
JSON shape required. Student work is clearly delimited."""
from __future__ import annotations

import json

SYSTEM = (
    "You are an experienced NSW HSC marker and teacher assisting a Year 12 student preparing for the 2027 HSC "
    "(Mathematics Advanced, English Advanced, Legal Studies). You are precise, honest and constructive. "
    "You never invent NESA questions, NESA marking guidelines, statistics, legislation, cases, dates or quotations. "
    "When something cannot be verified you say so. You always reply with a single JSON object and nothing else."
    + '\n\nVOICE (owner request): write feedback the way a warm, sharp teacher talks to a 17-18-year-old — plain, direct, specific, "you" and "your", short sentences, no jargon piles, no filler or stock phrases ("delve", "tapestry", "nuanced interplay", "it is important to note", "in conclusion", "furthermore", "showcases", "underscores", "multifaceted", "a testament to"). Model and improved answers must read like a genuinely top Year 12 student wrote them under exam conditions: confident, clear, natural sentence variety, precise subject vocabulary used naturally, not ornate or mechanical, no lists of techniques bolted together.'
)

BANDS = {
    "ENGLISH": "Band 6 responses: extensive, perceptive understanding; sophisticated, sustained analysis of how textual form, "
    "language and structure shape meaning; judicious, well-integrated evidence; precise, fluent expression. "
    "Band 5: thorough, well-developed analysis with relevant evidence. Band 4: sound analysis with some description. "
    "Band 3 and below: largely descriptive, limited evidence or explanation.",
    "LEGAL": "Band 6 responses: comprehensive knowledge and understanding of legal concepts; sustained, well-reasoned judgement "
    "directly answering the directive verb; extensive, accurate use of legislation, cases and contemporary evidence; "
    "effective evaluation of law reform and the effectiveness of the law; precise legal terminology; logical structure.",
    "MATHS": "Full marks require a correct answer supported by valid, clearly communicated working.",
}

DIRECTIVES = {
    "identify": "recognise and name", "explain": "relate cause and effect; make the relationships between things evident",
    "analyse": "identify components and the relationship between them; draw out and relate implications",
    "evaluate": "make a judgement based on criteria; determine the value of", "assess": "make a judgement of value, quality, outcomes, results or size",
    "compare": "show how things are similar or different", "discuss": "identify issues and provide points for and/or against",
    "describe": "provide characteristics and features", "outline": "sketch in general terms", "compose": "create a text with a clear purpose",
}

MARKING_SHAPE = {
    "mark_awarded": "number", "mark_possible": "number", "confidence": "0..1", "performance_level": "e.g. 'Band 5 standard'",
    "criteria": [{"name": "criterion", "judgement": "met/partly/not met", "comment": "..."}], "outcomes": ["syllabus outcome text"],
    "strengths": ["..."], "weaknesses": ["what prevented a higher mark"], "errors": [{"category": "error category", "description": "..."}],
    "dimensions": {"textual evidence": "...", "analysis": "...", "form": "...", "language": "...", "argument": "...", "structure": "...",
                   "expression": "...", "precision": "...", "sophistication": "..."},
    "next_level": "what a marker would expect at the next level", "improvements": ["concrete action"],
    "model_answer": "Band 6-standard response written specifically for this question (not a reproduction of any published answer)",
    "comparison": "what the model does that the student's response does not; where the student becomes descriptive; evidence integration; development; expression; sophistication",
    "improved_answer": "the student's answer rewritten, keeping as many of their ideas as possible, lifted toward Band 6",
    "revision_recommendation": ["..."],
}



def _directive(verb: str | None) -> str:
    if not verb:
        return "(none)"
    return f"{verb} — NESA glossary: {DIRECTIVES.get(verb.lower(), 'see NESA glossary of key words')}"


def _subject_module(subj: str):
    """Subject-specific prompt pieces live in prompts_english.py / prompts_legal.py."""
    if subj == "LEGAL":
        from app.ai import prompts_legal

        return prompts_legal
    if subj == "ENGLISH":
        from app.ai import prompts_english

        return prompts_english
    return None


def marking(ctx: dict) -> str:
    subj = ctx["subject"]
    shape = dict(MARKING_SHAPE)
    sub = _subject_module(subj)
    if sub is not None:
        shape.update(sub.shape_extra(ctx))
    parts = [
        f"TASK: Mark a {ctx['subject_name']} response for a Year 12 student (2027 HSC).",
        f"SYLLABUS: {ctx.get('syllabus', '')}",
        f"TOPIC / FOCUS AREA: {ctx.get('topic', '')}",
        f"SYLLABUS OUTCOME: {ctx.get('outcome', '(not imported)')}",
        f"MARKS AVAILABLE: {ctx['marks']}",
        f"DIRECTIVE VERB: {_directive(ctx.get('directive_verb'))}",
        f"QUESTION SOURCE: {ctx.get('source_context', '')}",
    ]
    if ctx.get("stimulus"):
        parts.append(f"STIMULUS (attribution: {ctx.get('stimulus_attribution', '')}):\n<<<STIMULUS\n{ctx['stimulus']}\nSTIMULUS>>>")
    parts.append(f"QUESTION:\n{ctx['question']}")
    if ctx.get("official_guideline"):
        parts.append(f"OFFICIAL NESA MARKING GUIDELINE (use it):\n{ctx['official_guideline']}")
    elif ctx.get("criteria"):
        parts.append(f"APP-AUTHORED MARKING CRITERIA (not official NESA; use as guidance):\n{ctx['criteria']}")
    else:
        parts.append("No official marking guideline exists: estimate against NESA syllabus and performance-band criteria.")
    parts.append(f"PERFORMANCE BANDS: {BANDS.get(subj, '')}")
    if sub is not None:
        parts.extend(sub.marking_sections(ctx))
    if ctx.get("previous_attempt"):
        parts.append(f"PREVIOUS ATTEMPT (for comparison):\n<<<PREVIOUS\n{ctx['previous_attempt']}\nPREVIOUS>>>")
    parts.append(f"STUDENT RESPONSE:\n<<<RESPONSE\n{ctx['response']}\nRESPONSE>>>")
    parts.append(
        "Award a whole or half mark from 0 to the marks available. Be calibrated: do not inflate. "
        "Feedback depth: " + ctx.get("feedback_depth", "full") + ". Reply ONLY with JSON of this shape:\n" + json.dumps(shape, indent=1)
    )
    return "\n\n".join(parts)


def why_lost(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Explain to the student, in 80-160 words, WHY they did not receive full marks. Teach the underlying principle "
        "(e.g. how the required depth changes with mark value and directive verb); do not repeat the marking feedback list.",
        f"SUBJECT: {ctx['subject_name']}", f"QUESTION ({ctx['marks']} marks, directive verb: {_directive(ctx.get('directive_verb'))}):\n{ctx['question']}",
        f"MARK AWARDED: {ctx['mark']} / {ctx['marks']}", f"STUDENT RESPONSE:\n<<<RESPONSE\n{ctx['response']}\nRESPONSE>>>",
        f"MARKER'S NOTES: {json.dumps(ctx.get('feedback', {}), ensure_ascii=False)[:3000]}",
        'Reply ONLY with JSON: {"explanation": "..."}',
    ])


def model_answer(ctx: dict) -> str:
    return "\n\n".join([
        f"TASK: Write a Band 6-standard model response to this {ctx['subject_name']} question, written specifically for it. "
        "Do not reproduce any published sample answer. For Legal Studies cite only the evidence provided.",
        f"QUESTION ({ctx['marks']} marks):\n{ctx['question']}",
        f"STIMULUS:\n{ctx.get('stimulus') or '(none)'}",
        f"EVIDENCE (Legal only): {json.dumps(ctx.get('evidence', []), ensure_ascii=False)}",
        'Reply ONLY with JSON: {"model_answer": "..."}',
    ])


def variant(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Write a NEW practice question testing the same skill as the question below, for the 2027 syllabus. "
        "It will be labelled GENERATED (or ADAPTED FROM HISTORICAL QUESTION). Do not claim it is an HSC question. "
        "For Mathematics give a machine-checkable final answer.",
        f"SUBJECT: {ctx['subject_name']}; TOPIC: {ctx.get('topic', '')}; MARKS: {ctx.get('marks')}",
        f"ORIGINAL QUESTION:\n{ctx['question']}",
        'Reply ONLY with JSON: {"question_text": "...", "marks": n, "answer_type": "num|expr|set|antiderivative|none", '
        '"answer_value": "sympy-parsable or null", "model_answer": "... or null", "worked_steps": ["..."]}',
    ])


def mapping(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Map this historical or imported question to the syllabus that applies to the student's 2027 HSC. "
        "Mathematics Advanced ONLY (Extension content must be REJECT with is_extension_content=true). "
        "Classify relevance: DIRECT (still directly applicable), PARTIAL (part applicable), ADAPTABLE (valuable skill, needs modification), "
        "REJECT (removed/obsolete/irrelevant content). For English, questions written for superseded prescribed texts are at most ADAPTABLE. "
        "For Legal Studies, judge QUESTION SKILL RELEVANCE separately from LEGAL FACT CURRENCY (current|check|outdated).",
        f"SUBJECT: {ctx['subject_name']}; SOURCE: {ctx.get('source', '')} ({ctx.get('year', '')})",
        f"AVAILABLE 2027 TOPICS (use one topic_code exactly): {json.dumps(ctx['topics'], ensure_ascii=False)}",
        f"QUESTION:\n{ctx['question']}",
        'Reply ONLY with JSON: {"topic_code": "...", "focus_area": "...", "outcome_code": null, "content_descriptor": null, '
        '"relevance": "DIRECT|PARTIAL|ADAPTABLE|REJECT", "relevance_score": 0..1, "confidence": 0..1, "reason": "...", '
        '"skill_relevance": null, "legal_fact_currency": null, "is_extension_content": false}',
    ])


def classify(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Classify this exam question.", f"SUBJECT: {ctx['subject_name']}", f"QUESTION:\n{ctx['question']}",
        'Reply ONLY with JSON: {"question_type": "mcq|short_answer|extended|working", "directive_verb": "...", "marks": n, '
        '"difficulty": 1|2|3, "estimated_minutes": n}',
    ])


def legal_summary(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Summarise this legal source for a Legal Studies evidence bank. Use ONLY the text provided; do not add facts. "
        "If the date or jurisdiction is not in the text, use null.",
        f"SOURCE URL: {ctx.get('url', '')}", f"SYLLABUS TOPICS: {ctx.get('topics', '')}",
        f"SOURCE TEXT (truncated):\n<<<SOURCE\n{ctx['text'][:12000]}\nSOURCE>>>",
        'Reply ONLY with JSON: {"title": "...", "date": "...", "jurisdiction": "...", "item_type": "legislation|case|law_reform|report|inquiry|treaty|media", '
        '"issue": "...", "summary": "...", "legal_significance": "...", "syllabus_link": "..."}',
    ])
