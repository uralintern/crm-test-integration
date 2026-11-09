"""Характеризационные тесты движка CRM-автоматизации (users.automation_engine).

Фиксируют текущее поведение перед реорганизацией кода. VK никогда не вызывается
по-настоящему: в api.settings_test интеграция выключена, а успешные отправки
подменяются в модулях integrations.vk.*.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from users.automation_engine import (
    CRMAutomationEvent,
    application_display_name,
    compare_values,
    condition_value,
    conditions_match,
    config_model_to_dict,
    create_notification,
    create_organizer_notifications,
    event_context,
    execute_pending_log,
    get_application_organizers,
    get_or_create_config,
    get_robot_attachments,
    latest_test_result,
    lower_text,
    normalize_crm_automation_config_dict,
    normalized_text,
    render_template,
    robot_attachment_ids,
    run_crm_automation,
    run_due_crm_automation,
    run_robot_action,
    run_stage_robots,
    run_trigger,
    should_delay,
    stable_fingerprint,
    stage_by_id,
    status_stage_id,
    target_status_for_stage,
    to_int,
    update_application_status,
    user_display_name,
)
from users.models import (
    Application,
    CRMAutomationAttachment,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    Event,
    Notification,
    Profile,
    Status,
    Test,
    TestResult,
    TestSession,
)


IMMEDIATE = {"runMode": "queue", "timing": "immediate", "delayMinutes": 0, "condition": {"mode": "all", "rules": []}}
DELAYED = {"runMode": "queue", "timing": "delayed", "delayMinutes": 5, "condition": {"mode": "all", "rules": []}}

STAGES = [
    {"id": "stage-a", "title": "Статус А", "description": ""},
    {"id": "stage-b", "title": "Статус Б", "description": ""},
    {"id": "stage-c", "title": "Статус В", "description": ""},
]


def get_status(name: str) -> Status:
    # Миграции уже засевают часть статусов, поэтому не создаём дубли.
    status_obj = Status.objects.filter(name=name).order_by("id").first()
    return status_obj or Status.objects.create(name=name)


def make_robot(robot_id: str, action: str, *, stage_id: str = "stage-a", settings=None, **extra) -> dict:
    robot = {
        "id": robot_id,
        "stageId": stage_id,
        "title": f"Робот {robot_id}",
        "description": "",
        "action": action,
        "enabled": True,
        "settings": settings or dict(IMMEDIATE),
        "subject": "Тема для {student}",
        "message": "Сообщение по «{event}»",
    }
    robot.update(extra)
    return robot


def make_trigger(trigger_id: str, event_code: str, *, stage_id: str, settings=None, **extra) -> dict:
    trigger = {
        "id": trigger_id,
        "stageId": stage_id,
        "title": f"Триггер {trigger_id}",
        "description": "",
        "eventCode": event_code,
        "enabled": True,
        "settings": settings or dict(IMMEDIATE),
        "targetStageId": stage_id,
        "allowBackTransition": False,
    }
    trigger.update(extra)
    return trigger


class CRMAutomationPureFunctionTests(SimpleTestCase):
    def test_to_int_converts_or_returns_none(self):
        cases = [(None, None), ("", None), ("12", 12), (7, 7), ("abc", None), ([1], None)]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(to_int(raw), expected)

    def test_text_helpers_strip_and_lower(self):
        self.assertEqual(normalized_text(None), "")
        self.assertEqual(normalized_text("  Привет "), "Привет")
        self.assertEqual(lower_text(" ГОТОВО "), "готово")

    def test_stable_fingerprint_is_short_and_independent_of_key_order(self):
        first = stable_fingerprint({"a": 1, "b": "x"})
        second = stable_fingerprint({"b": "x", "a": 1})

        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        self.assertNotEqual(first, stable_fingerprint({"a": 2, "b": "x"}))

    def test_compare_values_supports_all_operators(self):
        cases = [
            ("Готово", "equals", "готово", None, True),
            ("Готово", "equals", "другое", None, False),
            ("Готово", "not_equals", "другое", None, True),
            ("Готово", "not_equals", "ГОТОВО", None, False),
            ("Backend разработчик", "contains", "backend", None, True),
            ("Backend", "contains", "front", None, False),
            ("Backend", "not_contains", "front", None, True),
            ("Backend", "not_contains", "back", None, False),
            ("x", "filled", "", None, True),
            ("  ", "filled", "", None, False),
            ("", "empty", "", None, True),
            ("x", "empty", "", None, False),
            ("85", "greater_or_equal", "80", None, True),
            ("79", "greater_or_equal", "80", None, False),
            ("80", "less_or_equal", "80", None, True),
            ("81", "less_or_equal", "80", None, False),
            ("50", "in_range", "10", "60", True),
            ("70", "in_range", "10", "60", False),
            ("50", "in_range", "10", "", False),
            ("не число", "greater_or_equal", "1", None, False),
            ("5", "unknown_operator", "1", None, False),
        ]
        for actual, operator, expected, expected_to, result in cases:
            with self.subTest(actual=actual, operator=operator, expected=expected):
                self.assertEqual(compare_values(actual, operator, expected, expected_to), result)

    def test_condition_value_reads_key_or_its_camel_case_variant(self):
        context = {"testingResult": 90, "status": "Новый"}

        self.assertEqual(condition_value(context, "status"), "Новый")
        self.assertEqual(condition_value(context, "testing_result"), 90)
        self.assertEqual(condition_value(context, "missing_field"), "")
        self.assertEqual(condition_value(context, ""), "")

    def test_should_delay_only_for_delayed_timing_with_positive_minutes(self):
        before = timezone.now()
        delayed, scheduled_for = should_delay({"settings": DELAYED})

        self.assertTrue(delayed)
        self.assertGreaterEqual(scheduled_for, before + timedelta(minutes=5))

        for settings in (IMMEDIATE, {**DELAYED, "delayMinutes": 0}, "not-a-dict", None):
            with self.subTest(settings=settings):
                self.assertEqual(should_delay({"settings": settings}), (False, None))

    def test_stage_helpers_resolve_stage_ids_and_titles(self):
        config = {"stages": STAGES + ["not-a-dict", {"id": "", "title": "без id"}]}

        self.assertEqual(set(stage_by_id(config)), {"stage-a", "stage-b", "stage-c"})
        self.assertEqual(status_stage_id(config, " Статус Б "), "stage-b")
        self.assertEqual(status_stage_id(config, "Неизвестный"), "")
        self.assertEqual(target_status_for_stage(config, "stage-c"), "Статус В")

    def test_target_status_for_stage_falls_back_to_default_titles(self):
        cases = {
            "application-submitted": "Прислал заявку",
            "application-testing": "Прохождение тестирования",
            "application-chat-link-sent": "Отправлена ссылка на орг. чат",
            "application-joined-chat": "Добавился в орг. чат",
            "application-enrollment-closed": "Набор завершён",
            "application-started": "Приступил к ПШ",
            "unknown-stage": "",
        }
        for stage_id, expected in cases.items():
            with self.subTest(stage_id=stage_id):
                self.assertEqual(target_status_for_stage({"stages": []}, stage_id), expected)

    def test_robot_attachment_ids_accepts_dicts_and_ids_without_duplicates(self):
        robot = {"attachments": [{"id": 3}, "5", 3, {"id": "bad"}, None, 7]}

        self.assertEqual(robot_attachment_ids(robot), [3, 5, 7])
        self.assertEqual(robot_attachment_ids({"attachments": "not-a-list"}), [])
        self.assertEqual(robot_attachment_ids({}), [])

    def test_user_display_name_fallbacks(self):
        user_model = get_user_model()

        self.assertEqual(user_display_name(None), "")
        self.assertEqual(
            user_display_name(user_model(first_name="Иван", last_name="Иванов", email="a@example.test")),
            "Иванов Иван",
        )
        self.assertEqual(user_display_name(user_model(email="only-email@example.test")), "only-email@example.test")


class CRMAutomationConfigNormalizationTests(SimpleTestCase):
    def test_missing_default_items_are_added_without_mutating_input(self):
        config = {"eventId": 5, "stages": [], "triggers": [], "robots": []}

        normalized = normalize_crm_automation_config_dict(config)

        self.assertEqual(config["stages"], [])
        self.assertIn("application-submitted", [stage["id"] for stage in normalized["stages"]])
        self.assertIn("crm-application-created", [trigger["id"] for trigger in normalized["triggers"]])
        self.assertIn("crm-notify-organizer", [robot["id"] for robot in normalized["robots"]])

    def test_non_list_sections_are_replaced_with_defaults(self):
        normalized = normalize_crm_automation_config_dict({"eventId": "x", "stages": "broken"})

        self.assertIsInstance(normalized["stages"], list)
        self.assertTrue(normalized["stages"])
        self.assertTrue(normalized["triggers"])
        self.assertTrue(normalized["robots"])

    def test_existing_items_are_kept_and_not_duplicated(self):
        custom_stage = {"id": "application-submitted", "title": "Своё название"}

        normalized = normalize_crm_automation_config_dict({"eventId": 1, "stages": [custom_stage]})

        submitted = [stage for stage in normalized["stages"] if stage["id"] == "application-submitted"]
        self.assertEqual(submitted, [custom_stage])

    def test_legacy_chat_link_robots_are_moved_to_chat_link_sent_stage(self):
        config = {
            "eventId": 1,
            "robots": [
                {"id": "request-send-chat-link", "stageId": "application-joined-chat", "action": "message.vk"},
                {"id": "custom", "stageId": "application-joined-chat", "action": "chat.link.vk"},
                {"id": "other", "stageId": "application-joined-chat", "action": "message.vk"},
                "not-a-dict",
            ],
        }

        robots = {
            robot["id"]: robot
            for robot in normalize_crm_automation_config_dict(config)["robots"]
            if isinstance(robot, dict)
        }

        self.assertEqual(robots["request-send-chat-link"]["stageId"], "application-chat-link-sent")
        self.assertEqual(robots["custom"]["stageId"], "application-chat-link-sent")
        self.assertEqual(robots["other"]["stageId"], "application-joined-chat")

    def test_planner_invite_robot_is_forced_to_enrollment_closed_stage_and_enabled(self):
        config = {
            "eventId": 1,
            "robots": [{"id": "crm-send-planner-invite", "stageId": "application-submitted", "enabled": False}],
        }

        robot = next(
            robot
            for robot in normalize_crm_automation_config_dict(config)["robots"]
            if robot["id"] == "crm-send-planner-invite"
        )

        self.assertEqual(robot["stageId"], "application-enrollment-closed")
        self.assertTrue(robot["enabled"])

    def test_chat_link_and_enrollment_triggers_are_forced_to_their_stages(self):
        config = {
            "eventId": 1,
            "triggers": [
                {"id": "custom-chat", "eventCode": "notification.chat_link_opened", "stageId": "x", "targetStageId": "x"},
                {"id": "custom-closed", "eventCode": "enrollment.closed", "stageId": "x", "targetStageId": "x"},
                {"id": "custom-other", "eventCode": "application.created", "stageId": "x", "targetStageId": "x"},
                42,
            ],
        }

        triggers = {
            trigger["id"]: trigger
            for trigger in normalize_crm_automation_config_dict(config)["triggers"]
            if isinstance(trigger, dict)
        }

        self.assertEqual(triggers["custom-chat"]["stageId"], "application-joined-chat")
        self.assertEqual(triggers["custom-chat"]["targetStageId"], "application-joined-chat")
        self.assertEqual(triggers["custom-closed"]["stageId"], "application-enrollment-closed")
        self.assertEqual(triggers["custom-closed"]["targetStageId"], "application-enrollment-closed")
        self.assertEqual(triggers["custom-other"]["stageId"], "x")


class CRMAutomationTestBase(TestCase):
    """Общие данные: мероприятие с лидером и организатором, проектант с подтверждённым VK."""

    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(
            username="student-auto@example.test",
            email="student-auto@example.test",
            password="StrongPass123",
            first_name="Иван",
            last_name="Иванов",
        )
        self.leader = user_model.objects.create_user(
            username="leader-auto@example.test",
            email="leader-auto@example.test",
            password="StrongPass123",
            first_name="Лидия",
            last_name="Лидерова",
        )
        self.organizer = user_model.objects.create_user(
            username="organizer-auto@example.test",
            email="organizer-auto@example.test",
            password="StrongPass123",
        )
        self.profile, _ = Profile.objects.update_or_create(
            user=self.student,
            defaults={
                "surname": "Иванов",
                "name": "Иван",
                "email": "student-auto@example.test",
                "course": 3,
                "university": "Тестовый университет",
                "vk": "https://vk.com/id123456",
                "vk_user_id": 123456,
                "vk_confirmed_at": timezone.now(),
            },
        )
        self.event = Event.objects.create(
            name="Автоматизация",
            stage="Набор",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            end_app_date=timezone.now() + timedelta(days=7),
            leader=self.leader,
        )
        self.event.organizers.add(self.organizer)
        self.status_a = get_status("Статус А")
        self.status_b = get_status("Статус Б")
        self.status_c = get_status("Статус В")
        self.application = Application.objects.create(
            user=self.student,
            event=self.event,
            message="Хочу участвовать",
            comment="Комментарий",
            date_sub=timezone.now(),
            date_end=timezone.now() + timedelta(days=7),
            status=self.status_a,
            custom_fields={"github": "student-git", "status": "не должен перезаписать"},
        )

    def make_config(self, *, triggers=None, robots=None, stages=None) -> CRMAutomationConfig:
        return CRMAutomationConfig.objects.create(
            scope=CRMAutomationConfig.SCOPE_CRM,
            event=self.event,
            stages=stages if stages is not None else STAGES,
            triggers=triggers or [],
            robots=robots or [],
        )

    def make_event(self, code="request.status_changed", *, previous_status="", fingerprint="fp") -> CRMAutomationEvent:
        self.application.refresh_from_db()
        return CRMAutomationEvent(
            code=code,
            application=self.application,
            previous_status=previous_status,
            event_id=self.event.id,
            fingerprint=fingerprint,
        )

    def last_log(self, rule_id: str) -> CRMAutomationExecutionLog:
        return CRMAutomationExecutionLog.objects.filter(rule_id=rule_id).latest("id")


class CRMAutomationContextTests(CRMAutomationTestBase):
    def create_test_result(self, *, score, session_id, completed_delta_minutes=0):
        test = Test.objects.create(
            name="Квалификация",
            entry=0,
            event=self.event,
            passing_score=50,
            time_limit=30,
            question_count=10,
            test_type="online",
        )
        session = TestSession.objects.create(
            session_id=session_id,
            application=self.application,
            test=test,
            user=self.student,
            expires_at=timezone.now() + timedelta(hours=1),
            status="completed",
        )
        return TestResult.objects.create(
            score=score,
            max_score=100,
            is_passed=score >= 50,
            completed_at=timezone.now() + timedelta(minutes=completed_delta_minutes),
            started_at=timezone.now() - timedelta(minutes=30),
            application=self.application,
            session=session,
            test=test,
            user=self.student,
            correct_answers=score // 10,
            total_questions=10,
            percentage=score,
            time_spent_seconds=600,
            result_status="passed" if score >= 50 else "failed",
        )

    def test_event_context_contains_application_profile_and_custom_fields(self):
        context = event_context(self.make_event(previous_status="Старый"))

        self.assertEqual(context["applicationId"], self.application.id)
        self.assertEqual(context["eventCode"], "request.status_changed")
        self.assertEqual(context["event"], "Автоматизация")
        self.assertEqual(context["student"], "Иванов Иван")
        self.assertEqual(context["status"], "Статус А")
        self.assertEqual(context["previousStatus"], "Старый")
        self.assertEqual(context["university"], "Тестовый университет")
        self.assertEqual(context["course"], 3)
        self.assertEqual(context["responsible"], "Лидерова Лидия")
        self.assertEqual(context["responsibleId"], self.leader.id)
        self.assertEqual(context["message"], "Хочу участвовать")
        self.assertEqual(context["testScore"], "")
        # Пользовательские поля добавляются, но не перезаписывают системные.
        self.assertEqual(context["github"], "student-git")
        self.assertEqual(context["status"], "Статус А")

    def test_event_context_includes_latest_test_result(self):
        self.create_test_result(score=40, session_id="old-session", completed_delta_minutes=-10)
        self.create_test_result(score=90, session_id="new-session")

        context = event_context(self.make_event())

        self.assertEqual(context["testScore"], 90)
        self.assertEqual(context["testing_result"], 90)
        self.assertEqual(context["maxScore"], 100)
        self.assertEqual(context["testingPercentage"], 90.0)
        self.assertTrue(context["testPassed"])
        self.assertEqual(context["resultStatus"], "passed")

    def test_latest_test_result_prefers_current_session(self):
        current = self.create_test_result(score=40, session_id="current-session", completed_delta_minutes=-10)
        self.create_test_result(score=90, session_id="other-session")
        self.application.test_session_id = "current-session"
        self.application.save(update_fields=["test_session_id"])

        self.assertEqual(latest_test_result(self.application), current)

    def test_latest_test_result_falls_back_when_current_session_has_no_result(self):
        latest = self.create_test_result(score=70, session_id="some-session")
        self.application.test_session_id = "missing-session"
        self.application.save(update_fields=["test_session_id"])

        self.assertEqual(latest_test_result(self.application), latest)

    def test_application_display_name_falls_back_to_email(self):
        self.student.first_name = ""
        self.student.last_name = ""
        self.student.save(update_fields=["first_name", "last_name"])
        self.application.refresh_from_db()

        self.assertEqual(application_display_name(self.application), "student-auto@example.test")

    def test_render_template_replaces_known_placeholders_only(self):
        rendered = render_template("{student}: {event} / {unknown}", self.make_event())

        self.assertEqual(rendered, "Иванов Иван: Автоматизация / {unknown}")
        self.assertEqual(render_template(None, self.make_event()), "")

    def test_conditions_match_modes(self):
        event = self.make_event()
        match = {"field": "status", "operator": "equals", "value": "Статус А"}
        mismatch = {"field": "status", "value": "Статус Б"}  # оператор по умолчанию — equals

        cases = [
            (None, True),
            ({"condition": {"rules": []}}, True),
            ({"condition": {"rules": "broken"}}, True),
            ({"condition": {"rules": ["not-a-dict"]}}, True),
            ({"condition": {"mode": "all", "rules": [match]}}, True),
            ({"condition": {"mode": "all", "rules": [match, mismatch]}}, False),
            ({"condition": {"mode": "any", "rules": [match, mismatch]}}, True),
            ({"condition": {"mode": "any", "rules": [mismatch]}}, False),
        ]
        for settings, expected in cases:
            with self.subTest(settings=settings):
                self.assertEqual(conditions_match(settings, event), expected)


class CRMAutomationModelHelperTests(CRMAutomationTestBase):
    def test_config_model_to_dict_returns_defaults_for_empty_config(self):
        config_model = CRMAutomationConfig.objects.create(event=self.event)

        config = config_model_to_dict(config_model)

        self.assertEqual(config["scope"], "crm")
        self.assertEqual(config["eventId"], self.event.id)
        self.assertIn("application-submitted", [stage["id"] for stage in config["stages"]])

    def test_config_model_to_dict_normalizes_saved_config(self):
        config_model = self.make_config(robots=[make_robot("own", "notification.user")])

        config = config_model_to_dict(config_model)

        self.assertEqual(config["eventId"], self.event.id)
        self.assertEqual(config["updatedAt"], config_model.updated_at.isoformat())
        self.assertEqual(config["stages"][:3], STAGES)
        robot_ids = [robot["id"] for robot in config["robots"]]
        self.assertIn("own", robot_ids)
        self.assertIn("crm-notify-organizer", robot_ids)

    def test_get_or_create_config_creates_default_config_once(self):
        first = get_or_create_config(self.event.id)
        second = get_or_create_config(self.event.id)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.scope, CRMAutomationConfig.SCOPE_CRM)
        self.assertTrue(first.stages)
        self.assertTrue(first.triggers)
        self.assertTrue(first.robots)

    def test_get_application_organizers_includes_leader_once(self):
        self.event.organizers.add(self.leader)

        organizers = get_application_organizers(self.application)

        self.assertCountEqual([user.id for user in organizers], [self.organizer.id, self.leader.id])

    def test_get_application_organizers_without_event_is_empty(self):
        self.application.event = None
        self.application.save(update_fields=["event"])

        self.assertEqual(get_application_organizers(self.application), [])

    def test_create_notification_requires_user(self):
        self.assertFalse(create_notification(None, "Тема", "Текст"))
        self.assertTrue(create_notification(self.student.id, "Т" * 300, "Текст", link="/custom"))

        notification = Notification.objects.get(user=self.student)
        self.assertEqual(len(notification.title), 255)
        self.assertEqual(notification.link, "/custom")

    def test_create_organizer_notifications_counts_recipients(self):
        created = create_organizer_notifications(self.application, "Тема", "Текст")

        self.assertEqual(created, 2)
        self.assertEqual(
            set(Notification.objects.values_list("user_id", flat=True)),
            {self.leader.id, self.organizer.id},
        )

    def test_update_application_status(self):
        self.assertFalse(update_application_status(self.application, ""))
        self.assertFalse(update_application_status(self.application, "Статус А"))
        self.assertTrue(update_application_status(self.application, "Совсем новый статус"))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Совсем новый статус")

    def test_get_robot_attachments_filters_by_event_and_keeps_order(self):
        other_event = Event.objects.create(
            name="Другое",
            stage="Набор",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now(),
        )
        first = CRMAutomationAttachment.objects.create(event=self.event, file_name="a.pdf", content=b"a")
        second = CRMAutomationAttachment.objects.create(event=self.event, file_name="b.pdf", content=b"b")
        foreign = CRMAutomationAttachment.objects.create(event=other_event, file_name="c.pdf", content=b"c")

        attachments = get_robot_attachments({"attachments": [second.id, foreign.id, first.id]}, self.event.id)

        self.assertEqual([item.id for item in attachments], [second.id, first.id])
        self.assertEqual(get_robot_attachments({}, self.event.id), [])


class CRMRobotActionTests(CRMAutomationTestBase):
    def run_robot(self, robot, **kwargs):
        config_model = self.make_config(robots=[robot])
        return run_robot_action(config_model, robot, self.make_event(), **kwargs)

    def test_organizer_notification_robot(self):
        self.assertTrue(self.run_robot(make_robot("notify-org", "notification.organizer")))

        notification = Notification.objects.get(user=self.organizer)
        self.assertEqual(notification.title, "Тема для Иванов Иван")
        self.assertEqual(notification.message, "Сообщение по «Автоматизация»")
        log = self.last_log("notify-org")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(log.message, "Уведомления отправлены организаторам.")
        self.assertEqual(log.entity_id, str(self.application.id))

    def test_organizer_notification_robot_without_organizers_is_skipped(self):
        self.event.leader = None
        self.event.save(update_fields=["leader"])
        self.event.organizers.clear()

        self.assertFalse(self.run_robot(make_robot("notify-curator", "notification.curator")))

        log = self.last_log("notify-curator")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Организаторы не найдены.")

    def test_user_notification_robot_links_to_requests(self):
        self.assertTrue(self.run_robot(make_robot("notify-user", "notification.user")))

        notification = Notification.objects.get(user=self.student)
        self.assertEqual(notification.link, "/requests")
        self.assertEqual(self.last_log("notify-user").message, "Уведомление отправлено проектанту.")

    def test_testing_link_robot_links_to_testing_page(self):
        self.assertTrue(self.run_robot(make_robot("testing", "testing.link")))

        notification = Notification.objects.get(user=self.student)
        self.assertEqual(notification.link, f"/testing?applicationId={self.application.id}")

    def test_robot_without_subject_uses_default_title(self):
        self.run_robot(make_robot("no-subject", "notification.user", subject="", title=""))

        self.assertEqual(Notification.objects.get(user=self.student).title, "Уведомление")

    def test_unknown_action_is_skipped(self):
        self.assertFalse(self.run_robot(make_robot("unknown", "something.new")))

        log = self.last_log("unknown")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Действие робота something.new пока не поддерживается.")

    def test_status_change_robot_uses_explicit_target_status(self):
        robot = make_robot("move", "status.change", targetStatus="Статус В")

        self.assertTrue(self.run_robot(robot))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_c.id)
        self.assertEqual(self.last_log("move").message, "Заявка переведена в статус «Статус В».")

    def test_status_change_robot_resolves_target_stage(self):
        robot = make_robot("move-stage", "status.change", targetStageId="stage-b")

        self.assertTrue(self.run_robot(robot))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_b.id)

    def test_status_change_robot_without_change_is_skipped(self):
        robot = make_robot("same", "status.change", targetStatus="Статус А")

        self.assertFalse(self.run_robot(robot))

        log = self.last_log("same")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Статус заявки не изменился.")

    def test_delayed_robot_creates_pending_log_and_does_not_run(self):
        robot = make_robot("delayed", "notification.user", settings=dict(DELAYED))
        config_model = self.make_config(robots=[robot])
        event = self.make_event()

        self.assertFalse(run_robot_action(config_model, robot, event))
        # Повторный вызов для того же события не создаёт второй лог.
        self.assertFalse(run_robot_action(config_model, robot, event))

        log = CRMAutomationExecutionLog.objects.get(rule_id="delayed")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_PENDING)
        self.assertIsNotNone(log.scheduled_for)
        self.assertIsNone(log.executed_at)
        self.assertFalse(Notification.objects.filter(user=self.student).exists())

    def test_force_immediate_runs_without_writing_log(self):
        robot = make_robot("forced", "notification.user", settings=dict(DELAYED))

        self.assertTrue(self.run_robot(robot, force_immediate=True))

        self.assertTrue(Notification.objects.filter(user=self.student).exists())
        self.assertFalse(CRMAutomationExecutionLog.objects.filter(rule_id="forced").exists())

    def test_file_robot_without_selected_files_is_skipped(self):
        self.assertFalse(self.run_robot(make_robot("files", "file.vk", attachments=[])))

        self.assertEqual(self.last_log("files").message, "Файлы для VK-робота не выбраны.")

    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=11)
    @patch("integrations.vk.crm_notifications.upload_vk_document", return_value="doc123456_1")
    def test_file_robot_uploads_documents_and_sends_message(self, upload_mock, send_mock):
        attachment = CRMAutomationAttachment.objects.create(event=self.event, file_name="plan.pdf", content=b"pdf")

        self.assertTrue(self.run_robot(make_robot("files", "file.vk", attachments=[{"id": attachment.id}])))

        upload_mock.assert_called_once_with(peer_id=123456, file_name="plan.pdf", content=b"pdf")
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.kwargs["peer_id"], 123456)
        self.assertEqual(send_mock.call_args.kwargs["attachments"], ["doc123456_1"])
        self.assertEqual(send_mock.call_args.kwargs["message"], "Сообщение по «Автоматизация»")
        self.assertEqual(self.last_log("files").message, "VK-файлы отправлены проектанту.")

    def test_file_robot_with_disabled_vk_logs_error(self):
        attachment = CRMAutomationAttachment.objects.create(event=self.event, file_name="plan.pdf", content=b"pdf")

        self.assertFalse(self.run_robot(make_robot("files", "file.vk", attachments=[attachment.id])))

        log = self.last_log("files")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "VK integration is disabled.")

    @patch("integrations.vk.planner_invites.send_vk_message", return_value=5)
    def test_planner_invite_robot_sends_vk_invite(self, send_mock):
        self.assertTrue(self.run_robot(make_robot("invite", "planner.invite.vk")))

        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.kwargs["user_id"], 123456)
        self.assertEqual(send_mock.call_args.kwargs["message"], "Сообщение по «Автоматизация»")
        self.assertIn("buttons", send_mock.call_args.kwargs["keyboard"])
        self.assertEqual(self.last_log("invite").message, "VK-приглашение в планировщик отправлено проектанту.")

    def test_planner_invite_robot_without_confirmed_vk_logs_error(self):
        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])

        self.assertFalse(self.run_robot(make_robot("invite", "planner.invite.vk")))

        self.assertEqual(
            self.last_log("invite").message,
            "проектант не подтвердил VK-бота или указал некорректный VK",
        )

    @patch("integrations.vk.planner_invites.send_vk_message", return_value=6)
    def test_planner_start_robot_sends_vk_message(self, send_mock):
        self.assertTrue(self.run_robot(make_robot("start", "planner.start.vk")))

        send_mock.assert_called_once()
        self.assertEqual(self.last_log("start").message, "VK-Сообщение Старта")

    def test_planner_start_robot_with_disabled_vk_logs_error(self):
        self.assertFalse(self.run_robot(make_robot("start", "planner.start.vk")))

        self.assertEqual(self.last_log("start").message, "VK integration is disabled.")

    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=7)
    def test_vk_message_robot_sends_rendered_message(self, send_mock):
        robot = make_robot("vk", "message.vk_interactive", message="Привет, {student}")

        self.assertTrue(self.run_robot(robot))

        send_mock.assert_called_once_with(user_id=123456, message="Привет, Иванов Иван", keyboard=None, attachments=None)
        self.assertEqual(self.last_log("vk").message, "VK-сообщение отправлено проектанту.")

    @override_settings(VK_CHAT_LINK_BASE_URL="")
    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=8)
    def test_vk_message_robot_injects_chat_link_into_placeholder(self, send_mock):
        robot = make_robot("vk-link", "message.vk", message="Ссылка: {chat_link}")

        self.assertTrue(self.run_robot(robot))

        sent_message = send_mock.call_args.kwargs["message"]
        self.assertTrue(sent_message.startswith("Ссылка: /api/integrations/vk/chat-links/"))
        self.assertNotIn("{chat_link}", sent_message)

    @override_settings(VK_CHAT_LINK_BASE_URL="https://crm.example.test")
    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=9)
    def test_vk_or_notification_robot_appends_chat_link(self, send_mock):
        robot = make_robot("vk-or-note", "message.vk_or_notification", message="Добро пожаловать")

        self.assertTrue(self.run_robot(robot))

        sent_message = send_mock.call_args.kwargs["message"]
        self.assertTrue(sent_message.startswith("Добро пожаловать\n\nСсылка на орг.чат: https://crm.example.test/api/"))

    @override_settings(VK_ORG_CHAT_URL="", VK_ORG_CHAT_PEER_ID=0)
    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=10)
    def test_chat_link_robot_sends_link_when_chat_peer_is_unknown(self, send_mock):
        robot = make_robot("chat-link", "chat.link.vk", message="Вступайте: {chat_link}")

        self.assertTrue(self.run_robot(robot))

        self.assertIn("/api/integrations/vk/chat-links/", send_mock.call_args.kwargs["message"])

    def test_vk_message_robot_with_disabled_vk_logs_error(self):
        self.assertFalse(self.run_robot(make_robot("vk", "message.vk")))

        log = self.last_log("vk")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "VK integration is disabled.")

    def test_vk_message_robot_without_vk_profile_logs_error(self):
        self.profile.vk = ""
        self.profile.vk_user_id = None
        self.profile.save(update_fields=["vk", "vk_user_id"])

        self.assertFalse(self.run_robot(make_robot("vk", "message.vk")))

        self.assertEqual(self.last_log("vk").message, "у проектанта не указан корректный VK")


class CRMStageRobotsAndTriggerTests(CRMAutomationTestBase):
    def test_run_stage_robots_filters_disabled_deleted_and_other_stages(self):
        robots = [
            make_robot("enabled", "notification.user"),
            make_robot("disabled", "notification.user", enabled=False),
            make_robot("deleted", "notification.user", deleted=True),
            make_robot("other-stage", "notification.user", stage_id="stage-b"),
            "not-a-dict",
        ]
        config_model = self.make_config(robots=robots[:4])

        changed = run_stage_robots(config_model, {"robots": robots}, self.make_event(), "stage-a")

        self.assertTrue(changed)
        self.assertEqual(list(CRMAutomationExecutionLog.objects.values_list("rule_id", flat=True)), ["enabled"])

    def test_run_stage_robots_logs_skipped_when_conditions_fail(self):
        settings = {**IMMEDIATE, "condition": {"mode": "all", "rules": [{"field": "status", "value": "Другой"}]}}
        robot = make_robot("conditional", "notification.user", settings=settings)
        config_model = self.make_config(robots=[robot])

        changed = run_stage_robots(config_model, {"robots": [robot]}, self.make_event(), "stage-a")

        self.assertFalse(changed)
        log = self.last_log("conditional")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Условия робота не выполнены.")
        self.assertFalse(Notification.objects.exists())

    def run_single_trigger(self, trigger, *, code="custom.event"):
        config_model = self.make_config(triggers=[trigger])
        config = config_model_to_dict(config_model)
        return run_trigger(config_model, config, trigger, self.make_event(code))

    def test_trigger_moves_application_to_target_stage(self):
        stage_id = self.run_single_trigger(make_trigger("forward", "custom.event", stage_id="stage-b"))

        self.assertEqual(stage_id, "stage-b")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_b.id)
        log = self.last_log("forward")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(log.message, "Триггер перевел заявку на стадию «Статус Б».")

    def test_trigger_without_status_change_still_returns_stage(self):
        stage_id = self.run_single_trigger(make_trigger("same", "custom.event", stage_id="stage-a"))

        self.assertEqual(stage_id, "stage-a")
        self.assertEqual(self.last_log("same").message, "Триггер обработан без изменения статуса.")

    def test_trigger_is_not_repeated_for_same_event(self):
        trigger = make_trigger("once", "custom.event", stage_id="stage-b")
        config_model = self.make_config(triggers=[trigger])
        config = config_model_to_dict(config_model)
        event = self.make_event("custom.event")

        self.assertEqual(run_trigger(config_model, config, trigger, event), "stage-b")
        self.assertEqual(run_trigger(config_model, config, trigger, event), "")

    def test_trigger_with_failed_conditions_is_skipped(self):
        settings = {**IMMEDIATE, "condition": {"mode": "all", "rules": [{"field": "status", "value": "Другой"}]}}

        stage_id = self.run_single_trigger(make_trigger("cond", "custom.event", stage_id="stage-b", settings=settings))

        self.assertEqual(stage_id, "")
        self.assertEqual(self.last_log("cond").message, "Условия триггера не выполнены.")

    def test_status_changed_trigger_skips_application_on_other_stage(self):
        stage_id = self.run_single_trigger(
            make_trigger("status-trigger", "request.status_changed", stage_id="stage-b"),
            code="request.status_changed",
        )

        self.assertEqual(stage_id, "")
        self.assertEqual(
            self.last_log("status-trigger").message,
            "Триггер смены статуса пропущен: заявка находится не на стадии этого триггера.",
        )

    def test_back_transition_is_blocked_by_default(self):
        self.application.status = self.status_c
        self.application.save(update_fields=["status"])

        stage_id = self.run_single_trigger(make_trigger("back", "custom.event", stage_id="stage-a"))

        self.assertEqual(stage_id, "")
        self.assertEqual(self.last_log("back").message, "Переход на предыдущую стадию запрещен настройкой триггера.")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_c.id)

    def test_back_transition_is_allowed_by_setting(self):
        self.application.status = self.status_c
        self.application.save(update_fields=["status"])

        stage_id = self.run_single_trigger(
            make_trigger("back-allowed", "custom.event", stage_id="stage-a", allowBackTransition=True)
        )

        self.assertEqual(stage_id, "stage-a")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_a.id)

    def test_delayed_trigger_creates_pending_log(self):
        stage_id = self.run_single_trigger(
            make_trigger("delayed-trigger", "custom.event", stage_id="stage-b", settings=dict(DELAYED))
        )

        self.assertEqual(stage_id, "")
        log = self.last_log("delayed-trigger")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_PENDING)
        self.assertEqual(log.message, "Запланировано отложенное выполнение триггера.")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_a.id)


class CRMRunAutomationTests(CRMAutomationTestBase):
    def test_application_without_event_is_ignored(self):
        self.application.event = None
        self.application.save(update_fields=["event"])

        self.assertEqual(run_crm_automation(self.application, "application.created"), {"events": 0, "changed": 0})
        self.assertFalse(CRMAutomationConfig.objects.exists())

    def test_only_enabled_triggers_with_matching_event_code_run(self):
        self.make_config(
            triggers=[
                make_trigger("match", "custom.event", stage_id="stage-b"),
                make_trigger("disabled", "custom.event", stage_id="stage-c", enabled=False),
                make_trigger("deleted", "custom.event", stage_id="stage-c", deleted=True),
                make_trigger("other-code", "other.event", stage_id="stage-c"),
            ],
            robots=[make_robot("on-b", "notification.user", stage_id="stage-b")],
        )

        result = run_crm_automation(self.application, "custom.event")

        self.assertEqual(result["events"], 1)
        self.assertEqual(result["changed"], 2)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_b.id)
        trigger_ids = set(
            CRMAutomationExecutionLog.objects.filter(rule_kind="trigger").values_list("rule_id", flat=True)
        )
        self.assertEqual(trigger_ids, {"match"})
        self.assertTrue(Notification.objects.filter(user=self.student).exists())

    def test_run_due_crm_automation_processes_only_due_pending_logs(self):
        robot = make_robot("due", "notification.user", settings=dict(DELAYED))
        future_robot = make_robot("future", "notification.user", settings=dict(DELAYED))
        config_model = self.make_config(robots=[robot, future_robot])
        run_robot_action(config_model, robot, self.make_event(fingerprint="due"))
        run_robot_action(config_model, future_robot, self.make_event(fingerprint="future"))
        CRMAutomationExecutionLog.objects.filter(rule_id="due").update(
            scheduled_for=timezone.now() - timedelta(minutes=1)
        )

        result = run_due_crm_automation()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["chat_membership_scanned"], 0)
        self.assertEqual(result["chat_membership_changed"], 0)
        self.assertEqual(self.last_log("due").status, CRMAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(self.last_log("future").status, CRMAutomationExecutionLog.STATUS_PENDING)


class CRMPendingLogExecutionTests(CRMAutomationTestBase):
    def make_pending_log(self, config_model, *, rule_id, rule_kind="robot", event_code="custom.event", application=None):
        return CRMAutomationExecutionLog.objects.create(
            config=config_model,
            application=application if application is not None else self.application,
            event_id=self.event.id,
            entity_id=str(self.application.id),
            event_code=event_code,
            rule_kind=rule_kind,
            rule_id=rule_id,
            run_key=f"pending-{rule_id}-{rule_kind}",
            status=CRMAutomationExecutionLog.STATUS_PENDING,
            context={"previousStatus": "Старый"},
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )

    def test_missing_application_skips_log(self):
        config_model = self.make_config()
        log = CRMAutomationExecutionLog.objects.create(
            config=config_model,
            application=None,
            event_id=self.event.id,
            entity_id="0",
            event_code="custom.event",
            rule_kind="robot",
            rule_id="any",
            run_key="pending-no-application",
            status=CRMAutomationExecutionLog.STATUS_PENDING,
        )

        self.assertFalse(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Заявка для отложенного правила не найдена.")
        self.assertIsNotNone(log.executed_at)

    def test_missing_rule_fails_log(self):
        log = self.make_pending_log(self.make_config(), rule_id="removed-rule")

        self.assertFalse(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_FAILED)
        self.assertEqual(log.message, "Правило для отложенного выполнения не найдено.")

    def test_conditions_no_longer_matching_skip_log(self):
        settings = {**DELAYED, "condition": {"mode": "all", "rules": [{"field": "status", "value": "Другой"}]}}
        config_model = self.make_config(robots=[make_robot("cond", "notification.user", settings=settings)])
        log = self.make_pending_log(config_model, rule_id="cond")

        self.assertFalse(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Условия отложенного правила больше не выполнены.")

    def test_pending_robot_runs_immediately(self):
        config_model = self.make_config(robots=[make_robot("later", "notification.user", settings=dict(DELAYED))])
        log = self.make_pending_log(config_model, rule_id="later")

        self.assertTrue(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SUCCESS)
        self.assertEqual(log.message, "Отложенное правило выполнено.")
        self.assertTrue(Notification.objects.filter(user=self.student).exists())

    def test_pending_robot_without_effect_is_skipped(self):
        config_model = self.make_config(robots=[make_robot("noop", "unsupported.action", settings=dict(DELAYED))])
        log = self.make_pending_log(config_model, rule_id="noop")

        self.assertFalse(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(log.message, "Отложенное правило не внесло изменений.")

    def test_pending_trigger_changes_status_and_runs_stage_robots(self):
        config_model = self.make_config(
            triggers=[make_trigger("later-trigger", "custom.event", stage_id="stage-b", settings=dict(DELAYED))],
            robots=[make_robot("on-b", "notification.user", stage_id="stage-b")],
        )
        log = self.make_pending_log(config_model, rule_id="later-trigger", rule_kind="trigger")

        self.assertTrue(execute_pending_log(log))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, self.status_b.id)
        self.assertTrue(Notification.objects.filter(user=self.student).exists())
        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SUCCESS)

    def test_pending_status_trigger_is_skipped_when_application_left_stage(self):
        config_model = self.make_config(
            triggers=[make_trigger("status-later", "request.status_changed", stage_id="stage-b", settings=dict(DELAYED))],
        )
        log = self.make_pending_log(
            config_model,
            rule_id="status-later",
            rule_kind="trigger",
            event_code="request.status_changed",
        )

        self.assertFalse(execute_pending_log(log))

        log.refresh_from_db()
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_SKIPPED)
        self.assertEqual(
            log.message,
            "Отложенный триггер смены статуса пропущен: заявка находится не на стадии этого триггера.",
        )
