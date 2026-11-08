"""Характеризационные тесты движка автоматизации планировщика (planner.automation_engine).

Фиксируют текущее поведение перед реорганизацией кода. VK по-настоящему не вызывается:
в api.settings_test интеграция выключена, а для успешной отправки подменяется
urllib.request.urlopen в integrations.vk.services.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from integrations.vk.services import VKConfigurationError
from planner.automation_engine import (
    PlannerAutomationEvent,
    SPRINT_SWEEP_ROBOT_ID,
    apply_sprint_added_fallback,
    compare_values,
    condition_value,
    conditions_match,
    config_model_to_dict,
    create_notification,
    deadline_changed,
    detect_planner_events,
    detect_planner_scan_events,
    event_context,
    execute_pending_log,
    find_sprint_sweep_robot,
    get_or_create_config,
    has_task_data_changed,
    is_active_task,
    is_done_status,
    is_in_sprint,
    is_review_status,
    is_started_status,
    item_assignee_id,
    item_end_date,
    item_recipient_id,
    item_team_id,
    item_updated_at,
    list_by_id,
    render_template,
    run_config_for_event,
    run_due_planner_automation,
    run_planner_automation,
    run_robot_action,
    run_trigger,
    scan_planner_deadlines,
    send_vk_notification,
    set_in_sprint,
    should_delay,
    sprint_week_key,
    sprint_week_timezone,
    sweep_done_subtasks_from_sprint,
    target_status_for_stage,
    task_stage_id,
    team_by_id,
    team_curator_id,
    team_event_id,
    to_int,
    update_item_status,
    workspace_state_dict,
)
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, PlannerWorkspaceState
from users.models import Notification, Profile


EVENT_ID = 501
TEAM_ID = 17
IMMEDIATE = {"runMode": "queue", "timing": "immediate", "delayMinutes": 0, "condition": {"mode": "all", "rules": []}}
DELAYED = {"runMode": "queue", "timing": "delayed", "delayMinutes": 10, "condition": {"mode": "all", "rules": []}}

VK_TEST_SETTINGS = {
    "VK_ENABLED": True,
    "VK_ACCESS_TOKEN": "test-token",
    "VK_API_VERSION": "5.199",
    "VK_API_BASE_URL": "https://vk.example.test/method",
    "VK_REQUEST_TIMEOUT_SECONDS": 1,
}


def make_robot(robot_id, action, *, stage_id="planned", settings=None, **extra):
    robot = {
        "id": robot_id,
        "stageId": stage_id,
        "title": f"Робот {robot_id}",
        "description": "",
        "action": action,
        "enabled": True,
        "settings": settings or dict(IMMEDIATE),
        "subject": "Задача {task}",
        "message": "Команда {teamName}: {task}",
    }
    robot.update(extra)
    return robot


def make_trigger(trigger_id, event_code, *, target_stage_id, settings=None, **extra):
    trigger = {
        "id": trigger_id,
        "stageId": target_stage_id,
        "title": f"Триггер {trigger_id}",
        "description": "",
        "eventCode": event_code,
        "enabled": True,
        "settings": settings or dict(IMMEDIATE),
        "targetStageId": target_stage_id,
        "allowBackTransition": False,
    }
    trigger.update(extra)
    return trigger


class PlannerAutomationPureFunctionTests(SimpleTestCase):
    def test_to_int(self):
        for raw, expected in [(None, None), ("", None), ("4", 4), ("x", None), ({}, None)]:
            with self.subTest(raw=raw):
                self.assertEqual(to_int(raw), expected)

    def test_item_accessors_accept_camel_and_snake_case(self):
        self.assertEqual(item_team_id({"teamId": "3"}), 3)
        self.assertEqual(item_team_id({"team_id": 4}), 4)
        self.assertEqual(item_assignee_id({"assignee_id": "8"}), 8)
        self.assertEqual(item_recipient_id({"memberId": 9}), 9)
        self.assertEqual(item_recipient_id({"assigneeId": 5, "memberId": 9}), 5)
        self.assertEqual(item_end_date({"end_date": "2026-01-02"}).isoformat(), "2026-01-02")
        self.assertIsNone(item_end_date({"endDate": "not-a-date"}))

    def test_item_updated_at_parses_and_makes_aware(self):
        self.assertIsNone(item_updated_at({}))
        self.assertIsNone(item_updated_at({"updatedAt": "garbage"}))
        aware = item_updated_at({"updated_at": "2026-01-02T10:00:00+00:00"})
        self.assertEqual(aware, datetime(2026, 1, 2, 10, 0, tzinfo=dt_timezone.utc))
        naive = item_updated_at({"updatedAt": "2026-01-02T10:00:00"})
        self.assertTrue(timezone.is_aware(naive))

    def test_status_predicates_are_case_insensitive(self):
        self.assertTrue(is_done_status(" ГОТОВО "))
        self.assertTrue(is_done_status("done"))
        self.assertTrue(is_review_status("На проверке"))
        self.assertTrue(is_started_status("in-progress"))
        self.assertFalse(is_started_status("Готово"))
        self.assertFalse(is_active_task({"status": "Завершено"}))
        self.assertTrue(is_active_task({"status": "В работе"}))

    def test_sprint_flag_helpers_keep_snake_case_key_in_sync(self):
        item = {"in_sprint": True}
        self.assertTrue(is_in_sprint(item))

        set_in_sprint(item, False)

        self.assertEqual(item, {"in_sprint": False, "inSprint": False})
        camel_only = {}
        set_in_sprint(camel_only, True)
        self.assertEqual(camel_only, {"inSprint": True})

    def test_list_and_team_indexes(self):
        self.assertEqual(list_by_id("not-a-list"), {})
        self.assertEqual(set(list_by_id([{"id": 1}, {"id": ""}, "x", {"id": "b"}])), {"1", "b"})
        self.assertEqual(team_by_id(None), {})
        self.assertEqual(set(team_by_id([{"id": "5"}, {"id": None}, "x"])), {5})
        self.assertEqual(team_event_id({"event_id": "7"}), 7)
        self.assertIsNone(team_event_id(None))
        self.assertEqual(team_curator_id({"curator_id": 3}), 3)
        self.assertIsNone(team_curator_id("not-a-team"))

    def test_task_stage_id_mapping(self):
        cases = [
            ({"type": "parent", "status": "Готово"}, "backlog"),
            ({"status": "Риск по сроку"}, "risk"),
            ({"status": "Готово"}, "done"),
            ({"status": "На проверке"}, "review"),
            ({"status": "В работе"}, "in-progress"),
            ({"status": "Бэклог", "in_sprint": True}, "planned"),
            ({"status": "Бэклог"}, "backlog"),
        ]
        for item, expected in cases:
            with self.subTest(item=item):
                self.assertEqual(task_stage_id(item), expected)

    def test_target_status_for_stage_uses_config_then_fallback(self):
        config = {"stages": [{"id": "review", "title": "Своя проверка"}, "not-a-dict"]}
        cases = {
            "review": "Своя проверка",
            "planned": "Запланировано",
            "in-progress": "В работе",
            "done": "Готово",
            "risk": "Риск по сроку",
            "unknown": "Запланировано",
        }
        for stage_id, expected in cases.items():
            with self.subTest(stage_id=stage_id):
                self.assertEqual(target_status_for_stage(config, stage_id), expected)

    def test_compare_values_and_condition_value(self):
        cases = [
            ("a", "equals", "A", None, True),
            ("a", "not_equals", "b", None, True),
            ("abc", "contains", "B", None, True),
            ("abc", "not_contains", "z", None, True),
            ("x", "filled", "", None, True),
            ("", "empty", "", None, True),
            ("5", "greater_or_equal", "5", None, True),
            ("6", "less_or_equal", "5", None, False),
            ("5", "in_range", "1", "9", True),
            ("5", "in_range", "1", "", False),
            ("abc", "greater_or_equal", "1", None, False),
            ("5", "strange", "1", None, False),
        ]
        for actual, operator, expected, expected_to, result in cases:
            with self.subTest(operator=operator, actual=actual):
                self.assertEqual(compare_values(actual, operator, expected, expected_to), result)

        self.assertEqual(condition_value({"teamName": "A"}, "team_name"), "A")
        self.assertEqual(condition_value({}, ""), "")

    def test_should_delay(self):
        delayed, scheduled_for = should_delay({"settings": DELAYED})
        self.assertTrue(delayed)
        self.assertGreater(scheduled_for, timezone.now() + timedelta(minutes=9))
        self.assertEqual(should_delay({"settings": IMMEDIATE}), (False, None))
        self.assertEqual(should_delay({}), (False, None))

    def test_has_task_data_changed_and_deadline_changed(self):
        base = {"title": "API", "assigneeId": 1, "endDate": "2026-01-10", "inSprint": False}

        self.assertFalse(has_task_data_changed(base, None))
        self.assertFalse(has_task_data_changed(base, dict(base)))
        self.assertTrue(has_task_data_changed({**base, "title": "UI"}, base))
        self.assertTrue(has_task_data_changed({**base, "inSprint": True}, base))
        self.assertTrue(has_task_data_changed({"assignee_id": 2}, {"assigneeId": 1}))
        self.assertFalse(deadline_changed(base, None))
        self.assertFalse(deadline_changed(base, {"end_date": "2026-01-10"}))
        self.assertTrue(deadline_changed(base, {"endDate": "2026-01-11"}))

    @override_settings(PLANNER_SPRINT_WEEK_UTC_OFFSET_HOURS=99)
    def test_sprint_week_timezone_falls_back_to_default_offset(self):
        self.assertEqual(sprint_week_timezone().utcoffset(None), timedelta(hours=3))

    @override_settings(PLANNER_SPRINT_WEEK_UTC_OFFSET_HOURS=0)
    def test_sprint_week_key_format(self):
        self.assertEqual(sprint_week_key(datetime(2026, 1, 5, 12, 0, tzinfo=dt_timezone.utc)), "2026-W02")

    def test_find_sprint_sweep_robot_prefers_config_and_falls_back_to_default(self):
        own_robot = {"id": SPRINT_SWEEP_ROBOT_ID, "enabled": False}

        self.assertIs(find_sprint_sweep_robot({"eventId": 1, "robots": [own_robot]}), own_robot)
        default_robot = find_sprint_sweep_robot({"eventId": 1, "robots": "broken"})
        self.assertEqual(default_robot["id"], SPRINT_SWEEP_ROBOT_ID)
        self.assertTrue(default_robot["enabled"])


class PlannerEventDetectionTests(SimpleTestCase):
    def team(self, **extra):
        return {"id": TEAM_ID, "name": "Команда", "eventId": EVENT_ID, "curatorId": 900, "memberIds": [], **extra}

    def codes(self, events):
        return sorted((event.code, event.entity_type, event.entity_id) for event in events)

    def test_new_parent_task_without_assignee(self):
        state = {"teams": [self.team()], "parent_tasks": [{"id": 1, "teamId": TEAM_ID, "status": ""}]}

        events = detect_planner_events({}, state)

        self.assertEqual(
            self.codes(events),
            [("task.created", "parent_task", "1"), ("task.unassigned", "parent_task", "1")],
        )
        self.assertEqual(events[0].event_id, EVENT_ID)
        self.assertEqual(events[0].team["name"], "Команда")

    def test_parent_task_assignee_and_deadline_changes(self):
        previous = {"teams": [self.team()], "parent_tasks": [{"id": 1, "teamId": TEAM_ID, "assigneeId": 5, "endDate": "2030-01-01"}]}
        current = {"teams": [self.team()], "parent_tasks": [{"id": 1, "teamId": TEAM_ID, "endDate": "2030-01-02"}]}

        events = detect_planner_events(previous, current)

        self.assertEqual(
            self.codes(events),
            [
                ("task.assignee_changed", "parent_task", "1"),
                ("task.deadline_changed", "parent_task", "1"),
                ("task.unassigned", "parent_task", "1"),
            ],
        )
        deadline_event = next(event for event in events if event.code == "task.deadline_changed")
        self.assertTrue(deadline_event.item["deadlineChanged"])

    def test_new_subtask_in_sprint(self):
        state = {
            "teams": [self.team()],
            "subtasks": [{"id": 2, "teamId": TEAM_ID, "assigneeId": 5, "inSprint": True, "status": "В работе"}],
        }

        self.assertEqual(
            self.codes(detect_planner_events({}, state)),
            [
                ("task.created", "subtask", "2"),
                ("task.sprint_added", "subtask", "2"),
                ("task.status_started", "subtask", "2"),
            ],
        )

    def test_subtask_changes_produce_specific_events(self):
        previous_item = {"id": 3, "teamId": TEAM_ID, "assigneeId": 5, "status": "В работе", "endDate": "2030-01-01", "inSprint": False}
        current_item = {"id": 3, "teamId": TEAM_ID, "assigneeId": 6, "status": "На проверке", "endDate": "2030-01-05", "inSprint": True}

        events = detect_planner_events(
            {"teams": [self.team()], "subtasks": [previous_item]},
            {"teams": [self.team()], "subtasks": [current_item]},
        )

        self.assertEqual(
            [code for code, _, _ in self.codes(events)],
            [
                "task.assignee_changed",
                "task.deadline_changed",
                "task.review_requested",
                "task.sprint_added",
                "task.status_changed",
                "task.subtask_changed",
            ],
        )

    def test_subtask_done_event(self):
        previous_item = {"id": 4, "teamId": TEAM_ID, "assigneeId": 5, "status": "На проверке"}
        current_item = {"id": 4, "teamId": TEAM_ID, "assigneeId": 5, "status": "Готово"}

        codes = [code for code, _, _ in self.codes(detect_planner_events(
            {"teams": [self.team()], "subtasks": [previous_item]},
            {"teams": [self.team()], "subtasks": [current_item]},
        ))]

        self.assertEqual(codes, ["task.status_changed", "task.status_done"])

    def test_deadline_soon_and_overdue_events(self):
        today = timezone.localdate()
        soon = {"id": 5, "teamId": TEAM_ID, "assigneeId": 1, "status": "В работе", "endDate": (today + timedelta(days=1)).isoformat()}
        overdue = {"id": 6, "teamId": TEAM_ID, "assigneeId": 1, "status": "В работе", "endDate": (today - timedelta(days=2)).isoformat()}
        done_overdue = {"id": 7, "teamId": TEAM_ID, "assigneeId": 1, "status": "Готово", "endDate": (today - timedelta(days=2)).isoformat()}
        state = {"teams": [self.team()], "subtasks": [soon, overdue, done_overdue]}

        events = detect_planner_events(state, state)

        self.assertEqual(
            self.codes(events),
            [("task.deadline_soon", "subtask", "5"), ("task.overdue", "subtask", "6")],
        )

    def test_team_events(self):
        cases = [
            ({}, {"teams": [self.team(confirmed=True)]}, ["team.confirmed"]),
            ({"teams": [self.team()]}, {"teams": [self.team(confirmed=True)]}, ["team.confirmed"]),
            ({"teams": [self.team(curatorId=None)]}, {"teams": [self.team()]}, ["team.curator_assigned"]),
            ({}, {"teams": [self.team()]}, []),
        ]
        for previous, current, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual([event.code for event in detect_planner_events(previous, current)], expected)

    def test_items_of_team_without_event_are_ignored(self):
        team = {"id": TEAM_ID, "name": "Без мероприятия", "confirmed": True}
        state = {"teams": [team], "subtasks": [{"id": 1, "teamId": TEAM_ID}], "parent_tasks": [{"id": 2, "teamId": TEAM_ID}]}

        self.assertEqual(detect_planner_events({}, state), [])
        self.assertEqual(detect_planner_scan_events(state), [])

    def test_scan_events(self):
        stale_time = (timezone.now() - timedelta(days=5)).isoformat()
        busy_tasks = [
            {"id": 10 + index, "teamId": TEAM_ID, "assigneeId": 41, "status": "В работе"}
            for index in range(5)
        ]
        state = {
            "teams": [self.team(confirmed=True, memberIds=[41, 42, "bad"])],
            "parent_tasks": [{"id": 1, "teamId": TEAM_ID, "status": "Бэклог"}, "not-a-dict"],
            "subtasks": busy_tasks + [
                {"id": 20, "teamId": TEAM_ID, "assigneeId": 41, "status": "Готово"},
                {"id": 21, "teamId": TEAM_ID, "assigneeId": 41, "status": "В работе", "updatedAt": stale_time},
            ],
        }

        events = detect_planner_scan_events(state)

        codes = sorted(event.code for event in events)
        self.assertEqual(codes, ["member.idle", "member.overloaded", "task.stale", "task.unassigned"])
        overloaded = next(event for event in events if event.code == "member.overloaded")
        self.assertEqual(overloaded.item["activeTaskCount"], 6)
        idle = next(event for event in events if event.code == "member.idle")
        self.assertEqual(idle.item["memberId"], 42)
        stale = next(event for event in events if event.code == "task.stale")
        self.assertEqual(stale.item["inactiveDays"], 5)


class PlannerAutomationDbTestBase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.curator = user_model.objects.create_user(
            username="planner-curator@example.test",
            email="planner-curator@example.test",
            password="StrongPass123",
        )
        self.assignee = user_model.objects.create_user(
            username="planner-assignee@example.test",
            email="planner-assignee@example.test",
            password="StrongPass123",
        )
        self.team = {
            "id": TEAM_ID,
            "name": "Команда",
            "eventId": EVENT_ID,
            "curatorId": self.curator.id,
            "memberIds": [self.assignee.id],
        }
        self.workspace = PlannerWorkspaceState.objects.create(
            teams=[self.team],
            parent_tasks=[{"id": 1, "teamId": TEAM_ID, "title": "Большая задача"}],
            subtasks=[self.subtask()],
        )

    def subtask(self, **extra):
        item = {
            "id": 10,
            "teamId": TEAM_ID,
            "parentTaskId": 1,
            "title": "API",
            "assigneeId": self.assignee.id,
            "status": "Бэклог",
            "inSprint": False,
            "endDate": (timezone.localdate() + timedelta(days=10)).isoformat(),
        }
        item.update(extra)
        return item

    def make_config(self, *, triggers=None, robots=None):
        return PlannerAutomationConfig.objects.create(
            event_id=EVENT_ID,
            stages=create_stage_list(),
            triggers=triggers or [],
            robots=robots or [],
        )

    def make_event(self, code="task.status_changed", *, item=None, entity_type="subtask", fingerprint="fp"):
        item = item if item is not None else {**self.workspace.subtasks[0], "type": entity_type}
        return PlannerAutomationEvent(
            code=code,
            entity_type=entity_type,
            entity_id=str(item.get("id")),
            item=item,
            previous_item=None,
            team=self.team,
            event_id=EVENT_ID,
            team_id=TEAM_ID,
            fingerprint=fingerprint,
        )

    def last_log(self, rule_id):
        return PlannerAutomationExecutionLog.objects.filter(rule_id=rule_id).latest("id")

    def vk_profile(self, user, *, confirmed=True):
        profile, _ = Profile.objects.update_or_create(
            user=user,
            defaults={
                "surname": "Тестов",
                "name": "Тест",
                "email": user.email,
                "course": 1,
                "vk": "https://vk.com/id777",
                "vk_user_id": 777,
                "vk_confirmed_at": timezone.now() if confirmed else None,
            },
        )
        return profile


def create_stage_list():
    return [
        {"id": "backlog", "title": "Бэклог"},
        {"id": "planned", "title": "Запланировано"},
        {"id": "in-progress", "title": "В работе"},
        {"id": "review", "title": "На проверке"},
        {"id": "done", "title": "Готово"},
    ]


class PlannerContextAndHelperTests(PlannerAutomationDbTestBase):
    def test_event_context_contains_task_and_team_fields(self):
        overdue_item = self.subtask(endDate=(timezone.localdate() - timedelta(days=2)).isoformat(), memberId=3)

        context = event_context(self.make_event(item=overdue_item))

        self.assertEqual(context["teamName"], "Команда")
        self.assertEqual(context["curatorId"], self.curator.id)
        self.assertEqual(context["assigneeId"], self.assignee.id)
        self.assertEqual(context["task"], "API")
        self.assertEqual(context["daysToDeadline"], -2)
        self.assertTrue(context["isOverdue"])
        self.assertEqual(context["memberId"], 3)
        self.assertEqual(render_template("{teamName}/{task}/{status}", self.make_event(item=overdue_item)), "Команда/API/Бэклог")

    def test_conditions_match_modes(self):
        event = self.make_event()
        match = {"field": "task_status", "operator": "equals", "value": "бэклог"}
        mismatch = {"field": "teamName", "value": "Другая"}

        self.assertTrue(conditions_match(None, event))
        self.assertTrue(conditions_match({"condition": {"rules": [7]}}, event))
        self.assertTrue(conditions_match({"condition": {"rules": [match]}}, event))
        self.assertFalse(conditions_match({"condition": {"rules": [match, mismatch]}}, event))
        self.assertTrue(conditions_match({"condition": {"mode": "any", "rules": [match, mismatch]}}, event))

    def test_create_notification_checks_user_exists(self):
        self.assertFalse(create_notification(None, "Т", "С"))
        self.assertFalse(create_notification(999999, "Т", "С"))
        self.assertTrue(create_notification(self.assignee.id, "Т", "С"))
        self.assertEqual(Notification.objects.get(user=self.assignee).link, "/planner")

    def test_send_vk_notification_validates_profile(self):
        self.assertFalse(send_vk_notification(None, "текст"))

        Profile.objects.filter(user=self.assignee).delete()
        with self.assertRaisesMessage(ValueError, "у пользователя не указан корректный VK"):
            send_vk_notification(self.assignee.id, "текст")

        self.vk_profile(self.assignee, confirmed=False)
        with self.assertRaisesMessage(ValueError, "пользователь не подтвердил VK-бота"):
            send_vk_notification(self.assignee.id, "текст")

    def test_send_vk_notification_with_disabled_vk_raises(self):
        self.vk_profile(self.assignee)

        with self.assertRaises(VKConfigurationError):
            send_vk_notification(self.assignee.id, "текст")

    @override_settings(**VK_TEST_SETTINGS)
    @patch("integrations.vk.services.urllib.request.urlopen")
    def test_send_vk_notification_sends_message(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"response": 1}).encode()
        self.vk_profile(self.assignee)

        self.assertTrue(send_vk_notification(self.assignee.id, "текст"))
        urlopen.assert_called_once()

    def test_config_model_to_dict(self):
        empty = PlannerAutomationConfig.objects.create(event_id=EVENT_ID + 1)
        filled = self.make_config(robots=[make_robot("own", "notification.assignee")])

        self.assertEqual(config_model_to_dict(empty)["eventId"], EVENT_ID + 1)
        self.assertTrue(config_model_to_dict(empty)["robots"])
        filled_dict = config_model_to_dict(filled)
        self.assertEqual([robot["id"] for robot in filled_dict["robots"]], ["own"])
        self.assertEqual(filled_dict["triggers"], [])

    def test_get_or_create_config_is_idempotent(self):
        first = get_or_create_config(EVENT_ID)

        self.assertEqual(get_or_create_config(EVENT_ID).pk, first.pk)
        self.assertEqual(first.scope, PlannerAutomationConfig.SCOPE_PLANNER)
        self.assertTrue(first.robots)

    def test_workspace_state_dict_replaces_broken_sections(self):
        self.workspace.columns = "broken"
        self.workspace.teams = None

        state = workspace_state_dict(self.workspace)

        self.assertEqual(state["teams"], [])
        self.assertEqual(state["columns"], [])
        self.assertEqual(state["subtasks"], self.workspace.subtasks)

    def test_update_item_status(self):
        event = self.make_event()

        self.assertFalse(update_item_status(self.workspace, self.make_event(entity_type="parent_task"), "Готово"))
        self.assertTrue(update_item_status(self.workspace, event, "Новая колонка"))
        self.assertFalse(update_item_status(self.workspace, event, "Новая колонка"))

        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subtasks[0]["status"], "Новая колонка")
        self.assertTrue(self.workspace.subtasks[0]["inSprint"])
        self.assertIn("Новая колонка", self.workspace.columns)
        self.assertEqual(event.item["status"], "Новая колонка")


class PlannerRobotActionTests(PlannerAutomationDbTestBase):
    def run_robot(self, robot, *, event=None):
        # Робот передаётся явно, поэтому одна конфигурация мероприятия годится для нескольких вызовов.
        config_model = PlannerAutomationConfig.objects.filter(event_id=EVENT_ID).first() or self.make_config(robots=[robot])
        return run_robot_action(self.workspace, config_model, config_model_to_dict(config_model), robot, event or self.make_event())

    def test_assignee_notification(self):
        self.assertTrue(self.run_robot(make_robot("assignee", "notification.assignee")))

        notification = Notification.objects.get(user=self.assignee)
        self.assertEqual(notification.title, "Задача API")
        self.assertEqual(notification.message, "Команда Команда: API")
        log = self.last_log("assignee")
        self.assertEqual(log.status, PlannerAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(log.message, "Уведомление отправлено исполнителю.")
        self.assertEqual(log.team_id, TEAM_ID)

    def test_assignee_notification_without_assignee_is_skipped(self):
        event = self.make_event(item=self.subtask(assigneeId=None))

        self.assertFalse(self.run_robot(make_robot("assignee", "notification.assignee"), event=event))

        self.assertEqual(self.last_log("assignee").message, "Исполнитель не найден.")

    def test_curator_notifications(self):
        for index, action in enumerate(["notification.curator", "notification.deadline", "task.review"]):
            with self.subTest(action=action):
                robot = make_robot(f"curator-{index}", action)
                config_model, _ = PlannerAutomationConfig.objects.get_or_create(event_id=EVENT_ID)
                self.assertTrue(run_robot_action(self.workspace, config_model, {}, robot, self.make_event()))
                self.assertEqual(self.last_log(f"curator-{index}").message, "Уведомление отправлено куратору.")
        self.assertEqual(Notification.objects.filter(user=self.curator).count(), 3)

    def test_curator_notification_without_curator_is_skipped(self):
        self.team["curatorId"] = None

        self.assertFalse(self.run_robot(make_robot("curator", "notification.curator")))

        self.assertEqual(self.last_log("curator").message, "Куратор команды не найден.")

    def test_default_title_is_used_without_subject(self):
        self.run_robot(make_robot("no-title", "notification.assignee", subject="", title=""))

        self.assertEqual(Notification.objects.get(user=self.assignee).title, "Уведомление планировщика")

    def test_vk_robots_log_errors(self):
        self.vk_profile(self.assignee)
        self.assertFalse(self.run_robot(make_robot("vk-assignee", "message.vk.assignee")))
        self.assertEqual(self.last_log("vk-assignee").message, "VK integration is disabled.")

        self.assertFalse(self.run_robot(make_robot("vk-curator", "message.vk.curator")))
        self.assertEqual(self.last_log("vk-curator").message, "у пользователя не указан корректный VK")
        self.assertEqual(self.last_log("vk-curator").status, PlannerAutomationExecutionLog.STATUS_SKIPPED)

    @override_settings(**VK_TEST_SETTINGS)
    @patch("integrations.vk.services.urllib.request.urlopen")
    def test_vk_robots_send_messages(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"response": 1}).encode()
        self.vk_profile(self.assignee)
        self.vk_profile(self.curator)

        self.assertTrue(self.run_robot(make_robot("vk-assignee", "message.vk.assignee")))
        self.assertTrue(self.run_robot(make_robot("vk-curator", "message.vk.curator")))

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(self.last_log("vk-curator").message, "VK-сообщение отправлено куратору.")
        self.assertEqual(self.last_log("vk-assignee").message, "VK-сообщение отправлено исполнителю.")

    def test_task_create_robot_appends_parent_task(self):
        self.assertTrue(self.run_robot(make_robot("create", "task.create", message="Описание {task}")))

        self.workspace.refresh_from_db()
        created = self.workspace.parent_tasks[-1]
        self.assertEqual(created["id"], 2)
        self.assertEqual(created["teamId"], TEAM_ID)
        self.assertEqual(created["title"], "Задача API")
        self.assertEqual(created["description"], "Описание API")
        self.assertEqual(created["assigneeId"], self.curator.id)
        self.assertEqual(created["automationRuleId"], "create")
        self.assertEqual(created["sourceTaskId"], "10")
        self.assertEqual(self.last_log("create").message, "Создана задача автоматизации.")

    def test_unknown_action_is_skipped(self):
        self.assertFalse(self.run_robot(make_robot("unknown", "sprint.remove_done")))

        self.assertEqual(self.last_log("unknown").message, "Действие робота sprint.remove_done пока не поддерживается.")

    def test_delayed_robot_creates_single_pending_log(self):
        robot = make_robot("delayed", "notification.assignee", settings=dict(DELAYED))
        config_model = self.make_config(robots=[robot])
        event = self.make_event()

        self.assertFalse(run_robot_action(self.workspace, config_model, {}, robot, event))
        self.assertFalse(run_robot_action(self.workspace, config_model, {}, robot, event))

        log = PlannerAutomationExecutionLog.objects.get(rule_id="delayed")
        self.assertEqual(log.status, PlannerAutomationExecutionLog.STATUS_PENDING)
        self.assertIsNone(log.executed_at)
        self.assertFalse(Notification.objects.exists())


class PlannerTriggerTests(PlannerAutomationDbTestBase):
    def run_single_trigger(self, trigger, *, event=None, robots=None):
        config_model = self.make_config(triggers=[trigger], robots=robots)
        return run_trigger(self.workspace, config_model, config_model_to_dict(config_model), trigger, event or self.make_event())

    def test_trigger_moves_subtask_and_runs_stage_robots(self):
        changed = self.run_single_trigger(
            make_trigger("to-review", "task.status_changed", target_stage_id="review"),
            robots=[make_robot("review-robot", "task.review", stage_id="review")],
        )

        self.assertTrue(changed)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subtasks[0]["status"], "На проверке")
        self.assertEqual(self.last_log("to-review").message, "Триггер перевел элемент на стадию «На проверке».")
        self.assertTrue(Notification.objects.filter(user=self.curator).exists())

    def test_trigger_without_change_logs_success(self):
        changed = self.run_single_trigger(make_trigger("same", "task.status_changed", target_stage_id="backlog"))

        self.assertFalse(changed)
        log = self.last_log("same")
        self.assertEqual(log.status, PlannerAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(log.message, "Триггер обработан без изменения статуса.")

    def test_trigger_is_not_repeated_for_same_event(self):
        trigger = make_trigger("once", "task.status_changed", target_stage_id="review")
        config_model = self.make_config(triggers=[trigger])
        config = config_model_to_dict(config_model)
        event = self.make_event()

        self.assertTrue(run_trigger(self.workspace, config_model, config, trigger, event))
        self.assertFalse(run_trigger(self.workspace, config_model, config, trigger, event))

    def test_trigger_with_failed_conditions_is_skipped(self):
        settings = {**IMMEDIATE, "condition": {"rules": [{"field": "teamName", "value": "Другая"}]}}

        self.assertFalse(self.run_single_trigger(make_trigger("cond", "x", target_stage_id="review", settings=settings)))

        self.assertEqual(self.last_log("cond").message, "Условия триггера не выполнены.")

    def test_back_transition_is_blocked(self):
        event = self.make_event(item=self.subtask(status="Готово"))

        self.assertFalse(self.run_single_trigger(make_trigger("back", "x", target_stage_id="planned"), event=event))

        self.assertEqual(self.last_log("back").message, "Переход на предыдущую стадию запрещен настройкой триггера.")

    def test_delayed_trigger_creates_pending_log(self):
        self.assertFalse(
            self.run_single_trigger(make_trigger("delayed", "x", target_stage_id="review", settings=dict(DELAYED)))
        )

        log = self.last_log("delayed")
        self.assertEqual(log.status, PlannerAutomationExecutionLog.STATUS_PENDING)
        self.assertEqual(log.message, "Запланировано отложенное выполнение триггера.")

    def test_run_config_for_event_filters_triggers(self):
        config_model = self.make_config(
            triggers=[
                make_trigger("match", "task.status_changed", target_stage_id="review"),
                make_trigger("disabled", "task.status_changed", target_stage_id="done", enabled=False),
                make_trigger("deleted", "task.status_changed", target_stage_id="done", deleted=True),
                make_trigger("other", "task.created", target_stage_id="done"),
            ],
        )

        self.assertTrue(run_config_for_event(self.workspace, config_model, self.make_event()))

        self.assertEqual(
            list(PlannerAutomationExecutionLog.objects.filter(rule_kind="trigger").values_list("rule_id", flat=True)),
            ["match"],
        )

    def test_sprint_added_moves_started_subtask_back_to_planned(self):
        # Текущее поведение: даже при запрете обратного перехода событие «добавлена в спринт»
        # возвращает подзадачу в стадию «Запланировано».
        self.workspace.subtasks = [self.subtask(status="В работе", inSprint=True)]
        self.workspace.save(update_fields=["subtasks"])
        config_model = self.make_config(triggers=[make_trigger("sprint", "task.sprint_added", target_stage_id="planned")])
        event = self.make_event("task.sprint_added")

        self.assertTrue(run_config_for_event(self.workspace, config_model, event))

        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subtasks[0]["status"], "Запланировано")


class PlannerRunAutomationTests(PlannerAutomationDbTestBase):
    def test_run_planner_automation_reacts_to_review_status(self):
        previous_state = workspace_state_dict(self.workspace)
        previous_state = json.loads(json.dumps(previous_state))
        self.workspace.subtasks = [self.subtask(status="На проверке", inSprint=True)]
        self.workspace.save(update_fields=["subtasks"])

        result = run_planner_automation(previous_state, self.workspace)

        self.assertGreaterEqual(result["events"], 1)
        self.assertGreaterEqual(result["changed"], 1)
        # Робот по умолчанию на стадии «На проверке» уведомляет куратора.
        self.assertTrue(Notification.objects.filter(user=self.curator, title="Проверить результат").exists())

    def test_apply_sprint_added_fallback_moves_new_sprint_subtask(self):
        previous_state = {"subtasks": [self.subtask()]}
        self.workspace.subtasks = [self.subtask(inSprint=True)]
        self.workspace.save(update_fields=["subtasks"])

        self.assertTrue(apply_sprint_added_fallback(previous_state, self.workspace))

        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subtasks[0]["status"], "Запланировано")
        self.assertTrue(
            PlannerAutomationExecutionLog.objects.filter(
                rule_kind="trigger",
                event_code="task.sprint_added",
                status=PlannerAutomationExecutionLog.STATUS_SUCCESS,
            ).exists()
        )

    def test_apply_sprint_added_fallback_ignores_unchanged_and_unbound_subtasks(self):
        self.workspace.teams = [self.team, {"id": 99, "name": "Без мероприятия"}]
        self.workspace.subtasks = [
            self.subtask(inSprint=True),
            self.subtask(id=11, teamId=99, inSprint=True),
            self.subtask(id=12, inSprint=False),
        ]
        self.workspace.save(update_fields=["teams", "subtasks"])
        previous_state = {"subtasks": [self.subtask(inSprint=True)]}

        self.assertFalse(apply_sprint_added_fallback(previous_state, self.workspace))
        self.assertFalse(PlannerAutomationExecutionLog.objects.exists())

    def test_scan_planner_deadlines(self):
        self.workspace.subtasks = [self.subtask(assigneeId=None, status="В работе")]
        self.workspace.save(update_fields=["subtasks"])

        result = scan_planner_deadlines()

        self.assertGreaterEqual(result["events"], 1)
        self.assertTrue(PlannerAutomationConfig.objects.filter(event_id=EVENT_ID).exists())

    def test_functions_without_workspace_return_zeros(self):
        PlannerWorkspaceState.objects.all().delete()

        self.assertEqual(scan_planner_deadlines(), {"events": 0, "changed": 0})
        self.assertEqual(run_due_planner_automation(), {"processed": 0, "changed": 0})
        self.assertEqual(sweep_done_subtasks_from_sprint(), {"events": 0, "changed": 0})


class PlannerPendingLogTests(PlannerAutomationDbTestBase):
    def make_pending_log(self, config_model, *, rule_id, rule_kind="robot", entity_type="subtask", entity_id="10", scheduled_delta=-1):
        return PlannerAutomationExecutionLog.objects.create(
            config=config_model,
            event_id=EVENT_ID,
            team_id=TEAM_ID,
            entity_type=entity_type,
            entity_id=entity_id,
            event_code="task.status_changed",
            rule_kind=rule_kind,
            rule_id=rule_id,
            run_key=f"pending-{rule_id}-{entity_type}-{entity_id}",
            status=PlannerAutomationExecutionLog.STATUS_PENDING,
            scheduled_for=timezone.now() + timedelta(minutes=scheduled_delta),
        )

    def assert_log(self, log, status, message):
        log.refresh_from_db()
        self.assertEqual(log.status, status)
        self.assertEqual(log.message, message)
        self.assertIsNotNone(log.executed_at)

    def test_missing_rule_fails_log(self):
        log = self.make_pending_log(self.make_config(), rule_id="removed")

        self.assertFalse(execute_pending_log(log, self.workspace))

        self.assert_log(log, PlannerAutomationExecutionLog.STATUS_FAILED, "Правило для отложенного выполнения не найдено.")

    def test_missing_item_skips_log(self):
        config_model = self.make_config(robots=[make_robot("robot", "notification.assignee")])
        log = self.make_pending_log(config_model, rule_id="robot", entity_id="404")

        self.assertFalse(execute_pending_log(log, self.workspace))

        self.assert_log(log, PlannerAutomationExecutionLog.STATUS_SKIPPED, "Элемент для отложенного выполнения не найден.")

    def test_conditions_no_longer_matching_skip_log(self):
        settings = {**DELAYED, "condition": {"rules": [{"field": "teamName", "value": "Другая"}]}}
        config_model = self.make_config(robots=[make_robot("cond", "notification.assignee", settings=settings)])
        log = self.make_pending_log(config_model, rule_id="cond")

        self.assertFalse(execute_pending_log(log, self.workspace))

        self.assert_log(log, PlannerAutomationExecutionLog.STATUS_SKIPPED, "Условия отложенного правила больше не выполнены.")

    def test_pending_notification_robots(self):
        cases = [
            ("assignee", "notification.assignee", self.assignee),
            ("curator", "notification.curator", self.curator),
        ]
        config_model = self.make_config(robots=[make_robot(rule_id, action) for rule_id, action, _ in cases])
        for rule_id, _, recipient in cases:
            with self.subTest(rule_id=rule_id):
                log = self.make_pending_log(config_model, rule_id=rule_id)
                self.assertTrue(execute_pending_log(log, self.workspace))
                self.assert_log(log, PlannerAutomationExecutionLog.STATUS_SUCCESS, "Отложенное правило выполнено.")
                self.assertTrue(Notification.objects.filter(user=recipient).exists())

    def test_pending_team_notification_uses_team_as_item(self):
        config_model = self.make_config(robots=[make_robot("team-curator", "notification.curator", subject="Команда {title}")])
        log = self.make_pending_log(config_model, rule_id="team-curator", entity_type="team", entity_id=str(TEAM_ID))

        self.assertTrue(execute_pending_log(log, self.workspace))

        self.assertEqual(Notification.objects.get(user=self.curator).title, "Команда Команда")

    def test_pending_vk_robots_without_vk_are_skipped(self):
        config_model = self.make_config(
            robots=[make_robot("vk-a", "message.vk.assignee"), make_robot("vk-c", "message.vk.curator")]
        )
        for rule_id in ("vk-a", "vk-c"):
            with self.subTest(rule_id=rule_id):
                log = self.make_pending_log(config_model, rule_id=rule_id)
                self.assertFalse(execute_pending_log(log, self.workspace))
                self.assert_log(log, PlannerAutomationExecutionLog.STATUS_SKIPPED, "Отложенное правило не внесло изменений.")

    def test_pending_task_create_and_unknown_action(self):
        config_model = self.make_config(
            robots=[make_robot("create", "task.create"), make_robot("unknown", "something.else")]
        )
        create_log = self.make_pending_log(config_model, rule_id="create")
        unknown_log = self.make_pending_log(config_model, rule_id="unknown")

        self.assertTrue(execute_pending_log(create_log, self.workspace))
        self.assertFalse(execute_pending_log(unknown_log, self.workspace))

        self.workspace.refresh_from_db()
        self.assertEqual(len(self.workspace.parent_tasks), 2)
        self.assert_log(unknown_log, PlannerAutomationExecutionLog.STATUS_SKIPPED, "Отложенное правило не внесло изменений.")

    def test_pending_trigger_moves_subtask(self):
        config_model = self.make_config(
            triggers=[make_trigger("later", "task.status_changed", target_stage_id="review", settings=dict(DELAYED))]
        )
        log = self.make_pending_log(config_model, rule_id="later", rule_kind="trigger")

        self.assertTrue(execute_pending_log(log, self.workspace))

        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subtasks[0]["status"], "На проверке")
        self.assert_log(log, PlannerAutomationExecutionLog.STATUS_SUCCESS, "Отложенное правило выполнено.")

    def test_run_due_planner_automation_processes_only_due_logs(self):
        config_model = self.make_config(
            robots=[make_robot("due", "notification.assignee"), make_robot("future", "notification.assignee")]
        )
        due_log = self.make_pending_log(config_model, rule_id="due")
        future_log = self.make_pending_log(config_model, rule_id="future", scheduled_delta=60)

        result = run_due_planner_automation()

        self.assertEqual(result, {"processed": 1, "changed": 1})
        due_log.refresh_from_db()
        future_log.refresh_from_db()
        self.assertEqual(due_log.status, PlannerAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(future_log.status, PlannerAutomationExecutionLog.STATUS_PENDING)


@override_settings(PLANNER_SPRINT_WEEK_UTC_OFFSET_HOURS=3)
class PlannerSprintSweepConditionTests(PlannerAutomationDbTestBase):
    WEEK_ONE = datetime(2026, 7, 15, 9, 0, tzinfo=dt_timezone.utc)
    WEEK_TWO = datetime(2026, 7, 20, 9, 0, tzinfo=dt_timezone.utc)

    def test_sweep_respects_robot_conditions(self):
        self.workspace.subtasks = [
            self.subtask(id=1, status="Готово", inSprint=True, role="Backend"),
            self.subtask(id=2, status="Готово", inSprint=True, role="Frontend"),
        ]
        self.workspace.save(update_fields=["subtasks"])
        sweep_done_subtasks_from_sprint(now=self.WEEK_ONE)
        config = PlannerAutomationConfig.objects.get(event_id=EVENT_ID)
        robots = config.robots
        for robot in robots:
            if robot["id"] == SPRINT_SWEEP_ROBOT_ID:
                robot["settings"] = {**IMMEDIATE, "condition": {"rules": [{"field": "role", "value": "Backend"}]}}
        config.robots = robots
        config.save(update_fields=["robots"])

        result = sweep_done_subtasks_from_sprint(now=self.WEEK_TWO)

        self.assertEqual(result["changed"], 1)
        self.workspace.refresh_from_db()
        in_sprint = {item["id"]: item["inSprint"] for item in self.workspace.subtasks}
        self.assertEqual(in_sprint, {1: False, 2: True})
