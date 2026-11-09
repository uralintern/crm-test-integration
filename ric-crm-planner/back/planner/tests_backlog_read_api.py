"""API чтения бэклога: дерево, вычисляемые поля, фильтры, детали, коды, доступ."""

from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from planner.backlog.statuses import BacklogStatus
from planner.backlog_test_utils import OTHER_TEAM_ID, TEAM_ID, BacklogTestBase
from planner.models import BacklogComment

TASK_ROW_KEYS = {
    "id",
    "type",
    "code",
    "title",
    "description",
    "team_id",
    "stage_id",
    "responsible",
    "created_by",
    "status",
    "status_label",
    "start_date",
    "end_date",
    "planned_start_date",
    "planned_end_date",
    "start_date_is_auto",
    "end_date_is_auto",
    "sprint",
    "rework_of",
    "executors",
    "progress",
    "is_overdue",
    "position",
    "version",
    "created_at",
    "updated_at",
    "subtasks",
}
SUBTASK_ROW_KEYS = {
    "id",
    "type",
    "code",
    "title",
    "description",
    "team_id",
    "task_id",
    "executor",
    "created_by",
    "status",
    "status_label",
    "start_date",
    "end_date",
    "sprint",
    "rework_of",
    "progress",
    "is_overdue",
    "position",
    "version",
    "created_at",
    "updated_at",
}
STAGE_KEYS = {
    "id",
    "type",
    "title",
    "description",
    "team_id",
    "position",
    "start_date",
    "end_date",
    "created_by",
    "version",
    "created_at",
    "updated_at",
    "tasks",
}


def tree_url(team_id=TEAM_ID):
    return reverse("backlog-team-tree", kwargs={"team_id": team_id})


class BacklogTreeTests(BacklogTestBase):
    def setUp(self):
        super().setUp()
        self.stage1 = self.make_stage(title="Этап 1", position=0)
        self.stage2 = self.make_stage(title="Этап 2", position=1)
        self.task = self.make_task(self.stage1, title="Сделать API", responsible=self.member)
        self.sub_a = self.make_subtask(self.task, title="Модели", executor=self.member2, position=0)
        self.sub_b = self.make_subtask(self.task, title="Тесты", executor=self.member, position=1)
        self.make_work(self.sub_a, title="Поля", is_done=True)
        self.make_work(self.sub_a, title="Индексы", is_done=False)
        self.make_stage(team_id=OTHER_TEAM_ID, title="Чужой этап")

    def get_tree(self, user=None, **params):
        self.client.force_authenticate(user or self.member)
        return self.client.get(tree_url(), params)

    def test_member_gets_hierarchy_of_own_team(self):
        response = self.get_tree()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["team_id"], TEAM_ID)
        self.assertEqual(response.data["team_name"], "Команда А")
        self.assertEqual([stage["title"] for stage in response.data["stages"]], ["Этап 1", "Этап 2"])
        stage = response.data["stages"][0]
        self.assertEqual(set(stage.keys()), STAGE_KEYS)
        self.assertEqual(stage["type"], "stage")
        task = stage["tasks"][0]
        self.assertEqual(set(task.keys()), TASK_ROW_KEYS)
        self.assertEqual(task["type"], "task")
        self.assertEqual([sub["title"] for sub in task["subtasks"]], ["Модели", "Тесты"])
        self.assertEqual(set(task["subtasks"][0].keys()), SUBTASK_ROW_KEYS)
        self.assertEqual(response.data["stages"][1]["tasks"], [])

    def test_tree_tells_interface_the_user_role(self):
        member = self.get_tree(self.member).data["access"]
        curator = self.get_tree(self.curator).data["access"]

        self.assertEqual(member, {"role": "member", "is_manager": False, "user_id": self.member.id})
        self.assertEqual(curator, {"role": "curator", "is_manager": True, "user_id": self.curator.id})

    def test_work_items_are_not_rows_of_the_tree(self):
        # BL-02: работы видны только в чек-листе подзадачи.
        response = self.get_tree()

        subtask = response.data["stages"][0]["tasks"][0]["subtasks"][0]
        self.assertNotIn("work_items", subtask)
        self.assertEqual(subtask["progress"], {"done": 1, "total": 2})

    def test_row_fields_show_people_status_and_sprint(self):
        sprint = self.make_sprint()
        self.sub_a.sprint = sprint
        self.sub_a.status = BacklogStatus.IN_SPRINT
        self.sub_a.save()

        task = self.get_tree().data["stages"][0]["tasks"][0]
        subtask = task["subtasks"][0]

        self.assertEqual(task["responsible"], {"id": self.member.id, "name": "Участникова Мария"})
        self.assertEqual(task["status"], "new")
        self.assertEqual(task["status_label"], "Новая задача")
        self.assertEqual(task["code"], f"T-{self.task.id}")
        self.assertEqual(subtask["executor"], {"id": self.member2.id, "name": "Второв Павел"})
        self.assertEqual(subtask["status_label"], "В спринте")
        self.assertEqual(
            subtask["sprint"],
            {"id": sprint.id, "title": "Спринт 1", "start_date": "2026-11-02", "end_date": "2026-11-08"},
        )

    def test_task_shows_all_subtask_executors_once(self):
        self.make_subtask(self.task, title="Ещё", executor=self.member2, position=2)

        task = self.get_tree().data["stages"][0]["tasks"][0]

        self.assertEqual(
            task["executors"],
            [
                {"id": self.member2.id, "name": "Второв Павел"},
                {"id": self.member.id, "name": "Участникова Мария"},
            ],
        )

    def test_task_progress_counts_done_subtasks(self):
        self.sub_b.status = BacklogStatus.DONE
        self.sub_b.save()

        task = self.get_tree().data["stages"][0]["tasks"][0]

        self.assertEqual(task["progress"], {"done": 1, "total": 2})

    def test_empty_team_returns_empty_stage_list(self):
        self.client.force_authenticate(self.other_member)

        response = self.client.get(tree_url(OTHER_TEAM_ID))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([stage["title"] for stage in response.data["stages"]], ["Чужой этап"])

    def test_query_count_does_not_grow_with_rows(self):
        self.client.force_authenticate(self.member)
        with CaptureQueriesContext(connection) as small:
            self.client.get(tree_url())

        for index in range(5):
            task = self.make_task(self.stage2, title=f"Задача {index}", responsible=self.member2)
            subtask = self.make_subtask(task, title=f"Подзадача {index}", executor=self.member)
            self.make_work(subtask)

        with CaptureQueriesContext(connection) as large:
            self.client.get(tree_url())

        self.assertEqual(len(small.captured_queries), len(large.captured_queries))


class BacklogEffectiveDatesTests(BacklogTestBase):
    """«Карточки» §4: сроки задачи считаются по подзадачам."""

    def setUp(self):
        super().setUp()
        self.stage = self.make_stage()
        self.task = self.make_task(self.stage, start=date(2026, 11, 1), end=date(2026, 11, 20))

    def task_row(self):
        self.client.force_authenticate(self.member)
        return self.client.get(tree_url()).data["stages"][0]["tasks"][0]

    def test_without_subtasks_manual_dates_are_shown(self):
        row = self.task_row()

        self.assertEqual((row["start_date"], row["end_date"]), ("2026-11-01", "2026-11-20"))
        self.assertFalse(row["start_date_is_auto"])
        self.assertFalse(row["end_date_is_auto"])

    def test_start_is_earliest_subtask_start_and_end_stays_manual(self):
        self.make_subtask(self.task, start=date(2026, 11, 5), end=date(2026, 11, 10))
        self.make_subtask(self.task, start=date(2026, 11, 3), end=date(2026, 11, 18))

        row = self.task_row()

        self.assertEqual((row["start_date"], row["end_date"]), ("2026-11-03", "2026-11-20"))
        self.assertTrue(row["start_date_is_auto"])
        self.assertFalse(row["end_date_is_auto"])
        self.assertEqual((row["planned_start_date"], row["planned_end_date"]), ("2026-11-01", "2026-11-20"))

    def test_end_extends_to_latest_subtask_end(self):
        self.make_subtask(self.task, start=date(2026, 11, 5), end=date(2026, 11, 25))
        self.make_subtask(self.task, start=date(2026, 11, 6), end=date(2026, 11, 22))

        row = self.task_row()

        self.assertEqual(row["end_date"], "2026-11-25")
        self.assertTrue(row["end_date_is_auto"])
        self.assertEqual(row["planned_end_date"], "2026-11-20")


class BacklogOverdueTests(BacklogTestBase):
    def test_overdue_when_end_passed_and_not_done(self):
        today = date.today()
        stage = self.make_stage()
        late = self.make_task(stage, title="Просрочена", start=today - timedelta(days=5), end=today - timedelta(days=1))
        done = self.make_task(
            stage,
            title="Готова",
            start=today - timedelta(days=5),
            end=today - timedelta(days=1),
            status=BacklogStatus.DONE,
            position=1,
        )
        on_time = self.make_task(stage, title="В срок", start=today, end=today, position=2)
        self.client.force_authenticate(self.member)

        rows = {row["id"]: row for row in self.client.get(tree_url()).data["stages"][0]["tasks"]}

        self.assertTrue(rows[late.id]["is_overdue"])
        self.assertFalse(rows[done.id]["is_overdue"])
        self.assertFalse(rows[on_time.id]["is_overdue"])


class BacklogFilterTests(BacklogTestBase):
    """BL-23, BL-24, BL-25, S-02: фильтры с сохранением родителей."""

    def setUp(self):
        super().setUp()
        self.sprint = self.make_sprint()
        self.stage1 = self.make_stage(title="Аналитика", position=0)
        self.stage2 = self.make_stage(title="Разработка", position=1)
        self.task1 = self.make_task(
            self.stage1,
            title="Собрать требования",
            responsible=self.member,
            start=date(2026, 11, 1),
            end=date(2026, 11, 5),
        )
        self.task2 = self.make_task(
            self.stage2,
            title="Сделать вход",
            responsible=self.member2,
            start=date(2026, 11, 10),
            end=date(2026, 11, 30),
            sprint=self.sprint,
            status=BacklogStatus.IN_SPRINT,
        )
        self.sub1 = self.make_subtask(
            self.task2, title="Форма логина", executor=self.member, start=date(2026, 11, 10), end=date(2026, 11, 12)
        )
        self.sub2 = self.make_subtask(
            self.task2,
            title="Проверка пароля",
            executor=self.member2,
            start=date(2026, 11, 13),
            end=date(2026, 11, 20),
            status=BacklogStatus.REVIEW,
            position=1,
        )

    def filtered(self, **params):
        self.client.force_authenticate(self.member)
        response = self.client.get(tree_url(), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return {
            stage["title"]: {task["title"]: [sub["title"] for sub in task["subtasks"]] for task in stage["tasks"]}
            for stage in response.data["stages"]
        }

    def test_without_filters_everything_is_returned(self):
        self.assertEqual(
            self.filtered(),
            {
                "Аналитика": {"Собрать требования": []},
                "Разработка": {"Сделать вход": ["Форма логина", "Проверка пароля"]},
            },
        )

    def test_executor_filter_keeps_parent_task_and_stage(self):
        self.assertEqual(self.filtered(executor=self.member.id), {"Разработка": {"Сделать вход": ["Форма логина"]}})

    def test_responsible_filter_returns_task_with_its_subtasks(self):
        self.assertEqual(
            self.filtered(responsible=self.member2.id),
            {"Разработка": {"Сделать вход": ["Форма логина", "Проверка пароля"]}},
        )

    def test_status_filter_accepts_several_codes(self):
        self.assertEqual(
            self.filtered(status="review"),
            {"Разработка": {"Сделать вход": ["Проверка пароля"]}},
        )
        self.assertEqual(
            self.filtered(status="new,review"),
            {
                "Аналитика": {"Собрать требования": []},
                "Разработка": {"Сделать вход": ["Форма логина", "Проверка пароля"]},
            },
        )

    def test_sprint_filter_by_id_and_none(self):
        self.assertEqual(self.filtered(sprint=self.sprint.id), {"Разработка": {"Сделать вход": []}})
        self.assertEqual(
            self.filtered(sprint="none"),
            {
                "Аналитика": {"Собрать требования": []},
                "Разработка": {"Сделать вход": ["Форма логина", "Проверка пароля"]},
            },
        )

    def test_date_range_filter_uses_overlap(self):
        self.assertEqual(
            self.filtered(date_from="2026-11-13", date_to="2026-11-14"),
            {"Разработка": {"Сделать вход": ["Проверка пароля"]}},
        )
        self.assertEqual(self.filtered(date_to="2026-11-02"), {"Аналитика": {"Собрать требования": []}})

    def test_text_search_matches_title_description_and_code(self):
        self.task1.description = "Интервью с заказчиком"
        self.task1.save()

        self.assertEqual(self.filtered(q="ЛОГИН"), {"Разработка": {"Сделать вход": ["Форма логина"]}})
        self.assertEqual(self.filtered(q="заказчик"), {"Аналитика": {"Собрать требования": []}})
        self.assertEqual(self.filtered(q=self.sub2.code), {"Разработка": {"Сделать вход": ["Проверка пароля"]}})

    def test_text_search_matches_stage_title(self):
        self.assertEqual(self.filtered(q="аналит"), {"Аналитика": {}})

    def test_task_found_by_own_fields_hides_non_matching_subtasks(self):
        # BL-24: показываются только подходящие объекты и их родители; прогресс считается по всем подзадачам.
        self.client.force_authenticate(self.member)

        task = self.client.get(tree_url(), {"q": "вход"}).data["stages"][0]["tasks"][0]

        self.assertEqual(task["title"], "Сделать вход")
        self.assertEqual(task["subtasks"], [])
        self.assertEqual(task["progress"], {"done": 0, "total": 2})

    def test_zero_id_filter_is_applied_not_ignored(self):
        self.assertEqual(self.filtered(executor=0), {})

    def test_mixed_case_code_with_spaces_is_found(self):
        self.client.force_authenticate(self.member)
        code = f"  {self.task2.code.lower()} "

        response = self.client.get(reverse("backlog-by-code", kwargs={"code": code}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["item"]["id"], self.task2.id)

    def test_filters_are_combined(self):
        self.assertEqual(self.filtered(executor=self.member2.id, status="new"), {})

    def test_invalid_filter_values_return_400(self):
        self.client.force_authenticate(self.member)
        for params in ({"executor": "abc"}, {"status": "unknown"}, {"sprint": "x"}, {"date_from": "13.11.2026"}):
            with self.subTest(params=params):
                response = self.client.get(tree_url(), params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BacklogDetailTests(BacklogTestBase):
    def setUp(self):
        super().setUp()
        self.stage = self.make_stage(title="Этап")
        self.task = self.make_task(self.stage, title="Задача", description="Описание")
        self.subtask = self.make_subtask(self.task, title="Подзадача")
        self.work_done = self.make_work(self.subtask, title="Сделано", is_done=True, position=0)
        self.work_todo = self.make_work(self.subtask, title="Сделать", position=1, due_date=date(2026, 11, 9))
        BacklogComment.objects.create(task=self.task, author=self.member, text="Комментарий")

    def test_task_detail_has_stage_and_subtasks(self):
        self.client.force_authenticate(self.member)

        response = self.client.get(reverse("backlog-task-detail", kwargs={"task_id": self.task.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stage"], {"id": self.stage.id, "title": "Этап"})
        self.assertEqual(response.data["description"], "Описание")
        self.assertEqual([sub["title"] for sub in response.data["subtasks"]], ["Подзадача"])

    def test_subtask_detail_has_checklist_with_inherited_executor(self):
        self.client.force_authenticate(self.member)

        response = self.client.get(reverse("backlog-subtask-detail", kwargs={"subtask_id": self.subtask.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["task"],
            {
                "id": self.task.id,
                "code": self.task.code,
                "title": "Задача",
                "responsible": {"id": self.member.id, "name": "Участникова Мария"},
            },
        )
        self.assertEqual(
            response.data["work_items"],
            [
                {"id": self.work_done.id, "title": "Сделано", "is_done": True, "due_date": None, "position": 0},
                {
                    "id": self.work_todo.id,
                    "title": "Сделать",
                    "is_done": False,
                    "due_date": "2026-11-09",
                    "position": 1,
                },
            ],
        )
        # BL-16: исполнитель работ — исполнитель подзадачи.
        self.assertEqual(response.data["executor"], {"id": self.member2.id, "name": "Второв Павел"})

    def test_lookup_by_code_for_permalink(self):
        self.client.force_authenticate(self.member)

        for obj, kind in ((self.task, "task"), (self.subtask, "subtask")):
            with self.subTest(kind=kind):
                response = self.client.get(reverse("backlog-by-code", kwargs={"code": obj.code}))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["type"], kind)
                self.assertEqual(response.data["team_id"], TEAM_ID)
                self.assertEqual(response.data["item"]["id"], obj.id)

    def test_lookup_by_code_is_case_insensitive_and_404_for_unknown(self):
        self.client.force_authenticate(self.member)

        self.assertEqual(
            self.client.get(reverse("backlog-by-code", kwargs={"code": self.task.code.lower()})).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(reverse("backlog-by-code", kwargs={"code": "T-999999"})).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class BacklogReadAccessTests(BacklogTestBase):
    """BL-32: чужая команда не получает данные; ответ 404, чтобы не раскрывать существование."""

    def setUp(self):
        super().setUp()
        self.task = self.make_task(self.make_stage())
        self.subtask = self.make_subtask(self.task)
        self.urls = [
            tree_url(),
            reverse("backlog-task-detail", kwargs={"task_id": self.task.id}),
            reverse("backlog-subtask-detail", kwargs={"subtask_id": self.subtask.id}),
            reverse("backlog-by-code", kwargs={"code": self.task.code}),
        ]

    def test_anonymous_gets_401(self):
        for url in self.urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_outsiders_get_404(self):
        for user in (self.outsider, self.other_member, self.make_global_curator()):
            self.client.force_authenticate(user)
            for url in self.urls:
                with self.subTest(user=user.email, url=url):
                    self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_member_curator_organizer_and_admin_get_200(self):
        for user in (self.member, self.curator, self.leader, self.make_admin()):
            self.client.force_authenticate(user)
            for url in self.urls:
                with self.subTest(user=user.email, url=url):
                    self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_unknown_team_is_404(self):
        self.client.force_authenticate(self.make_admin())

        self.assertEqual(self.client.get(tree_url(999999)).status_code, status.HTTP_404_NOT_FOUND)
