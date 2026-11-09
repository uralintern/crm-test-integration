"""Модели бэклога.

Иерархия: этап → задача → подзадача → работа (пункт чек-листа подзадачи).
Команды живут в JSON планировщика, поэтому объекты ссылаются на них по `team_id`.
"""

from django.conf import settings
from django.db import models, transaction

from .statuses import BacklogStatus


class BacklogCodeMixin(models.Model):
    """Уникальный код объекта для постоянной ссылки (BL-35): T-<id> или S-<id>.

    Код всегда в верхнем регистре, поэтому поиск идёт точным сравнением по уникальному индексу.
    """

    CODE_PREFIX = ""

    code = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Вставка и присвоение кода — одна транзакция: строка без кода не останется.
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.code:
                self.code = f"{self.CODE_PREFIX}-{self.pk}"
                type(self).objects.filter(pk=self.pk).update(code=self.code)


class BacklogSprint(models.Model):
    team_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_BACKLOG_SPRINT"
        ordering = ("start_date", "id")
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="backlog_sprint_end_after_start",
            )
        ]

    def __str__(self):
        return f"Спринт «{self.title}» команды #{self.team_id}"


class BacklogStage(models.Model):
    """Этап: группа задач без ответственного (BR-02)."""

    team_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_BACKLOG_STAGE"
        ordering = ("position", "id")
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_date__isnull=True)
                | models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="backlog_stage_end_after_start",
            )
        ]

    def __str__(self):
        return f"Этап «{self.title}»"


class BacklogTask(BacklogCodeMixin):
    """Задача внутри этапа: один ответственный (BL-14)."""

    CODE_PREFIX = "T"

    stage = models.ForeignKey(BacklogStage, on_delete=models.CASCADE, related_name="tasks")
    # Индекс по team_id даёт составной индекс (team_id, status) ниже.
    team_id = models.BigIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlog_responsible_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=BacklogStatus.choices, default=BacklogStatus.NEW)
    # Даты, заданные вручную; фактические сроки пересчитываются по подзадачам («Карточки» §4).
    start_date = models.DateField()
    end_date = models.DateField()
    sprint = models.ForeignKey(
        BacklogSprint, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks"
    )
    rework_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="rework_tasks"
    )
    position = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_BACKLOG_TASK"
        ordering = ("position", "id")
        indexes = [models.Index(fields=["team_id", "status"], name="backlog_task_team_status")]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="backlog_task_end_after_start",
            )
        ]

    def __str__(self):
        return f"{self.code or 'T-?'} {self.title}"

    def save(self, *args, **kwargs):
        # Команда задачи всегда совпадает с командой этапа: по ней проверяются права.
        self.team_id = self.stage.team_id
        super().save(*args, **kwargs)


class BacklogSubtask(BacklogCodeMixin):
    """Подзадача внутри задачи: один исполнитель (BL-15)."""

    CODE_PREFIX = "S"

    task = models.ForeignKey(BacklogTask, on_delete=models.CASCADE, related_name="subtasks")
    # Индекс по team_id даёт составной индекс (team_id, status) ниже.
    team_id = models.BigIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    executor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlog_executed_subtasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=BacklogStatus.choices, default=BacklogStatus.NEW)
    start_date = models.DateField()
    end_date = models.DateField()
    sprint = models.ForeignKey(
        BacklogSprint, null=True, blank=True, on_delete=models.SET_NULL, related_name="subtasks"
    )
    rework_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="rework_subtasks"
    )
    position = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_BACKLOG_SUBTASK"
        ordering = ("position", "id")
        indexes = [models.Index(fields=["team_id", "status"], name="backlog_subtask_team_status")]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="backlog_subtask_end_after_start",
            )
        ]

    def __str__(self):
        return f"{self.code or 'S-?'} {self.title}"

    def save(self, *args, **kwargs):
        # Команда подзадачи всегда совпадает с командой задачи: по ней проверяются права.
        self.team_id = self.task.team_id
        super().save(*args, **kwargs)


class BacklogWorkItem(models.Model):
    """Работа — пункт чек-листа подзадачи; исполнитель наследуется от подзадачи (BR-03)."""

    subtask = models.ForeignKey(BacklogSubtask, on_delete=models.CASCADE, related_name="work_items")
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_BACKLOG_WORK_ITEM"
        ordering = ("position", "id")

    def __str__(self):
        return self.title


class BacklogComment(models.Model):
    """Комментарий к задаче или подзадаче («Карточки» §3)."""

    task = models.ForeignKey(
        BacklogTask, null=True, blank=True, on_delete=models.CASCADE, related_name="comments"
    )
    subtask = models.ForeignKey(
        BacklogSubtask, null=True, blank=True, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CRM_BACKLOG_COMMENT"
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                check=(models.Q(task__isnull=False) & models.Q(subtask__isnull=True))
                | (models.Q(task__isnull=True) & models.Q(subtask__isnull=False)),
                name="backlog_comment_single_target",
            )
        ]

    def __str__(self):
        return f"Комментарий #{self.pk}"
