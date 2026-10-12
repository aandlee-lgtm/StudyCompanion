"""Never serve an imported question before every subtopic it needs is unlocked (sources-05).

``Question.plan_item_id`` is the primary (latest-in-sequence) subtopic, but a multi-topic question
also lists every other subtopic it needs in ``import_meta['required_plan_item_ids']`` (mirrored by
``question_plan_items`` rows). The selection engine calls :func:`requirements_unlocked` with its
already-loaded plan so this costs no extra queries."""
from __future__ import annotations

from collections.abc import Mapping

from app.models.common import APPROVAL_APPROVED, LOCKED, REJECT


def required_ids(q) -> list[int]:
    ids = [int(i) for i in ((q.import_meta or {}).get("required_plan_item_ids") or []) if i]
    if q.plan_item_id and q.plan_item_id not in ids:
        ids.append(q.plan_item_id)
    return ids


def requirements_unlocked(plan: Mapping[int, object], q) -> bool:
    """True when the question has a subtopic and none of its required subtopics is LOCKED,
    inactive (an option not studied) or missing from the plan. UNMAPPED questions, and unseen-text
    questions without a linked text, are never servable."""
    ids = required_ids(q)
    if not ids or (q.import_meta or {}).get("mapping_state") == "UNMAPPED":
        return False
    if q.category == "unseen" and q.stimulus_id is None:  # english-11: never an unseen question without its text
        return False
    for i in ids:
        it = plan.get(i)
        if it is None or it.status == LOCKED or not it.active:
            return False
    return True


def blocked_reason(plan: Mapping[int, object], q) -> str | None:
    """Plain-language reason a question is not in the daily pool (library and review)."""
    if q.approval_status != APPROVAL_APPROVED or not q.approved:
        return "Not approved"
    if q.relevance_status == REJECT or q.is_extension:
        return "Rejected content"
    if not required_ids(q) or (q.import_meta or {}).get("mapping_state") == "UNMAPPED":
        return "No subtopic"
    if q.category == "unseen" and q.stimulus_id is None:
        return "No linked text"
    locked = [plan[i] for i in required_ids(q) if i in plan and (plan[i].status == LOCKED or not plan[i].active)]
    if locked:
        return "Waits for " + ", ".join(f"{it.code}" for it in locked)
    return None
