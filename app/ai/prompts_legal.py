"""Legal Studies parts of the structured marking prompt (audit legal-13/14).

- the 14 section-9 assessment dimensions replace the generic (English-flavoured) ones;
- today's date and the contemporary window, so old material is treated as background;
- the evidence bank with each item's verification status and legal status;
- the allowed error categories;
- corrections must name a bank item or begin 'Possible issue — verify:', so the model's own
  (possibly stale) knowledge is never presented as a correction."""
from __future__ import annotations

import json

# spec section 9: what Legal Studies feedback assesses
LEGAL_DIMENSIONS = {
    "knowledge of relevant law": "...", "legal terminology": "...", "response to the directive verb": "...", "judgement": "...",
    "argument": "...", "use of legislation": "...", "use of cases": "...", "contemporary evidence": "...", "law reform": "...",
    "effectiveness analysis": "...", "responsiveness to stimulus": "... (or 'no stimulus')", "structure": "...", "clarity": "...",
    "integration of evidence": "...",
}

LEGAL_ERROR_CATEGORIES = [
    "missing authority", "outdated legislation", "weak judgement", "description instead of evaluation",
    "insufficient contemporary evidence", "poor use of cases", "failure to address directive verb",
    "unverified/invented authority", "no law reform", "stimulus not used", "imprecise legal terminology",
]

LEGAL_EXTRA = {
    "dimensions": LEGAL_DIMENSIONS,
    "errors": [{"category": "one of the allowed Legal error categories", "description": "..."}],
    "marking_rationale": "why this mark: which criteria level the response reaches and what keeps it from the next",
    "missing_elements": ["..."],
    "corrections": ["each names the evidence-bank item it relies on by exact title, or begins 'Possible issue — verify:'"],
    "evidence_suggestions": ["ONLY items from the evidence bank below, cited by exact title"],
    "improved_argument": "claim, law, evidence, evaluation, link — citing only bank items",
    "improvement_task": "one specific task aimed at the largest gap",
    "references_used": ["exact titles of every legal authority mentioned anywhere in your output"],
}


def shape_extra(ctx: dict) -> dict:
    return json.loads(json.dumps(LEGAL_EXTRA))


def _today(ctx: dict) -> str:
    if ctx.get("today"):
        return str(ctx["today"])
    from app.services import clock

    return clock.today().isoformat()


def marking_sections(ctx: dict) -> list[str]:
    years = int(ctx.get("contemporary_years") or 5)
    return [
        f"TODAY: {_today(ctx)}. Treat evidence older than {years} years as background, not contemporary; a 'contemporary' example "
        f"must be dated within the last {years} years.",
        "LEGAL EVIDENCE BANK (verification status per item; cite ONLY these items, by exact title. 'unverified' items must be "
        "described as 'to be verified'; items whose legal_status is repealed or superseded are outdated law. Do not cite any other "
        "case, Act, treaty, statistic or report, and never invent one):\n" + json.dumps(ctx.get("evidence", []), ensure_ascii=False, indent=1),
        "ASSESS these Legal Studies dimensions (NSW Stage 6): " + ", ".join(LEGAL_DIMENSIONS) + ".",
        "ALLOWED ERROR CATEGORIES (use these exact words): " + "; ".join(LEGAL_ERROR_CATEGORIES) + ".",
        "CORRECTIONS: if the response relies on outdated or incorrect law, say so in 'corrections'. Every correction must name the "
        "evidence-bank item it relies on (exact title) or begin 'Possible issue — verify:' when the bank does not settle it. "
        "If the student cites an authority that is not in the bank, do not confirm it exists: use 'unverified/invented authority'.",
        "Your model answer and suggestions may cite only bank items; anything else will be removed before the student sees it.",
    ]
