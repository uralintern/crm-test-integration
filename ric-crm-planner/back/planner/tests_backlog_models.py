"""Модели бэклога: иерархия, коды, ограничения дат, удаление."""

from datetime import date

from django.db import IntegrityError, transaction

from planner.backlog.statuses import BacklogStatus
from planner.backlog_test_utils import OTHER_TEAM_ID, TEAM_ID, BacklogTestBase
from planner.models import (
    BacklogComment,
    BacklogStage,
    BacklogSubtask,
    BacklogTask,
    BacklogWorkItem,
)


class BacklogStatusTests(BacklogTestBase):
    def test_statuses_follow_bl28_in_order(self):
        self.assertEqual(
            [(choice.value, choice.label) for choice in BacklogStatus],
            [
                ("new", "Новая задача"),
                ("in_sprint", "В спринте"),
                ("review", "На проверке"),
                ("done", "Завершена"),
            ],
        )

    def test_new_task_and_subtask_start_as_new(self):
        task = self.make_task(self.make_stage())
        subtask = self.make_subtask(task)

        self.assertEqual(task.status, BacklogStatus.NEW)
        self.assertEqual(subtask.status, BacklogStatus.NEW)


class BacklogCodeTests(BacklogTestBase):
    def test_task_and_subtask_get_unique_codes_after_create(self):
        task = self.make_task(self.make_stage())
        subtask = self.make_subtask(task)

        task.refresh_from_db()
        subtask.refresh_from_db()
        self.assertEqual(task.code, f"T-{task.id}")
        self.assertEqual(subtask.code, f"S-{subtask.id}")

    def test_code_does_not_change_on_update(self):
        task = self.make_task(self.make_stage())
        code = task.code

        task.title = "Новое название"
        task.save()

        task.refresh_from_db()
        self.assertEqual(task.code, code)


class BacklogTeamConsistencyTests(BacklogTestBase):
    """Команда задачи и подзадачи всегда берётся у родителя: по ней проверяются права."""

    def test_task_and_subtask_take_team_from_parent(self):
        task = self.make_task(self.make_stage(team_id=TEAM_ID))
        task.team_id = OTHER_TEAM_ID
        task.save()
        subtask = BacklogSubtask.objects.create(
            task=task,
            team_id=OTHER_TEAM_ID,
            title="Подзадача",
            start_date=date(2026, 11, 3),
            end_date=date(2026, 11, 4),
        )

        task.refresh_from_db()
        subtask.refresh_from_db()
        self.assertEqual(task.team_id, TEAM_ID)
        self.assertEqual(subtask.team_id, TEAM_ID)

    def test_every_created_object_has_a_code(self):
        task = self.make_task(self.make_stage())
        self.make_subtask(task)

        self.assertFalse(BacklogTask.objects.filter(code__isnull=True).exists())
        self.assertFalse(BacklogSubtask.objects.filter(code__isnull=True).exists())


class BacklogDateConstraintTests(BacklogTestBase):
    """BL-20: окончание не может быть раньше начала — защищено и на уровне БД."""

    def assert_integrity_error(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_sprint_end_before_start_is_rejected(self):
        self.assert_integrity_error(lambda: self.make_sprint(start=date(2026, 11, 10), end=date(2026, 11, 1)))

    def test_stage_end_before_start_is_rejected(self):
        self.assert_integrity_error(
            lambda: self.make_stage(start_date=date(2026, 11, 10), end_date=date(2026, 11, 1))
        )

    def test_stage_dates_are_optional(self):
        stage = self.make_stage()

        self.assertIsNone(stage.start_date)
        self.assertIsNone(stage.end_date)

    def test_task_end_before_start_is_rejected(self):
        stage = self.make_stage()
        self.assert_integrity_error(lambda: self.make_task(stage, start=date(2026, 11, 10), end=date(2026, 11, 1)))

    def test_subtask_end_before_start_is_rejected(self):
        task = self.make_task(self.make_stage())
        self.assert_integrity_error(lambda: self.make_subtask(task, start=date(2026, 11, 10), end=date(2026, 11, 1)))

    def test_same_day_start_and_end_is_allowed(self):
        task = self.make_task(self.make_stage(), start=date(2026, 11, 5), end=date(2026, 11, 5))

        self.assertEqual(task.start_date, task.end_date)

    def test_work_item_due_date_is_optional(self):
        task = self.make_task(self.make_stage())
        work = self.make_work(self.make_subtask(task))

        self.assertIsNone(work.due_date)


class BacklogCommentConstraintTests(BacklogTestBase):
    def test_comment_belongs_to_exactly_one_object(self):
        task = self.make_task(self.make_stage())
        subtask = self.make_subtask(task)

        with self.assertRaises(IntegrityError), transaction.atomic():
            BacklogComment.objects.create(task=task, subtask=subtask, author=self.member, text="x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            BacklogComment.objects.create(author=self.member, text="x")

        comment = BacklogComment.objects.create(task=task, author=self.member, text="Комментарий")
        self.assertIsNotNone(comment.created_at)


class BacklogCascadeTests(BacklogTestBase):
    def test_deleting_stage_removes_whole_branch(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        subtask = self.make_subtask(task)
        self.make_work(subtask)
        BacklogComment.objects.create(subtask=subtask, author=self.member, text="x")

        stage.delete()

        self.assertFalse(BacklogTask.objects.exists())
        self.assertFalse(BacklogSubtask.objects.exists())
        self.assertFalse(BacklogWorkItem.objects.exists())
        self.assertFalse(BacklogComment.objects.exists())

    def test_deleting_user_keeps_tasks_without_responsible(self):
        stage = self.make_stage()
        task = self.make_task(stage, responsible=self.member)
        subtask = self.make_subtask(task, executor=self.member)

        self.member.delete()

        task.refresh_from_db()
        subtask.refresh_from_db()
        self.assertIsNone(task.responsible)
        self.assertIsNone(subtask.executor)

    def test_deleting_sprint_keeps_tasks(self):
        sprint = self.make_sprint()
        task = self.make_task(self.make_stage(), sprint=sprint, status=BacklogStatus.IN_SPRINT)

        sprint.delete()

        task.refresh_from_db()
        self.assertIsNone(task.sprint)

    def test_rework_task_links_to_original(self):
        stage = self.make_stage()
        original = self.make_task(stage, title="Исходная")
        rework = self.make_task(stage, title="Доработка", rework_of=original)

        self.assertEqual(list(original.rework_tasks.all()), [rework])

    def test_stage_has_no_responsible_field(self):
        field_names = {field.name for field in BacklogStage._meta.get_fields()}

        self.assertNotIn("responsible", field_names)
        self.assertNotIn("executor", field_names)
