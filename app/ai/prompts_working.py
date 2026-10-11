"""Prompts for photographed handwritten working (Mathematics)."""
from __future__ import annotations

import json

SYSTEM = (
    "You transcribe a NSW Year 12 student's handwritten mathematics working from photographs, for a study app. "
    "You are a careful, literal reader: you copy exactly what is written, including mistakes, and never correct, "
    "complete or improve the student's work. Where a symbol or line cannot be read with confidence you say so instead "
    "of guessing. You always reply with a single JSON object and nothing else."
)

NOTATION = (
    "Write mathematics in this plain-text notation (the app's answer box reads it): * for multiplication, ^ for powers, "
    "sqrt(...), ln(...), log(...), e^(...), sin(x), cos(x), tan(x), pi, fractions as (numerator)/(denominator), "
    "intervals like [0, 2) or x > 3, several answers separated by commas (e.g. x = 1, x = -2), ± as +/-."
)


def read_working(ctx: dict, n_images: int) -> str:
    parts = ctx.get("parts") or []
    return (
        f"The {n_images} attached photo(s) show, in order, the student's handwritten working for this question.\n\n"
        f"QUESTION ({ctx.get('marks', '?')} marks):\n{ctx.get('question', '')}\n"
        + (f"\nPARTS: {json.dumps(parts)}\n" if parts else "")
        + f"\nANSWER FORMAT EXPECTED: {ctx.get('answer_format') or 'a value or expression'}\n\n"
        "Tasks:\n"
        "1. working_text: transcribe the working line by line, in order (one line per written line, '\\n' between lines). "
        "Keep crossed-out lines out, but mention them in notes if they matter.\n"
        "2. final_answer: the student's own final answer exactly as written (usually the last line, boxed or underlined), "
        "converted to the notation below. If the question has parts, put each part's final answer in part_answers "
        "keyed by the part label (e.g. \"a\", \"b(i)\") and leave final_answer empty.\n"
        "3. unclear: list anything you could not read with confidence (e.g. 'line 3: exponent could be 2 or 3').\n"
        "4. legible: false if the photos do not show readable working for this question (wrong page, blurred, blank).\n"
        "Do not solve the question and do not judge whether the answer is correct.\n\n"
        f"{NOTATION}\n\n"
        'Reply with JSON: {"legible": true, "final_answer": "", "part_answers": {}, "working_text": "", "unclear": [], "notes": ""}'
    )


def marking_addendum(n_images: int) -> str:
    return (
        f"\n\nThe student's working is ALSO attached as {n_images} photo(s) of handwriting, in page order. Read it as their "
        "working: award method marks only for steps that are actually written there (or in the typed working), judged "
        "against the worked solution. If part of the handwriting is illegible, say so in the rationale and do not award "
        "marks for steps you cannot read."
    )
