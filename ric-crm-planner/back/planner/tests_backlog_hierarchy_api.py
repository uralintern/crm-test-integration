"""Задача 2: иерархия бэклога и чек-листы — создание, изменение, порядок, удаление."""

from datetime import date

from django.urls import reverse
from rest_framework import status

from planner.backlog.statuses import BacklogStatus
from planner.backlog_test_utils import OTHER_TEAM_ID, TEAM_ID, BacklogTestBase
from planner.models import BacklogStage, BacklogSubtask, BacklogTask, BacklogWorkItem


def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


class BacklogWriteTestBase(BacklogTestBase):
    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def task_payload(self, **extra):
        payload = {
            "title": "Задача",
            "responsible_id": self.member.id,
            "start_date": "2026-11-01",
            "end_date": "2026-11-20",
        }
        payload.update(extra)
        return payload

    def subtask_payload(self, **extra):
        payload = {
            "title": "Подзадача",
            "executor_id": self.member2.id,
            "start_date": "2026-11-03",
            "end_date": "2026-11-10",
        }
        payload.update(extra)
        return payload


class StageWriteTests(BacklogWriteTestBase):
    def test_member_creates_stage_at_the_end(self):
        self.make_stage(title="Первый", position=0)

        response = self.as_user(self.member).post(
            url("backlog-stage-create", team_id=TEAM_ID), {"title": "  Второй  "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["title"], "Второй")
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(response.data["created_by"]["id"], self.member.id)
        self.assertEqual(response.data["tasks"], [])
        self.assertEqual(BacklogStage.objects.get(pk=response.data["id"]).team_id, TEAM_ID)

    def test_title_is_required(self):
        # BL-13: пустое название блокирует сохранение.
        for payload in ({}, {"title": ""}, {"title": "   "}):
            with self.subTest(payload=payload):
                response = self.as_user(self.member).post(
                    url("backlog-stage-create", team_id=TEAM_ID), payload, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("title", response.data)

    def test_stage_end_before_start_is_rejected(self):
        response = self.as_user(self.member).post(
            url("backlog-stage-create", team_id=TEAM_ID),
            {"title": "Этап", "start_date": "2026-11-10", "end_date": "2026-11-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data)

    def test_outsider_and_foreign_team_get_404_anonymous_401(self):
        create_url = url("backlog-stage-create", team_id=TEAM_ID)
        self.assertEqual(self.client.post(create_url, {"title": "x"}, format="json").status_code, 401)
        for user in (self.outsider, self.other_member):
            with self.subTest(user=user.email):
                response = self.as_user(user).post(create_url, {"title": "x"}, format="json")
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(BacklogStage.objects.exists())

    def test_update_stage_bumps_version(self):
        stage = self.make_stage(title="Старое")

        response = self.as_user(self.member).patch(
            url("backlog-stage-detail", stage_id=stage.id), {"title": "Новое", "version": 1}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["title"], "Новое")
        self.assertEqual(response.data["version"], 2)

    def test_stale_version_returns_409_and_keeps_data(self):
        stage = self.make_stage(title="Старое")
        self.as_user(self.member).patch(url("backlog-stage-detail", stage_id=stage.id), {"title": "Первая правка"})

        response = self.as_user(self.member2).patch(
            url("backlog-stage-detail", stage_id=stage.id), {"title": "Вторая правка", "version": 1}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["current_version"], 2)
        stage.refresh_from_db()
        self.assertEqual(stage.title, "Первая правка")

    def test_reorder_stages(self):
        first = self.make_stage(title="A", position=0)
        second = self.make_stage(title="B", position=1)

        response = self.as_user(self.member).post(
            url("backlog-stage-reorder", team_id=TEAM_ID), {"ids": [second.id, first.id]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([stage["id"] for stage in response.data], [second.id, first.id])

    def test_reorder_requires_exactly_all_stages(self):
        first = self.make_stage(title="A", position=0)
        self.make_stage(title="B", position=1)

        response = self.as_user(self.member).post(
            url("backlog-stage-reorder", team_id=TEAM_ID), {"ids": [first.id]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DeleteTests(BacklogWriteTestBase):
    """BL-22: удаление с подтверждением и последствиями; права — п. 4 решений."""

    def setUp(self):
        super().setUp()
        self.stage = self.make_stage(created_by=self.member)
        self.task = self.make_task(self.stage, created_by=self.member)
        self.subtask = self.make_subtask(self.task, created_by=self.member)
        self.make_work(self.subtask)
        self.make_work(self.subtask)

    def test_delete_with_children_requires_confirmation(self):
        response = self.as_user(self.member).delete(url("backlog-stage-detail", stage_id=self.stage.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["children"], {"tasks": 1, "subtasks": 1, "work_items": 2})
        self.assertTrue(BacklogStage.objects.filter(pk=self.stage.id).exists())

    def test_confirmed_delete_removes_branch(self):
        response = self.as_user(self.member).delete(
            url("backlog-stage-detail", stage_id=self.stage.id) + "?confirm=true"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BacklogTask.objects.exists())
        self.assertFalse(BacklogWorkItem.objects.exists())

    def test_object_without_children_is_deleted_without_confirmation(self):
        stage = self.make_stage(title="Пустой", created_by=self.member, position=5)

        response = self.as_user(self.member).delete(url("backlog-stage-detail", stage_id=stage.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_member_cannot_delete_objects_created_by_others(self):
        for name, kwargs in (
            ("backlog-stage-detail", {"stage_id": self.stage.id}),
            ("backlog-task-detail", {"task_id": self.task.id}),
            ("backlog-subtask-detail", {"subtask_id": self.subtask.id}),
        ):
            with self.subTest(name=name):
                response = self.as_user(self.member2).delete(url(name, **kwargs) + "?confirm=true")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(BacklogSubtask.objects.filter(pk=self.subtask.id).exists())

    def test_curator_and_organizer_delete_anything_in_their_team(self):
        task_response = self.as_user(self.curator).delete(
            url("backlog-task-detail", task_id=self.task.id) + "?confirm=true"
        )
        stage_response = self.as_user(self.leader).delete(url("backlog-stage-detail", stage_id=self.stage.id))

        self.assertEqual(task_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(stage_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_work_item_delete_follows_same_rules(self):
        own = self.make_work(self.subtask, title="Моя", created_by=self.member2, position=5)
        foreign = self.make_work(self.subtask, title="Чужая", created_by=self.member, position=6)

        own_response = self.as_user(self.member2).delete(url("backlog-work-detail", work_id=own.id))
        foreign_response = self.as_user(self.member2).delete(url("backlog-work-detail", work_id=foreign.id))

        self.assertEqual(own_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(foreign_response.status_code, status.HTTP_403_FORBIDDEN)


class TaskWriteTests(BacklogWriteTestBase):
    def setUp(self):
        super().setUp()
        self.stage = self.make_stage()

    def create(self, user=None, stage=None, **payload):
        return self.as_user(user or self.member).post(
            url("backlog-task-create", stage_id=(stage or self.stage).id), self.task_payload(**payload), format="json"
        )

    def test_create_task_inside_stage(self):
        # BL-09: задача связана с этапом из контекста создания.
        response = self.create(description="Описание")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        task = BacklogTask.objects.get(pk=response.data["id"])
        self.assertEqual(task.stage_id, self.stage.id)
        self.assertEqual(task.team_id, TEAM_ID)
        self.assertEqual(task.created_by_id, self.member.id)
        self.assertEqual(response.data["status"], BacklogStatus.NEW)
        self.assertEqual(response.data["code"], f"T-{task.id}")
        self.assertEqual(response.data["stage"], {"id": self.stage.id, "title": self.stage.title})

    def test_required_fields(self):
        # BL-19: название, даты и ответственный обязательны.
        for field in ("title", "responsible_id", "start_date", "end_date"):
            with self.subTest(field=field):
                payload = self.task_payload()
                payload.pop(field)
                response = self.as_user(self.member).post(
                    url("backlog-task-create", stage_id=self.stage.id), payload, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_responsible_must_be_team_member(self):
        for user_id in (self.outsider.id, self.curator.id, 999999):
            with self.subTest(user_id=user_id):
                response = self.create(responsible_id=user_id)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("responsible_id", response.data)

    def test_end_before_start_is_rejected(self):
        response = self.create(start_date="2026-11-20", end_date="2026-11-01")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data)

    def test_parent_is_taken_from_url_not_from_body(self):
        # BR-05, W-01: родитель задаётся контекстом создания и не меняется через API.
        other_stage = self.make_stage(title="Другой", position=1)

        response = self.create(stage_id=other_stage.id, team_id=OTHER_TEAM_ID)

        task = BacklogTask.objects.get(pk=response.data["id"])
        self.assertEqual((task.stage_id, task.team_id), (self.stage.id, TEAM_ID))
        patch = self.as_user(self.member).patch(
            url("backlog-task-detail", task_id=task.id), {"stage_id": other_stage.id}, format="json"
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.stage_id, self.stage.id)

    def test_cannot_create_in_foreign_stage(self):
        foreign_stage = self.make_stage(team_id=OTHER_TEAM_ID, title="Чужой")

        response = self.create(stage=foreign_stage)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_fields_and_dates_are_checked_against_current_values(self):
        task = self.make_task(self.stage, start=date(2026, 11, 1), end=date(2026, 11, 20))

        ok = self.as_user(self.member).patch(
            url("backlog-task-detail", task_id=task.id),
            {"title": "Новое", "description": "Текст", "end_date": "2026-11-25", "responsible_id": self.member2.id},
            format="json",
        )
        bad = self.as_user(self.member).patch(
            url("backlog-task-detail", task_id=task.id), {"start_date": "2026-12-01"}, format="json"
        )

        self.assertEqual(ok.status_code, status.HTTP_200_OK, ok.data)
        self.assertEqual(ok.data["title"], "Новое")
        self.assertEqual(ok.data["planned_end_date"], "2026-11-25")
        self.assertEqual(ok.data["responsible"]["id"], self.member2.id)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", bad.data)

    def test_blank_title_on_update_is_rejected(self):
        task = self.make_task(self.stage)

        response = self.as_user(self.member).patch(
            url("backlog-task-detail", task_id=task.id), {"title": "  "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_tasks_go_to_the_end_and_can_be_reordered(self):
        first = self.create(title="A").data["id"]
        second = self.create(title="B").data["id"]

        response = self.as_user(self.member).post(
            url("backlog-task-reorder", stage_id=self.stage.id), {"ids": [second, first]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([task["id"] for task in response.data], [second, first])


class SubtaskWriteTests(BacklogWriteTestBase):
    def setUp(self):
        super().setUp()
        self.stage = self.make_stage()
        self.task = self.make_task(self.stage, start=date(2026, 11, 1), end=date(2026, 11, 20))

    def test_create_subtask_inside_task_updates_task_dates(self):
        response = self.as_user(self.member).post(
            url("backlog-subtask-create", task_id=self.task.id),
            self.subtask_payload(start_date="2026-11-05", end_date="2026-11-28"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["task"]["id"], self.task.id)
        self.assertEqual(response.data["code"], f"S-{response.data['id']}")
        self.assertEqual(response.data["work_items"], [])
        task = self.as_user(self.member).get(url("backlog-task-detail", task_id=self.task.id)).data
        self.assertEqual((task["start_date"], task["end_date"]), ("2026-11-05", "2026-11-28"))
        self.assertTrue(task["end_date_is_auto"])

    def test_executor_required_and_must_be_member(self):
        payload = self.subtask_payload()
        payload.pop("executor_id")
        missing = self.as_user(self.member).post(url("backlog-subtask-create", task_id=self.task.id), payload)
        outsider = self.as_user(self.member).post(
            url("backlog-subtask-create", task_id=self.task.id),
            self.subtask_payload(executor_id=self.outsider.id),
            format="json",
        )

        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(outsider.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("executor_id", outsider.data)

    def test_bulk_create_from_checklist_lines(self):
        # «Карточки» §5: пункты чек-листа задачи превращаются в подзадачи.
        response = self.as_user(self.member).post(
            url("backlog-subtask-bulk", task_id=self.task.id),
            {
                "titles": ["Макет", "  ", "Вёрстка"],
                "executor_id": self.member.id,
                "start_date": "2026-11-02",
                "end_date": "2026-11-06",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual([sub["title"] for sub in response.data], ["Макет", "Вёрстка"])
        self.assertFalse(BacklogSubtask.objects.filter(code__isnull=True).exists())

    def test_bulk_create_needs_at_least_one_title(self):
        response = self.as_user(self.member).post(
            url("backlog-subtask-bulk", task_id=self.task.id),
            {"titles": ["", " "], "executor_id": self.member.id, "start_date": "2026-11-02", "end_date": "2026-11-06"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_subtask(self):
        subtask = self.make_subtask(self.task)

        response = self.as_user(self.member).patch(
            url("backlog-subtask-detail", subtask_id=subtask.id),
            {"title": "Переименована", "executor_id": self.member.id, "description": "Детали"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["title"], "Переименована")
        self.assertEqual(response.data["executor"]["id"], self.member.id)
        self.assertEqual(response.data["version"], 2)


class WorkItemTests(BacklogWriteTestBase):
    """BL-12, BL-16, BL-21: чек-лист работ подзадачи."""

    def setUp(self):
        super().setUp()
        self.subtask = self.make_subtask(self.make_task(self.make_stage()))

    def test_add_toggle_rename_and_due_date_is_optional(self):
        created = self.as_user(self.member).post(
            url("backlog-work-create", subtask_id=self.subtask.id), {"title": "Нарисовать"}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(
            created.data,
            {"id": created.data["id"], "title": "Нарисовать", "is_done": False, "due_date": None, "position": 0},
        )

        updated = self.as_user(self.member2).patch(
            url("backlog-work-detail", work_id=created.data["id"]),
            {"is_done": True, "title": "Нарисовать макет", "due_date": "2026-11-09"},
            format="json",
        )

        self.assertEqual(updated.status_code, status.HTTP_200_OK, updated.data)
        self.assertEqual((updated.data["is_done"], updated.data["title"]), (True, "Нарисовать макет"))
        detail = self.as_user(self.member).get(url("backlog-subtask-detail", subtask_id=self.subtask.id)).data
        self.assertEqual(detail["progress"], {"done": 1, "total": 1})

    def test_work_title_required(self):
        response = self.as_user(self.member).post(
            url("backlog-work-create", subtask_id=self.subtask.id), {"title": " "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_work_has_no_executor_of_its_own(self):
        response = self.as_user(self.member).post(
            url("backlog-work-create", subtask_id=self.subtask.id),
            {"title": "Работа", "executor_id": self.member.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("executor", response.data)

    def test_outsider_cannot_touch_checklist(self):
        work = self.make_work(self.subtask)
        self.as_user(self.outsider)

        self.assertEqual(
            self.client.post(url("backlog-work-create", subtask_id=self.subtask.id), {"title": "x"}).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(url("backlog-work-detail", work_id=work.id), {"is_done": True}).status_code,
            status.HTTP_404_NOT_FOUND,
        )
