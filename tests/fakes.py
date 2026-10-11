"""A fake AI provider for tests: returns canned JSON strings (valid or malformed)."""
from __future__ import annotations

import json

from app.ai.base import AIProvider


class FakeProvider(AIProvider):
    name = "fake"
    generative = True
    vision = True
    model = "fake-model"

    def __init__(self, replies: list[str] | None = None, default: dict | None = None):
        self.replies = list(replies or [])
        self.default = default
        self.prompts: list[str] = []
        self.images: list[list[tuple[str, bytes]]] = []

    def _complete(self, system: str, user: str, images: list[tuple[str, bytes]] | None = None) -> str:
        self.prompts.append(user)
        self.images.append(list(images or []))
        if self.replies:
            return self.replies.pop(0)
        return json.dumps(self.default or {})


def marking_json(mark=2.0, possible=4.0, **extra) -> str:
    base = {
        "mark_awarded": mark, "mark_possible": possible, "confidence": 0.7, "performance_level": "Band 4 standard",
        "criteria": [{"name": "Analysis", "judgement": "partly met", "comment": "Identifies but does not analyse"}],
        "outcomes": ["EA12-1"], "strengths": ["Relevant quotation"], "weaknesses": ["Descriptive"],
        "errors": [{"category": "technique identification without analysis", "description": "Names the metaphor without its effect"}],
        "dimensions": {"analysis": "limited"}, "next_level": "Explain how form shapes meaning", "improvements": ["Link technique to idea"],
        "model_answer": "A Band 6 response that analyses the metaphor and its effect on the representation of memory in detail.",
        "comparison": "The model connects the image to memory; yours stops at identification.",
        "improved_answer": "Your answer, improved.", "revision_recommendation": ["Practise analysing imagery"],
    }
    base.update(extra)
    return json.dumps(base)
