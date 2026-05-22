from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import (
    Application,
    CRMRole,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    Direction,
    Event,
    Notification,
    Project,
    ROLE_CURATOR,
    ROLE_PROJECTANT,
    Specialization,
    Status,
)
from users.automation_engine import run_crm_automation, run_due_crm_automation


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CRMContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.password = "StrongPass123"

        self.projectant = self.user_model.objects.create_user(
            email="projectant-contract@example.com",
            username="projectant-contract@example.com",
            password=self.password,
            first_name="Project",
            last_name="Student",
            is_active=True,
        )
        self.curator = self.user_model.objects.create_user(
            email="curator-contract@example.com",
            username="curator-contract@example.com",
            password=self.password,
            first_name="Curator",
            last_name="Owner",
            is_active=True,
        )

        event_content_type = ContentType.objects.get_for_model(Event)
        CRMRole.objects.create(
            user=self.projectant,
            role_type=ROLE_PROJECTANT,
            content_type=event_content_type,
            object_id=0,
        )
        CRMRole.objects.create(
            user=self.curator,
            role_type=ROLE_CURATOR,
            content_type=event_content_type,
            object_id=0,
        )

        self.event = Event.objects.create(
            name="Contract Event",
            description="Event for CRM contract tests",
            stage="open",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            end_app_date=timezone.now() + timedelta(days=7),
            leader=self.curator,
        )
        self.direction = Direction.objects.create(
            name="Backend",
            description="Direction",
            event=self.event,
            leader=self.curator,
        )
        self.project = Project.objects.create(
            name="CRM API",
            description="Project",
            direction=self.direction,
            curator=self.curator,
        )

    def test_public_can_read_events_directions_and_projects(self):
        events_response = self.client.get(reverse("event-list-create"))
        directions_response = self.client.get(
            reverse("direction-list-create", kwargs={"event_id": self.event.id})
        )
        projects_response = self.client.get(reverse("user-project-list-create"))

        self.assertEqual(events_response.status_code, status.HTTP_200_OK)
        self.assertEqual(directions_response.status_code, status.HTTP_200_OK)
        self.assertEqual(projects_response.status_code, status.HTTP_200_OK)

    def test_public_can_read_specializations(self):
        response = self.client.get(reverse("specialization-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["title"] == "Frontend разработчик" for item in response.data))

    def test_curator_can_create_event_with_leader_and_specializations(self):
        specialization, _ = Specialization.objects.get_or_create(
            name="Frontend разработчик",
            defaults={"description": ""},
        )
        self.client.force_authenticate(user=self.curator)

        response = self.client.post(
            reverse("event-list-create"),
            {
                "name": "Практика 2026",
                "description": "Новое мероприятие",
                "stage": "-",
                "start_date": str(timezone.now().date()),
                "end_date": str(timezone.now().date() + timedelta(days=60)),
                "end_app_date": (timezone.now() + timedelta(days=14)).isoformat(),
                "leader": self.curator.id,
                "specialization": specialization.id,
                "specializations": [specialization.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        created_event = Event.objects.get(pk=response.data["id"])
        self.assertEqual(created_event.leader_id, self.curator.id)
        self.assertEqual(created_event.specialization_id, specialization.id)
        self.assertEqual(
            list(
                created_event.event_specializations.values_list(
                    "specialization_id", flat=True
                )
            ),
            [specialization.id],
        )

    def test_projectant_can_create_application_for_event_only(self):
        self.client.force_authenticate(user=self.projectant)

        response = self.client.post(
            reverse("application-list"),
            {"event_id": self.event.id, "message": "Ready to join"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get(pk=response.data["id"])
        self.assertEqual(application.event_id, self.event.id)
        self.assertIsNone(application.direction_id)
        self.assertEqual(application.user_id, self.projectant.id)
        self.assertIsNotNone(application.status_id)
        self.assertEqual(response.data["studentName"], "Student Project")
        self.assertEqual(response.data["status"], "Прислал заявку")

    def test_curator_can_list_all_applications(self):
        Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=None,
            project=None,
            message="Own application",
            is_link=False,
            is_approved=False,
            comment="",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
        )
        self.client.force_authenticate(user=self.curator)

        response = self.client.get(reverse("application-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["studentName"], "Student Project")

    def test_application_creation_creates_notification_for_event_leader(self):
        self.client.force_authenticate(user=self.projectant)

        response = self.client.post(
            reverse("application-list"),
            {"event_id": self.event.id, "message": "Ready to join"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = Notification.objects.get(user=self.curator)
        self.assertEqual(notification.title, "Новая заявка: Student Project")
        self.assertIn("Student Project", notification.message)
        self.assertIn("Contract Event", notification.message)
        self.assertEqual(notification.link, "/requests")

    def test_user_can_read_and_mark_notifications(self):
        notification = Notification.objects.create(
            user=self.projectant,
            title="Переход к тесту",
            message="Откройте ссылку и продолжите.",
            link="/requests",
        )
        self.client.force_authenticate(user=self.projectant)

        list_response = self.client.get(reverse("notification-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["title"], "Переход к тесту")

        patch_response = self.client.patch(
            reverse("notification-detail", kwargs={"notification_id": notification.id}),
            {"read": True},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.read)

        mark_all_response = self.client.post(reverse("notification-mark-all-read"))
        self.assertEqual(mark_all_response.status_code, status.HTTP_200_OK)

    def test_curator_can_manage_crm_automation_config(self):
        self.client.force_authenticate(user=self.curator)

        response = self.client.get(reverse("crm-automation-config", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "crm")
        self.assertEqual(response.data["eventId"], self.event.id)
        self.assertTrue(response.data["stages"])
        self.assertTrue(response.data["triggers"])
        self.assertTrue(response.data["robots"])

    def test_crm_delayed_robot_runs_from_backend_queue(self):
        submitted_status = Status.objects.get_or_create(name="Прислал заявку")[0]
        testing_status = Status.objects.get_or_create(name="Прохождение тестирования")[0]
        application = Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=self.direction,
            message="Ready",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
            status=submitted_status,
        )
        config = CRMAutomationConfig.objects.create(
            scope="crm",
            event=self.event,
            stages=[
                {"id": "application-submitted", "title": "Прислал заявку", "description": ""},
                {"id": "application-testing", "title": "Прохождение тестирования", "description": ""},
            ],
            triggers=[],
            robots=[
                {
                    "id": "delayed-test-notification",
                    "stageId": "application-testing",
                    "title": "Отложенное уведомление",
                    "description": "",
                    "action": "notification.user",
                    "enabled": True,
                    "settings": {
                        "runMode": "queue",
                        "timing": "delayed",
                        "delayMinutes": 1,
                        "condition": {"mode": "all", "rules": []},
                    },
                    "subject": "Тестирование",
                    "message": "Откройте тестирование.",
                }
            ],
        )
        self.client.force_authenticate(user=self.curator)

        response = self.client.patch(
            reverse("application-detail", kwargs={"application_id": application.id}),
            {"status": testing_status.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = CRMAutomationExecutionLog.objects.get(config=config, rule_id="delayed-test-notification")
        self.assertEqual(log.status, CRMAutomationExecutionLog.STATUS_PENDING)
        self.assertFalse(Notification.objects.filter(user=self.projectant, title="Тестирование").exists())

        log.scheduled_for = timezone.now() - timedelta(minutes=1)
        log.save(update_fields=["scheduled_for"])
        result = run_due_crm_automation()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["changed"], 1)
        self.assertTrue(Notification.objects.filter(user=self.projectant, title="Тестирование").exists())

    def test_crm_robot_can_change_application_status(self):
        submitted_status = Status.objects.get_or_create(name="Прислал заявку")[0]
        failed_status = Status.objects.get_or_create(name="Не прошел тестирование")[0]
        application = Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=self.direction,
            message="Ready",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
            status=submitted_status,
        )
        CRMAutomationConfig.objects.create(
            scope="crm",
            event=self.event,
            stages=[
                {"id": "application-submitted", "title": submitted_status.name, "description": ""},
            ],
            triggers=[],
            robots=[
                {
                    "id": "move-to-failed-testing",
                    "stageId": "application-submitted",
                    "targetStatus": failed_status.name,
                    "title": "Перевести заявку",
                    "description": "",
                    "action": "status.change",
                    "enabled": True,
                    "settings": {
                        "runMode": "queue",
                        "timing": "immediate",
                        "delayMinutes": 0,
                        "condition": {"mode": "all", "rules": []},
                    },
                    "subject": "",
                    "message": "",
                }
            ],
        )

        result = run_crm_automation(application, "application.created")

        self.assertEqual(result["changed"], 1)
        application.refresh_from_db()
        self.assertEqual(application.status.name, failed_status.name)

    def test_crm_chat_link_opened_trigger_does_not_revert_joined_status_from_legacy_config(self):
        sent_status = Status.objects.get_or_create(name="Отправлена ссылка на орг. чат")[0]
        joined_status = Status.objects.get_or_create(name="Добавился в орг. чат")[0]
        application = Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=self.direction,
            message="Ready",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
            status=joined_status,
        )
        CRMAutomationConfig.objects.create(
            scope="crm",
            event=self.event,
            stages=[
                {"id": "application-chat-link-sent", "title": sent_status.name, "description": ""},
                {"id": "application-joined-chat", "title": joined_status.name, "description": ""},
            ],
            triggers=[
                {
                    "id": "crm-chat-link-opened",
                    "stageId": "application-chat-link-sent",
                    "title": "Legacy chat link trigger",
                    "description": "",
                    "eventCode": "notification.chat_link_opened",
                    "enabled": True,
                    "settings": {
                        "runMode": "queue",
                        "timing": "immediate",
                        "delayMinutes": 0,
                        "condition": {"mode": "all", "rules": []},
                    },
                    "targetStageId": "application-chat-link-sent",
                    "allowBackTransition": False,
                }
            ],
            robots=[],
        )

        run_crm_automation(application, "notification.chat_link_opened", previous_status=sent_status.name)

        application.refresh_from_db()
        self.assertEqual(application.status.name, joined_status.name)

    def test_curator_can_create_notification_for_projectant(self):
        self.client.force_authenticate(user=self.curator)

        response = self.client.post(
            reverse("notification-list"),
            {
                "userId": self.projectant.id,
                "title": "Системное уведомление",
                "message": "Проверьте следующий шаг.",
                "link": "/requests",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = Notification.objects.get(user=self.projectant, title="Системное уведомление")
        self.assertEqual(notification.message, "Проверьте следующий шаг.")

    def test_projectant_cannot_create_notification_for_other_user(self):
        self.client.force_authenticate(user=self.projectant)

        response = self.client.post(
            reverse("notification-list"),
            {
                "userId": self.curator.id,
                "title": "Недоступно",
                "message": "Нет прав.",
                "link": "/requests",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Notification.objects.filter(user=self.curator, title="Недоступно").exists())

    def test_projectant_can_delete_own_application(self):
        application = Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=None,
            project=None,
            message="Own application",
            is_link=False,
            is_approved=False,
            comment="",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
        )
        self.client.force_authenticate(user=self.projectant)

        response = self.client.delete(
            reverse("application-detail", kwargs={"application_id": application.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Application.objects.filter(pk=application.id).exists())

    def test_projectant_can_update_own_application_status(self):
        self.client.force_authenticate(user=self.projectant)
        create_response = self.client.post(
            reverse("application-list"),
            {"event_id": self.event.id, "message": "Ready to join"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        patch_response = self.client.patch(
            reverse("application-detail", kwargs={"application_id": create_response.data["id"]}),
            {"status": "Прохождение тестирования"},
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK, patch_response.data)
        self.assertEqual(patch_response.data["status"], "Прохождение тестирования")
