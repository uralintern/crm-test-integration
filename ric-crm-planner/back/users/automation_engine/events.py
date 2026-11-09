"""Событие CRM-автоматизации."""

from dataclasses import dataclass
from typing import Any
from users.models import Application


@dataclass
class CRMAutomationEvent:
    code: str
    application: Application
    previous_status: str
    event_id: int
    fingerprint: str
    request: Any = None
