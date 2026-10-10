"""Legal Studies parts of the structured marking prompt."""
from __future__ import annotations

import json

LEGAL_EXTRA = {
    "marking_rationale": "...", "missing_elements": ["..."], "corrections": ["factual/legal corrections, e.g. outdated legislation"],
    "evidence_suggestions": ["ONLY items from the provided evidence list, cited by exact title"], "improved_argument": "...",
    "improvement_task": "one specific task", "references_used": ["exact titles of every legal authority mentioned anywhere in your output"],
}


def shape_extra(ctx: dict) -> dict:
    return dict(LEGAL_EXTRA)


def marking_sections(ctx: dict) -> list[str]:
    return [
        "VERIFIED LEGAL EVIDENCE AVAILABLE (you may cite ONLY these items, by exact title; items marked UNVERIFIED must be "
        "described as 'to be verified'; do not cite any other case, Act, statistic or report):\n"
        + json.dumps(ctx.get("evidence", []), ensure_ascii=False, indent=1),
        "If the student's response relies on outdated or incorrect law, say so in 'corrections'.",
    ]
