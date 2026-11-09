"""Задача 3: статусы, спринты, завершение, доработка, канбан, комментарии, назначения."""

from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status

from planner.backlog.statuses import BacklogStatus
from planner.backlog_test_utils import OTHER_TEAM_ID, TEAM_ID, BacklogTestBase
from planner.models import BacklogComment, BacklogTask


def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


class WorkflowTestBase(BacklogTestBase):
    def setUp(self):
        super().setUp()
        self.stage = self.make_stage()
        self.task = self.make_task(self.stage, title="Задача", responsible=self.member)
        self.subtask = self.make_subtask(self.task, title="Подзадача", executor=self.member2)
        today = date.today()
        self.sprint = self.make_sprint(start=today - timedelta(days=2), end=today + timedelta(days=4))

    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def patch_task(self, data, user=None, task=None):
        return self.as_user(user or self.member).patch(
            url("backlog-task-detail", task_id=(task or self.task).id), data, format="json"
        )

    def patch_subtask(self, data, user=None):
        return self.as_user(user or self.member).patch(
            url("backlog-subtask-detail", subtask_id=self.subtask.id), data, format="json"
        )


class StatusTransitionTests(WorkflowTestBase):
    """BL-28, BL-30, S-07: только вперёд; «Завершена» — только действием «Завершить»."""

    def test_skipping_forward_is_allowed(self):
        response = self.patch_task({"status": "review"})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual((response.data["status"], response.data["status_label"]), ("review", "На проверке"))

    def test_going_back_is_forbidden(self):
        self.task.status = BacklogStatus.REVIEW
        self.task.sprint = self.sprint
        self.task.save()

        for target in ("new", "in_sprint"):
            with self.subTest(target=target):
                response = self.patch_task({"status": target})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("status", response.data)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, BacklogStatus.REVIEW)

    def test_done_only_through_complete_action(self):
        response = self.patch_task({"status": "done"}, user=self.curator)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_in_sprint_requires_a_sprint(self):
        response = self.patch_task({"status": "in_sprint"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_status_is_rejected(self):
        self.assertEqual(self.patch_task({"status": "in_progress"}).status_code, status.HTTP_400_BAD_REQUEST)

    def test_subtask_follows_the_same_rules(self):
        forward = self.patch_subtask({"status": "review"})
        back = self.patch_subtask({"status": "new"})

        self.assertEqual(forward.status_code, status.HTTP_200_OK, forward.data)
        self.assertEqual(back.status_code, status.HTTP_400_BAD_REQUEST)


class SprintTests(WorkflowTestBase):
    """M-07, BL-26: спринты команды; добавление в спринт меняет статус на «В спринте»."""

    def test_member_creates_and_lists_sprints(self):
        created = self.as_user(self.member).post(
            url("backlog-sprints", team_id=TEAM_ID),
            {"title": "Спринт 2", "start_date": "2026-12-01", "end_date": "2026-12-03"},
            format="json",
        )
        listed = self.as_user(self.member).get(url("backlog-sprints", team_id=TEAM_ID))

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertIsInstance(listed.data, list)
        self.assertEqual([sprint["title"] for sprint in listed.data], ["Спринт 1", "Спринт 2"])
        self.assertEqual([sprint["is_current"] for sprint in listed.data], [True, False])

    def test_sprint_dates_are_validated(self):
        response = self.as_user(self.member).post(
            url("backlog-sprints", team_id=TEAM_ID),
            {"title": "Плохой", "start_date": "2026-12-05", "end_date": "2026-12-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adding_to_sprint_moves_new_task_to_in_sprint(self):
        response = self.patch_task({"sprint_id": self.sprint.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "in_sprint")
        self.assertEqual(response.data["sprint"]["id"], self.sprint.id)

    def test_subtask_can_be_planned_into_sprint_separately(self):
        response = self.patch_subtask({"sprint_id": self.sprint.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "in_sprint")

    def test_sprint_of_another_team_is_rejected(self):
        foreign = self.make_sprint(team_id=OTHER_TEAM_ID, title="Чужой")

        response = self.patch_task({"sprint_id": foreign.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sprint_id", response.data)

    def test_removing_from_sprint_is_not_available_yet(self):
        self.patch_task({"sprint_id": self.sprint.id})

        response = self.patch_task({"sprint_id": None})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.task.refresh_from_db()
        self.assertEqual(self.task.sprint_id, self.sprint.id)

    def test_sprint_with_active_tasks_cannot_be_deleted(self):
        self.patch_task({"sprint_id": self.sprint.id})

        response = self.as_user(self.curator).delete(url("backlog-sprint-detail", sprint_id=self.sprint.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_update_and_delete_sprint(self):
        sprint = self.make_sprint(title="Пустой", start=date(2027, 1, 1), end=date(2027, 1, 7))

        updated = self.as_user(self.curator).patch(
            url("backlog-sprint-detail", sprint_id=sprint.id), {"title": "Январь"}, format="json"
        )
        deleted = self.as_user(self.curator).delete(url("backlog-sprint-detail", sprint_id=sprint.id))

        self.assertEqual(updated.status_code, status.HTTP_200_OK, updated.data)
        self.assertEqual(updated.data["title"], "Январь")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_outsider_gets_404(self):
        self.assertEqual(
            self.as_user(self.outsider).get(url("backlog-sprints", team_id=TEAM_ID)).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class CompleteTests(WorkflowTestBase):
    """BL-29, S-07, «Карточки» §6: задачу завершает куратор, подзадачу — ответственный задачи."""

    def complete_task(self, user):
        return self.as_user(user).post(url("backlog-task-complete", task_id=self.task.id))

    def complete_subtask(self, user):
        return self.as_user(user).post(url("backlog-subtask-complete", subtask_id=self.subtask.id))

    def test_curator_completes_task(self):
        response = self.complete_task(self.curator)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual((response.data["status"], response.data["status_label"]), ("done", "Завершена"))

    def test_organizer_and_admin_complete_task(self):
        other_task = self.make_task(self.stage, title="Другая", position=1)

        self.assertEqual(self.complete_task(self.leader).status_code, status.HTTP_200_OK)
        response = self.as_user(self.make_admin()).post(url("backlog-task-complete", task_id=other_task.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_cannot_complete_task(self):
        response = self.complete_task(self.member)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, BacklogStatus.NEW)

    def test_repeated_completion_is_rejected(self):
        self.complete_task(self.curator)

        response = self.complete_task(self.curator)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_subtask_completed_by_task_responsible_or_curator(self):
        self.assertEqual(self.complete_subtask(self.member2).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.complete_subtask(self.member).status_code, status.HTTP_200_OK)
        self.assertEqual(self.complete_subtask(self.member).status_code, status.HTTP_409_CONFLICT)

        other = self.make_subtask(self.task, title="Ещё", position=1)
        response = self.as_user(self.curator).post(url("backlog-subtask-complete", subtask_id=other.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_completed_task_progress_counts_done_subtasks(self):
        self.complete_subtask(self.member)

        task = self.as_user(self.member).get(url("backlog-task-detail", task_id=self.task.id)).data

        self.assertEqual(task["progress"], {"done": 1, "total": 1})


class ReworkTests(WorkflowTestBase):
    """«Карточки» §6, «Канбан» §2: доработка — новая задача, статус исходной не меняется."""

    def rework_payload(self, **extra):
        payload = {
            "title": "Доработать отчёт",
            "comment": "Не хватает выводов",
            "responsible_id": self.member2.id,
            "start_date": "2026-11-21",
            "end_date": "2026-11-25",
        }
        payload.update(extra)
        return payload

    def test_rework_only_from_review(self):
        response = self.as_user(self.member).post(
            url("backlog-task-rework", task_id=self.task.id), self.rework_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_creates_rework_task_linked_to_original(self):
        self.task.status = BacklogStatus.REVIEW
        self.task.save()

        response = self.as_user(self.member).post(
            url("backlog-task-rework", task_id=self.task.id), self.rework_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["rework_of"], {"id": self.task.id, "code": self.task.code})
        self.assertEqual(response.data["status"], "new")
        self.assertEqual(response.data["stage"]["id"], self.stage.id)
        rework = BacklogTask.objects.get(pk=response.data["id"])
        self.assertEqual(
            list(BacklogComment.objects.filter(task=rework).values_list("text", "author_id")),
            [("Не хватает выводов", self.member.id)],
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, BacklogStatus.REVIEW)

    def test_rework_requires_comment(self):
        self.task.status = BacklogStatus.REVIEW
        self.task.save()

        response = self.as_user(self.member).post(
            url("backlog-task-rework", task_id=self.task.id), self.rework_payload(comment=" "), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comment", response.data)

    def test_subtask_rework(self):
        self.subtask.status = BacklogStatus.REVIEW
        self.subtask.save()

        response = self.as_user(self.member2).post(
            url("backlog-subtask-rework", subtask_id=self.subtask.id),
            {
                "title": "Поправить",
                "comment": "Ошибка в расчёте",
                "executor_id": self.member2.id,
                "start_date": "2026-11-11",
                "end_date": "2026-11-12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["rework_of"]["id"], self.subtask.id)
        self.assertEqual(response.data["task"]["id"], self.task.id)


class KanbanTests(WorkflowTestBase):
    """M-06, BL-28: на канбане задачи спринта «В спринте» и «На проверке»; завершённые исчезают."""

    def setUp(self):
        super().setUp()
        self.patch_task({"sprint_id": self.sprint.id})
        self.review_task = self.make_task(self.stage, title="На проверке", position=1)
        self.patch_task({"sprint_id": self.sprint.id, "status": "review"}, task=self.review_task)
        self.done_task = self.make_task(self.stage, title="Готовая", position=2)
        self.patch_task({"sprint_id": self.sprint.id}, task=self.done_task)
        self.as_user(self.curator).post(url("backlog-task-complete", task_id=self.done_task.id))
        self.patch_subtask({"sprint_id": self.sprint.id})
        self.make_task(self.stage, title="Вне спринта", position=3)

    def board(self, **params):
        response = self.as_user(self.member).get(url("backlog-kanban", team_id=TEAM_ID), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_current_sprint_board(self):
        data = self.board()

        self.assertEqual(data["sprint"]["id"], self.sprint.id)
        self.assertEqual([column["status"] for column in data["columns"]], ["in_sprint", "review"])
        self.assertEqual([column["label"] for column in data["columns"]], ["В спринте", "На проверке"])
        in_sprint = [(item["type"], item["title"]) for item in data["columns"][0]["items"]]
        self.assertEqual(in_sprint, [("task", "Задача"), ("subtask", "Подзадача")])
        self.assertEqual([item["title"] for item in data["columns"][1]["items"]], ["На проверке"])

    def test_explicit_sprint_and_empty_board(self):
        future = self.make_sprint(title="Будущий", start=date(2030, 1, 1), end=date(2030, 1, 7))

        data = self.board(sprint=future.id)

        self.assertEqual(data["sprint"]["id"], future.id)
        self.assertEqual([column["items"] for column in data["columns"]], [[], []])

    def test_no_current_sprint(self):
        self.sprint.start_date = date(2020, 1, 1)
        self.sprint.end_date = date(2020, 1, 2)
        self.sprint.save()

        data = self.board()

        self.assertIsNone(data["sprint"])
        self.assertEqual([column["items"] for column in data["columns"]], [[], []])

    def test_foreign_sprint_id_returns_404(self):
        foreign = self.make_sprint(team_id=OTHER_TEAM_ID, title="Чужой")

        response = self.as_user(self.member).get(url("backlog-kanban", team_id=TEAM_ID), {"sprint": foreign.id})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CommentTests(WorkflowTestBase):
    def test_add_and_list_task_comments(self):
        created = self.as_user(self.member).post(
            url("backlog-task-comments", task_id=self.task.id), {"text": "  Готово к проверке "}, format="json"
        )
        listed = self.as_user(self.curator).get(url("backlog-task-comments", task_id=self.task.id))

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(set(created.data), {"id", "author", "text", "created_at"})
        self.assertEqual(created.data["text"], "Готово к проверке")
        self.assertEqual(created.data["author"], {"id": self.member.id, "name": "Участникова Мария"})
        self.assertEqual([comment["text"] for comment in listed.data], ["Готово к проверке"])

    def test_subtask_comments_and_validation(self):
        blank = self.as_user(self.member).post(
            url("backlog-subtask-comments", subtask_id=self.subtask.id), {"text": " "}, format="json"
        )
        ok = self.as_user(self.member).post(
            url("backlog-subtask-comments", subtask_id=self.subtask.id), {"text": "Вопрос"}, format="json"
        )

        self.assertEqual(blank.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_outsider_gets_404(self):
        response = self.as_user(self.outsider).get(url("backlog-task-comments", task_id=self.task.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AssignmentTests(WorkflowTestBase):
    """M-03, BL-14, BL-15: один ответственный/исполнитель из участников команды."""

    def test_reassign_to_member_and_reject_outsider(self):
        ok = self.patch_task({"responsible_id": self.member2.id})
        bad = self.patch_task({"responsible_id": self.outsider.id})
        bad_sub = self.patch_subtask({"executor_id": self.other_member.id})

        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_sub.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_of_responsibles_is_not_accepted(self):
        response = self.patch_task({"responsible_id": [self.member.id, self.member2.id]})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_responsible_cannot_be_cleared(self):
        response = self.patch_task({"responsible_id": None})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReviewFollowUpTests(WorkflowTestBase):
    """Случаи, отмеченные на ревью: версии, спринты, права, ограничения размеров."""

    def test_stale_version_on_task_and_subtask_returns_409(self):
        self.patch_task({"title": "Первая правка"})
        self.patch_subtask({"title": "Первая правка"})

        task = self.patch_task({"title": "Вторая", "version": 1})
        subtask = self.patch_subtask({"title": "Вторая", "version": 1})

        self.assertEqual((task.status_code, task.data["current_version"]), (409, 2))
        self.assertEqual((subtask.status_code, subtask.data["current_version"]), (409, 2))

    def test_explicit_new_status_with_sprint_becomes_in_sprint(self):
        response = self.patch_task({"status": "new", "sprint_id": self.sprint.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "in_sprint")

    def test_member_cannot_delete_sprint_created_by_someone_else(self):
        sprint = self.make_sprint(title="Чужой", start=date(2027, 2, 1), end=date(2027, 2, 7))
        sprint.created_by = self.member
        sprint.save()

        response = self.as_user(self.member2).delete(url("backlog-sprint-detail", sprint_id=sprint.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sprint_with_only_done_tasks_is_kept_for_history(self):
        self.patch_task({"sprint_id": self.sprint.id})
        self.as_user(self.curator).post(url("backlog-task-complete", task_id=self.task.id))

        response = self.as_user(self.curator).delete(url("backlog-sprint-detail", sprint_id=self.sprint.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.task.refresh_from_db()
        self.assertEqual(self.task.sprint_id, self.sprint.id)

    def test_subtask_rework_only_from_review(self):
        response = self.as_user(self.member).post(
            url("backlog-subtask-rework", subtask_id=self.subtask.id),
            {
                "title": "Поправить",
                "comment": "Причина",
                "executor_id": self.member2.id,
                "start_date": "2026-11-11",
                "end_date": "2026-11-12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outsider_cannot_write_comments(self):
        response = self.as_user(self.outsider).post(
            url("backlog-task-comments", task_id=self.task.id), {"text": "Привет"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(BacklogComment.objects.exists())

    def test_bulk_create_checks_executor_and_size_limit(self):
        base = {"executor_id": self.member.id, "start_date": "2026-11-02", "end_date": "2026-11-06"}
        outsider = self.as_user(self.member).post(
            url("backlog-subtask-bulk", task_id=self.task.id),
            {**base, "titles": ["A"], "executor_id": self.outsider.id},
            format="json",
        )
        too_many = self.as_user(self.member).post(
            url("backlog-subtask-bulk", task_id=self.task.id),
            {**base, "titles": [f"Пункт {index}" for index in range(101)]},
            format="json",
        )

        self.assertEqual(outsider.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_long_description_and_comment_are_rejected(self):
        description = self.patch_task({"description": "x" * 10_001})
        comment = self.as_user(self.member).post(
            url("backlog-task-comments", task_id=self.task.id), {"text": "x" * 5_001}, format="json"
        )

        self.assertEqual(description.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(comment.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_reorder_rejects_task_of_another_stage(self):
        other_stage = self.make_stage(title="Другой", position=1)
        foreign_task = self.make_task(other_stage, title="Чужая")

        response = self.as_user(self.member).post(
            url("backlog-task-reorder", stage_id=self.stage.id), {"ids": [foreign_task.id]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
