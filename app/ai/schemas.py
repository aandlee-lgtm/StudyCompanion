"""Strict schemas for everything an AI provider returns. Output that fails validation is
never stored (see ``AIProvider.complete_json``)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ErrorCategory = str


class Criterion(BaseModel):
    name: str
    judgement: str = ""
    comment: str = ""


class ErrorItem(BaseModel):
    category: str
    description: str


class MarkingResult(BaseModel):
    mark_awarded: float = Field(ge=0)
    mark_possible: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1, default=0.5)
    performance_level: str = ""
    criteria: list[Criterion] = []
    outcomes: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    errors: list[ErrorItem] = []
    dimensions: dict[str, str] = {}
    next_level: str = ""
    improvements: list[str] = []
    model_answer: str = ""
    comparison: str = ""
    improved_answer: str = ""
    revision_recommendation: list[str] = []
    # Legal Studies extras
    marking_rationale: str = ""
    missing_elements: list[str] = []
    corrections: list[str] = []
    evidence_suggestions: list[str] = []
    improved_argument: str = ""
    improvement_task: str = ""
    references_used: list[str] = []

    @model_validator(mode="after")
    def _mark_in_range(self):
        if self.mark_awarded > self.mark_possible:
            raise ValueError("mark_awarded exceeds mark_possible")
        return self

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        if isinstance(v, str):
            return {"low": 0.3, "medium": 0.6, "high": 0.85}.get(v.lower(), 0.5)
        return v


class MappingResult(BaseModel):
    topic_code: str
    focus_area: str = ""
    outcome_code: str | None = None
    content_descriptor: str | None = None
    relevance: Literal["DIRECT", "PARTIAL", "ADAPTABLE", "REJECT"]
    relevance_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reason: str
    skill_relevance: str | None = None
    legal_fact_currency: str | None = None
    is_extension_content: bool = False


class ClassifyResult(BaseModel):
    question_type: Literal["mcq", "short_answer", "extended", "working"]
    directive_verb: str | None = None
    marks: int | None = Field(default=None, ge=0, le=40)
    difficulty: int = Field(ge=1, le=3, default=2)
    estimated_minutes: float | None = Field(default=None, ge=0, le=90)


class WhyLost(BaseModel):
    explanation: str = Field(min_length=20)


class ModelAnswer(BaseModel):
    model_answer: str = Field(min_length=20)


class QuestionVariant(BaseModel):
    question_text: str = Field(min_length=10)
    marks: int = Field(ge=1, le=20)
    answer_value: str | None = None
    answer_type: Literal["num", "expr", "set", "antiderivative", "none"] = "none"
    model_answer: str | None = None
    worked_steps: list[str] = []


class LegalSourceSummary(BaseModel):
    title: str
    date: str | None = None
    jurisdiction: str = ""
    item_type: str = "media"
    issue: str | None = None
    summary: str
    legal_significance: str = ""
    syllabus_link: str | None = None


class WorkingReading(BaseModel):
    """What the AI read from photos of handwritten working. A transcription, never a mark: the
    student confirms the final answer before it is marked like a typed answer."""

    legible: bool = True
    final_answer: str = Field(default="", max_length=400)
    part_answers: dict[str, str] = {}
    working_text: str = Field(default="", max_length=8000)
    unclear: list[str] = []
    notes: str = Field(default="", max_length=1000)

    @field_validator("part_answers")
    @classmethod
    def _short_parts(cls, v: dict[str, str]) -> dict[str, str]:
        return {str(k)[:20]: str(a)[:400] for k, a in list(v.items())[:12]}
