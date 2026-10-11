"""Validated shapes for English AI output (owner: english-logic).

``EnglishMarking`` extends the shared ``MarkingResult``: error categories are normalised to the
allowed list (spec 23 plus Craft of Writing), and structured comparison / improvement fields are
kept. Fields stay optional at parse time so a thin reply is not thrown away; completeness is
checked afterwards (``missing_fields``), the AI is re-asked once for just the missing parts,
and anything still missing is shown as 'Not assessed'."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import ErrorItem, MarkingResult

# Spec section 23 (English) plus Craft of Writing categories (english-04/18).
ANALYTICAL_ERRORS = ["insufficient textual evidence", "technique identification without analysis", "weak thesis", "descriptive response",
                     "poor comparison", "limited evaluation", "imprecise expression"]
CRAFT_ERRORS = ["telling not showing", "uncontrolled tense or point of view", "reflection not linked to purpose", "structure lacks purpose",
                "generic or clichéd detail"]
ALL_ERRORS = ANALYTICAL_ERRORS + CRAFT_ERRORS

DIMENSIONS = ("textual evidence", "analysis", "form", "language", "argument", "structure", "expression", "precision", "sophistication")
_DIM_ALIASES = {"evidence": "textual evidence", "textual_evidence": "textual evidence", "use of evidence": "textual evidence",
                "form/language": "form", "argument/thesis": "argument", "thesis": "argument", "sophistication of interpretation": "sophistication"}


def canonical_category(raw: str) -> str | None:
    c = (raw or "").strip().lower()
    if c in ALL_ERRORS:
        return c
    for a in ALL_ERRORS:
        if a in c or c in a:
            return a
    keys = {"evidence": "insufficient textual evidence", "quot": "insufficient textual evidence", "identif": "technique identification without analysis",
            "thesis": "weak thesis", "descript": "descriptive response", "retell": "descriptive response", "compar": "poor comparison",
            "evaluat": "limited evaluation", "judg": "limited evaluation", "express": "imprecise expression", "precis": "imprecise expression",
            "telling": "telling not showing", "tense": "uncontrolled tense or point of view", "point of view": "uncontrolled tense or point of view",
            "reflection": "reflection not linked to purpose", "structure": "structure lacks purpose", "clich": "generic or clichéd detail"}
    return next((v for k, v in keys.items() if k in c), None)


class EnglishError(ErrorItem):
    @field_validator("category", mode="after")
    @classmethod
    def _canonical(cls, v: str) -> str:
        return canonical_category(v) or "other"


class ComparisonPoints(BaseModel):
    what_model_does: str = ""
    descriptive_moments: str = ""
    evidence_integration: str = ""
    development: str = ""
    expression: str = ""
    sophistication: str = ""


class ImprovementSinceLast(BaseModel):
    addressed: list[str] = []
    still_missing: list[str] = []
    new_issues: list[str] = []


class CriterionEvidence(BaseModel):
    criterion: str
    student_phrase: str = ""
    judgement: str = ""


class EnglishMarking(MarkingResult):
    errors: list[EnglishError] = []
    comparison_points: ComparisonPoints | None = None
    improvement_since_last: ImprovementSinceLast | None = None
    criterion_evidence: list[CriterionEvidence] = []

    @field_validator("errors", mode="before")
    @classmethod
    def _keep_original(cls, v):
        # keep the AI's own wording when its category is not one of ours
        out = []
        for e in v or []:
            if isinstance(e, dict) and e.get("category") and canonical_category(e["category"]) is None:
                e = {**e, "description": f"({e['category']}) {e.get('description', '')}".strip()}
            out.append(e)
        return out

    @field_validator("dimensions", mode="before")
    @classmethod
    def _dims(cls, v):
        if not isinstance(v, dict):
            return v
        return {_DIM_ALIASES.get(str(k).strip().lower(), str(k).strip().lower()): ("" if val is None else str(val)) for k, val in v.items()}


class EnglishPatch(BaseModel):
    """Re-ask for only the elements a first reply left out."""
    performance_level: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    dimensions: dict[str, str] = {}
    next_level: str = ""
    improvements: list[str] = []
    comparison_points: ComparisonPoints | None = None
    improved_answer: str = ""

    @field_validator("dimensions", mode="before")
    @classmethod
    def _dims(cls, v):
        return EnglishMarking._dims(v)


class SentenceUpgrade(BaseModel):
    student_sentence: str = ""
    upgraded: str = ""


class EnglishWhyLost(BaseModel):
    did_well_specific: str = Field(min_length=10)
    gap_principle: str = Field(min_length=10)
    passage_specific_next_step: str = Field(min_length=10)
    example_sentence_upgrade: SentenceUpgrade | None = None


def missing_fields(r: MarkingResult, has_model: bool, retry: bool) -> list[str]:
    """Which of the required English feedback elements an AI reply left empty."""
    missing = [f for f in ("performance_level", "next_level") if not getattr(r, f, "").strip()]
    if not r.strengths:
        missing.append("strengths")
    if not r.weaknesses and r.mark_awarded < r.mark_possible:
        missing.append("weaknesses")
    if len(r.improvements) < 2 and r.mark_awarded < r.mark_possible:
        missing.append("improvements")
    dims = {k for k, v in (r.dimensions or {}).items() if str(v).strip()}
    if any(d not in dims for d in DIMENSIONS):
        missing.append("dimensions")
    cp = getattr(r, "comparison_points", None)
    if has_model and not (cp and cp.what_model_does.strip()) and not r.comparison.strip():
        missing.append("comparison_points")
    if not r.improved_answer.strip() and r.mark_awarded < r.mark_possible:
        missing.append("improved_answer")
    return missing
