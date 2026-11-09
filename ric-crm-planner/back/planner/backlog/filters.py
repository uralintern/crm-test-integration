"""Фильтры дерева бэклога из параметров запроса (BL-23, BL-24, BL-25, S-02)."""

from dataclasses import dataclass, field
from datetime import date

from rest_framework.exceptions import ValidationError

from .statuses import BacklogStatus

SPRINT_NONE = "none"


@dataclass(frozen=True)
class BacklogFilters:
    executor_id: int | None = None
    responsible_id: int | None = None
    statuses: frozenset = field(default_factory=frozenset)
    # id спринта, SPRINT_NONE («вне спринта») или None (фильтр не задан).
    sprint: int | str | None = None
    date_from: date | None = None
    date_to: date | None = None
    query: str = ""

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.executor_id is not None,
                self.responsible_id is not None,
                self.statuses,
                self.sprint is not None,
                self.date_from,
                self.date_to,
                self.query,
            )
        )

    @property
    def only_text_query(self) -> bool:
        return bool(self.query) and BacklogFilters(query="") == BacklogFilters(
            executor_id=self.executor_id,
            responsible_id=self.responsible_id,
            statuses=self.statuses,
            sprint=self.sprint,
            date_from=self.date_from,
            date_to=self.date_to,
        )


def _parse_int(params, name, errors):
    raw = (params.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        errors[name] = "Ожидается числовой идентификатор."
        return None


def _parse_date(params, name, errors):
    raw = (params.get(name) or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors[name] = "Ожидается дата в формате ГГГГ-ММ-ДД."
        return None


def _parse_statuses(params, errors):
    raw = (params.get("status") or "").strip()
    if not raw:
        return frozenset()
    codes = {code.strip() for code in raw.split(",") if code.strip()}
    unknown = codes - set(BacklogStatus.values)
    if unknown:
        errors["status"] = (
            f"Неизвестные статусы: {', '.join(sorted(unknown))}. "
            f"Допустимо: {', '.join(BacklogStatus.values)}."
        )
    return frozenset(codes & set(BacklogStatus.values))


def _parse_sprint(params, errors):
    raw = (params.get("sprint") or "").strip()
    if not raw:
        return None
    if raw.lower() == SPRINT_NONE:
        return SPRINT_NONE
    try:
        return int(raw)
    except ValueError:
        errors["sprint"] = "Ожидается id спринта или «none»."
        return None


def parse_backlog_filters(params) -> BacklogFilters:
    errors = {}
    filters = BacklogFilters(
        executor_id=_parse_int(params, "executor", errors),
        responsible_id=_parse_int(params, "responsible", errors),
        statuses=_parse_statuses(params, errors),
        sprint=_parse_sprint(params, errors),
        date_from=_parse_date(params, "date_from", errors),
        date_to=_parse_date(params, "date_to", errors),
        query=(params.get("q") or "").strip(),
    )
    if filters.date_from and filters.date_to and filters.date_to < filters.date_from:
        errors["date_to"] = "Конец диапазона раньше начала."
    if errors:
        raise ValidationError(errors)
    return filters
