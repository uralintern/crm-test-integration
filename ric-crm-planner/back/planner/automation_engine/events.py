"""Событие автоматизации планировщика."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PlannerAutomationEvent:
    code: str
    entity_type: str
    entity_id: str
    item: dict[str, Any]
    previous_item: dict[str, Any] | None
    team: dict[str, Any] | None
    event_id: int
    team_id: int | None
    fingerprint: str
