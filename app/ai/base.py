"""Provider-neutral AI interface. Add a provider by subclassing ``AIProvider`` and
implementing ``_complete`` (one chat completion returning text). Providers that can read
images accept ``images`` — a list of ``(media_type, bytes)`` — and set ``vision = True``."""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai import prompts
from app.ai.schemas import (
    ClassifyResult,
    LegalSourceSummary,
    MappingResult,
    MarkingResult,
    ModelAnswer,
    QuestionVariant,
    WhyLost,
    WorkingReading,
)

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AIError(RuntimeError):
    pass


class AIUnavailable(AIError):
    """Raised by providers that cannot perform a generative task (e.g. offline mode)."""


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


Image = tuple[str, bytes]  # (media type, image bytes)


class AIProvider(ABC):
    name = "base"
    generative = True
    vision = False

    @abstractmethod
    def _complete(self, system: str, user: str) -> str: ...

    def complete_json(self, system: str, user: str, schema: type[T], retries: int = 1, images: list[Image] | None = None) -> T:
        """Call the model and validate its JSON. Malformed output is retried once with the
        validation error, then rejected — it never reaches the database."""
        if images and not self.vision:
            raise AIUnavailable(f"The '{self.name}' provider cannot read images")
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            prompt = user if attempt == 0 else f"{user}\n\nYour previous reply was invalid ({last_err}). Reply with ONLY a JSON object matching the schema."
            raw = self._complete(system, prompt, images=images) if images else self._complete(system, prompt)
            try:
                return schema.model_validate(extract_json(raw))
            except (ValueError, ValidationError) as exc:
                last_err = exc
                log.warning("AI JSON validation failed (%s): %s", schema.__name__, exc)
        raise AIError(f"AI output failed validation: {last_err}")

    # ----- tasks ---------------------------------------------------------------
    def classify_question(self, ctx: dict) -> ClassifyResult:
        return self.complete_json(prompts.SYSTEM, prompts.classify(ctx), ClassifyResult)

    def map_to_syllabus(self, ctx: dict) -> MappingResult:
        return self.complete_json(prompts.SYSTEM, prompts.mapping(ctx), MappingResult)

    def mark_response(self, ctx: dict, images: list[Image] | None = None) -> MarkingResult:
        """``images``: photos of the student's handwritten working, read alongside the response."""
        user = prompts.marking(ctx)
        if images:
            from app.ai import prompts_working

            user += prompts_working.marking_addendum(len(images))
        return self.complete_json(prompts.SYSTEM, user, MarkingResult, images=images)

    def read_working(self, ctx: dict, images: list[Image]) -> WorkingReading:
        """Transcribe photographed handwritten working and the final answer (not marked)."""
        from app.ai import prompts_working

        return self.complete_json(prompts_working.SYSTEM, prompts_working.read_working(ctx, len(images)), WorkingReading, images=images)

    def generate_feedback(self, ctx: dict) -> WhyLost:
        return self.complete_json(prompts.SYSTEM, prompts.why_lost(ctx), WhyLost)

    def generate_model_answer(self, ctx: dict) -> ModelAnswer:
        return self.complete_json(prompts.SYSTEM, prompts.model_answer(ctx), ModelAnswer)

    def generate_question_variant(self, ctx: dict) -> QuestionVariant:
        return self.complete_json(prompts.SYSTEM, prompts.variant(ctx), QuestionVariant)

    def summarise_legal_source(self, ctx: dict) -> LegalSourceSummary:
        return self.complete_json(prompts.SYSTEM, prompts.legal_summary(ctx), LegalSourceSummary)
