"""Статусы задач и подзадач бэклога (BL-28) и правила переходов (BL-30)."""

from django.db import models


class BacklogStatus(models.TextChoices):
    NEW = "new", "Новая задача"
    IN_SPRINT = "in_sprint", "В спринте"
    REVIEW = "review", "На проверке"
    DONE = "done", "Завершена"


# Порядок статусов: переходы разрешены только вперёд, перескакивать можно.
STATUS_ORDER = [BacklogStatus.NEW, BacklogStatus.IN_SPRINT, BacklogStatus.REVIEW, BacklogStatus.DONE]

# Статусы, которые показываются на канбане спринта; «Завершена» с доски уходит.
KANBAN_STATUSES = [BacklogStatus.IN_SPRINT, BacklogStatus.REVIEW]


def transition_error(current: str, target: str) -> str | None:
    """Текст ошибки, если переход current → target запрещён, иначе None."""
    if target == current:
        return None
    if target == BacklogStatus.DONE:
        return "Статус «Завершена» ставится только действием «Завершить»."
    if STATUS_ORDER.index(target) < STATUS_ORDER.index(current):
        return (
            f"Нельзя вернуть статус назад: «{BacklogStatus(current).label}» → «{BacklogStatus(target).label}». "
            "Если работа не принята, создайте доработку."
        )
    return None
