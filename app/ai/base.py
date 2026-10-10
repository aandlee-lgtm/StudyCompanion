"""Provider-neutral AI interface. Add a provider by subclassing ``AIProvider`` and
implementing ``_complete`` (one chat completion returning text)."""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai import prompts
from app.ai.schemas import ClassifyResult, LegalSourceSummary, MappingResult, MarkingResult, ModelAnswer, QuestionVariant, WhyLost

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


class AIProvider(ABC):
    name = "base"
    generative = True

    @abstractmethod
    def _complete(self, system: str, user: str) -> str: ...

    def complete_json(self, system: str, user: str, schema: type[T], retries: int = 1) -> T:
        """Call the model and validate its JSON. Malformed output is retried once with the
        validation error, then rejected — it never reaches the database."""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            prompt = user if attempt == 0 else f"{user}\n\nYour previous reply was invalid ({last_err}). Reply with ONLY a JSON object matching the schema."
            raw = self._complete(system, prompt)
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

    def mark_response(self, ctx: dict) -> MarkingResult:
        return self.complete_json(prompts.SYSTEM, prompts.marking(ctx), MarkingResult)

    def generate_feedback(self, ctx: dict) -> WhyLost:
        return self.complete_json(prompts.SYSTEM, prompts.why_lost(ctx), WhyLost)

    def generate_model_answer(self, ctx: dict) -> ModelAnswer:
        return self.complete_json(prompts.SYSTEM, prompts.model_answer(ctx), ModelAnswer)

    def generate_question_variant(self, ctx: dict) -> QuestionVariant:
        return self.complete_json(prompts.SYSTEM, prompts.variant(ctx), QuestionVariant)

    def summarise_legal_source(self, ctx: dict) -> LegalSourceSummary:
        return self.complete_json(prompts.SYSTEM, prompts.legal_summary(ctx), LegalSourceSummary)
