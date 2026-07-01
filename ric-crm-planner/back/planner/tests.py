from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, PlannerWorkspaceState, TeamPlannerDesk
from django.utils import timezone

from users.models import Application, CRMRole, Event, Notification, Profile, ROLE_CURATOR, Specialization


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PlannerDeskViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="planner@example.com",
            username="planner@example.com",
            password="StrongPass123",
            is_active=True,
        )

    def authenticate(self):
        self.client.force_authenticate(user=self.user)

    def test_team_desk_get_creates_default_desk(self):
        self.authenticate()
        response = self.client.get(
            reverse("planner-team-desk-detail", kwargs={"team_id": 17})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["team_id"], 17)
        self.assertEqual(response.data["parent_tasks"], [])
        self.assertEqual(response.data["subtasks"], [])
        self.assertEqual(response.data["columns"], ["Запланировано", "В работе", "На проверке", "Готово"])
        self.assertTrue(TeamPlannerDesk.objects.filter(team_id=17).exists())

    def test_team_desk_put_updates_existing_desk(self):
        self.authenticate()
        payload = {
            "team_name": "Backend Team",
            "curator_id": 21,
            "member_ids": [11, 12],
            "parent_tasks": [
                {
                    "id": 1,
                    "team_id": 17,
                    "title": "Sprint 1",
                    "start_date": "2026-03-25",
                    "end_date": "2026-04-01",
                }
            ],
            "subtasks": [
                {
                    "id": 2,
                    "team_id": 17,
                    "parent_task_id": 1,
                    "title": "API endpoint",
                    "role": "Backend",
                    "start_date": "2026-03-25",
                    "end_date": "2026-03-28",
                    "in_sprint": True,
                    "status": "В работе",
                }
            ],
            "columns": ["Backlog", "In progress", "Done"],
        }
        response = self.client.put(
            reverse("planner-team-desk-detail", kwargs={"team_id": 17}),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        desk = TeamPlannerDesk.objects.get(team_id=17)
        self.assertEqual(desk.team_name, payload["team_name"])
        self.assertEqual(desk.curator_id, payload["curator_id"])
        self.assertEqual(desk.member_ids, payload["member_ids"])
        self.assertEqual(desk.parent_tasks, payload["parent_tasks"])
        self.assertEqual(desk.subtasks, payload["subtasks"])
        self.assertEqual(desk.columns, payload["columns"])

    def test_team_desk_list_returns_all_desks(self):
        self.authenticate()
        TeamPlannerDesk.objects.create(team_id=1, team_name="A")
        TeamPlannerDesk.objects.create(team_id=2, team_name="B")

        response = self.client.get(reverse("planner-team-desk-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_auth_required(self):
        response = self.client.get(
            reverse("planner-team-desk-detail", kwargs={"team_id": 17})
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_planner_automation_get_returns_default_config(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.authenticate()

        response = self.client.get(reverse("planner-automation-config", kwargs={"event_id": 44}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "planner")
        self.assertEqual(response.data["eventId"], 44)
        self.assertTrue(response.data["stages"])
        self.assertTrue(response.data["triggers"])
        self.assertTrue(response.data["robots"])
        self.assertTrue(PlannerAutomationConfig.objects.filter(event_id=44, scope="planner").exists())

    def test_planner_automation_put_updates_config(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.authenticate()
        payload = {
            "scope": "planner",
            "eventId": 44,
            "stages": [{"id": "planned", "title": "Запланировано", "description": ""}],
            "triggers": [],
            "robots": [],
        }

        response = self.client.put(reverse("planner-automation-config", kwargs={"event_id": 44}), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = PlannerAutomationConfig.objects.get(event_id=44, scope="planner")
        self.assertEqual(config.stages, payload["stages"])
        self.assertEqual(config.triggers, [])
        self.assertEqual(config.robots, [])

    def test_planner_automation_runs_on_subtask_sprint_added(self):
        self.authenticate()
        assignee = get_user_model().objects.create_user(
            email="assignee@example.com",
            username="assignee@example.com",
            password="StrongPass123",
            is_active=True,
        )
        event = Event.objects.create(
            name="Automation event",
            description="",
            stage="active",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now(),
        )
        PlannerWorkspaceState.objects.create(
            teams=[
                {
                    "id": 17,
                    "name": "Team",
                    "curatorId": self.user.id,
                    "memberIds": [assignee.id],
                    "confirmed": True,
                    "eventId": event.id,
                }
            ],
            parent_tasks=[],
            subtasks=[
                {
                    "id": 10,
                    "teamId": 17,
                    "parentTaskId": 1,
                    "title": "API",
                    "role": "Backend",
                    "assigneeId": assignee.id,
                    "startDate": timezone.now().date().isoformat(),
                    "endDate": timezone.now().date().isoformat(),
                    "inSprint": False,
                    "status": "Бэклог",
                }
            ],
        )
        payload = {
            "enrollment_closed": False,
            "participants": [],
            "teams": [
                {
                    "id": 17,
                    "name": "Team",
                    "curatorId": self.user.id,
                    "memberIds": [assignee.id],
                    "confirmed": True,
                    "eventId": event.id,
                }
            ],
            "parent_tasks": [],
            "subtasks": [
                {
                    "id": 10,
                    "teamId": 17,
                    "parentTaskId": 1,
                    "title": "API",
                    "role": "Backend",
                    "assigneeId": assignee.id,
                    "startDate": timezone.now().date().isoformat(),
                    "endDate": timezone.now().date().isoformat(),
                    "inSprint": True,
                    "status": "Бэклог",
                }
            ],
            "columns": ["Бэклог", "Запланировано", "В работе", "На проверке", "Готово"],
        }

        response = self.client.put(reverse("planner-state"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.first()
        self.assertEqual(workspace.subtasks[0]["status"], "Запланировано")
        self.assertTrue(Notification.objects.filter(user=assignee, title__icontains="назначена").exists())
        self.assertTrue(
            PlannerAutomationExecutionLog.objects.filter(
                event_id=event.id,
                rule_kind="trigger",
                event_code="task.sprint_added",
                status=PlannerAutomationExecutionLog.STATUS_SUCCESS,
            ).exists()
        )

    def test_frontend_contract_get_users_planner(self):
        self.authenticate()
        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["enrollment_closed"], False)
        self.assertEqual(response.data["participants"], [])
        self.assertEqual(response.data["teams"], [])
        self.assertEqual(response.data["parent_tasks"], [])
        self.assertEqual(response.data["subtasks"], [])
        self.assertEqual(response.data["columns"], ["Запланировано", "В работе", "На проверке", "Готово"])
        self.assertEqual(PlannerWorkspaceState.objects.count(), 1)

    def test_frontend_contract_put_users_planner_syncs_team_desks(self):
        staff_user = get_user_model().objects.create_user(
            email="planner-admin@example.com",
            username="planner-admin@example.com",
            password="StrongPass123",
            is_active=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        payload = {
            "enrollment_closed": True,
            "participants": [{"id": 11, "full_name": "A"}],
            "teams": [
                {"id": 17, "name": "Team 17", "curatorId": 4, "memberIds": [11, 12], "confirmed": True},
                {"id": 18, "name": "Team 18", "curatorId": 5, "memberIds": [13], "confirmed": True},
            ],
            "parent_tasks": [
                {"id": 1, "teamId": 17, "title": "P1", "startDate": "2026-03-01", "endDate": "2026-03-03"},
                {"id": 2, "teamId": 18, "title": "P2", "startDate": "2026-03-04", "endDate": "2026-03-06"},
            ],
            "subtasks": [
                {
                    "id": 10,
                    "teamId": 17,
                    "parentTaskId": 1,
                    "title": "S1",
                    "role": "Backend",
                    "startDate": "2026-03-01",
                    "endDate": "2026-03-02",
                    "inSprint": True,
                    "status": "В работе",
                },
                {
                    "id": 11,
                    "teamId": 18,
                    "parentTaskId": 2,
                    "title": "S2",
                    "role": "Frontend",
                    "startDate": "2026-03-04",
                    "endDate": "2026-03-05",
                    "inSprint": False,
                    "status": "Запланировано",
                },
            ],
            "columns": ["Todo", "Doing", "Done"],
        }
        response = self.client.put(reverse("planner-state"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.first()
        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.teams, payload["teams"])
        self.assertEqual(workspace.parent_tasks, payload["parent_tasks"])
        self.assertEqual(workspace.subtasks, payload["subtasks"])

        desk17 = TeamPlannerDesk.objects.get(team_id=17)
        desk18 = TeamPlannerDesk.objects.get(team_id=18)
        self.assertEqual(len(desk17.parent_tasks), 1)
        self.assertEqual(len(desk17.subtasks), 1)
        self.assertEqual(len(desk18.parent_tasks), 1)
        self.assertEqual(len(desk18.subtasks), 1)

    def test_frontend_contract_patch_users_planner_preserves_missing_team_desk_without_prune(self):
        staff_user = get_user_model().objects.create_user(
            email="planner-preserve-admin@example.com",
            username="planner-preserve-admin@example.com",
            password="StrongPass123",
            is_active=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        workspace = PlannerWorkspaceState.objects.create(
            enrollment_closed=True,
            participants=[],
            teams=[
                {"id": 17, "name": "Team 17", "curatorId": 4, "memberIds": [11], "confirmed": False},
                {"id": 18, "name": "Team 18", "curatorId": 5, "memberIds": [12], "confirmed": False},
            ],
            parent_tasks=[{"id": 1, "teamId": 17, "title": "P1"}, {"id": 2, "teamId": 18, "title": "P2"}],
            subtasks=[{"id": 10, "teamId": 17, "parentTaskId": 1, "title": "S1"}],
            columns=["Todo", "Done"],
        )
        TeamPlannerDesk.objects.create(team_id=17, team_name="Team 17", member_ids=[11])
        TeamPlannerDesk.objects.create(team_id=18, team_name="Team 18", member_ids=[12])

        response = self.client.patch(
            reverse("planner-state"),
            {"teams": [{"id": 18, "name": "Team 18", "curatorId": 5, "memberIds": [12], "confirmed": False}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(TeamPlannerDesk.objects.filter(team_id=17).exists())
        self.assertTrue(TeamPlannerDesk.objects.filter(team_id=18).exists())
        workspace.refresh_from_db()
        self.assertEqual(sorted(team["id"] for team in workspace.teams), [17, 18])

    def test_frontend_contract_patch_users_planner_prunes_deleted_team_desk_when_requested(self):
        staff_user = get_user_model().objects.create_user(
            email="planner-delete-admin@example.com",
            username="planner-delete-admin@example.com",
            password="StrongPass123",
            is_active=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        PlannerWorkspaceState.objects.create(
            enrollment_closed=True,
            participants=[],
            teams=[
                {"id": 17, "name": "Team 17", "curatorId": 4, "memberIds": [11], "confirmed": False},
                {"id": 18, "name": "Team 18", "curatorId": 5, "memberIds": [12], "confirmed": False},
            ],
            parent_tasks=[{"id": 1, "teamId": 17, "title": "P1"}, {"id": 2, "teamId": 18, "title": "P2"}],
            subtasks=[{"id": 10, "teamId": 17, "parentTaskId": 1, "title": "S1"}],
            columns=["Todo", "Done"],
        )
        TeamPlannerDesk.objects.create(team_id=17, team_name="Team 17", member_ids=[11])
        TeamPlannerDesk.objects.create(team_id=18, team_name="Team 18", member_ids=[12])

        response = self.client.patch(
            reverse("planner-state"),
            {
                "teams": [{"id": 18, "name": "Team 18", "curatorId": 5, "memberIds": [12], "confirmed": False}],
                "prune_missing_team_desks": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(TeamPlannerDesk.objects.filter(team_id=17).exists())
        self.assertTrue(TeamPlannerDesk.objects.filter(team_id=18).exists())

    def test_projectant_get_users_planner_sees_team_subtasks(self):
        self.authenticate()
        PlannerWorkspaceState.objects.create(
            enrollment_closed=False,
            participants=[],
            teams=[
                {"id": 10, "name": "Own team", "memberIds": [self.user.id, self.user.id + 1]},
                {"id": 20, "name": "Foreign team", "memberIds": [self.user.id + 2]},
            ],
            parent_tasks=[
                {"id": 1, "teamId": 10, "title": "Own team parent"},
                {"id": 2, "teamId": 20, "title": "Foreign parent"},
            ],
            subtasks=[
                {"id": 1, "teamId": 10, "assigneeId": self.user.id, "title": "Mine"},
                {"id": 2, "teamId": 10, "assigneeId": self.user.id + 1, "title": "Teammate"},
                {"id": 3, "teamId": 20, "assigneeId": self.user.id + 2, "title": "Foreign"},
            ],
            columns=["A"],
        )

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([team["id"] for team in response.data.get("teams", [])], [10])
        self.assertEqual([task["id"] for task in response.data.get("parent_tasks", [])], [1])
        self.assertEqual([subtask["id"] for subtask in response.data.get("subtasks", [])], [1, 2])

    def test_projectant_get_users_planner_returns_teammate_roles(self):
        teammate = get_user_model().objects.create_user(
            email="planner-teammate@example.com",
            username="planner-teammate@example.com",
            password="StrongPass123",
            is_active=True,
        )
        backend = Specialization.objects.create(name="Backend")
        frontend = Specialization.objects.create(name="Frontend")
        event = Event.objects.create(
            name="Planner event",
            description="",
            stage="active",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now(),
        )
        own_application = Application.objects.create(
            user=self.user,
            event=event,
            specialization=backend,
            date_sub=timezone.now(),
            date_end=event.end_app_date,
        )
        teammate_application = Application.objects.create(
            user=teammate,
            event=event,
            specialization=frontend,
            date_sub=timezone.now(),
            date_end=event.end_app_date,
        )
        PlannerWorkspaceState.objects.create(
            enrollment_closed=False,
            participants=[],
            teams=[
                {
                    "id": 10,
                    "name": "Own team",
                    "memberIds": [self.user.id, teammate.id],
                    "eventId": event.id,
                    "sourceRequestIds": [own_application.id, teammate_application.id],
                },
            ],
            parent_tasks=[],
            subtasks=[],
            columns=["A"],
        )
        self.authenticate()

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team = response.data["teams"][0]
        self.assertEqual(team["memberRoles"][str(self.user.id)], "Backend")
        self.assertEqual(team["memberRoles"][str(teammate.id)], "Frontend")

    def test_staff_get_users_planner_sees_all_subtasks(self):
        staff_user = get_user_model().objects.create_user(
            email="staff-planner@example.com",
            username="staff-planner@example.com",
            password="StrongPass123",
            is_active=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        PlannerWorkspaceState.objects.create(
            enrollment_closed=False,
            participants=[],
            teams=[],
            parent_tasks=[],
            subtasks=[
                {"id": 1, "assigneeId": self.user.id, "title": "Assigned"},
                {"id": 2, "assigneeId": self.user.id + 1, "title": "Other"},
                {"id": 3, "title": "No assignee"},
            ],
            columns=["A"],
        )

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("subtasks", [])), 3)

    def test_curator_get_users_planner_sees_all_subtasks(self):
        CRMRole.objects.create(
            user=self.user,
            role_type=ROLE_CURATOR,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=self.user.crm_profile.pk,
        )
        self.authenticate()
        PlannerWorkspaceState.objects.create(
            enrollment_closed=False,
            participants=[],
            teams=[],
            parent_tasks=[],
            subtasks=[
                {"id": 1, "assigneeId": self.user.id, "title": "Assigned"},
                {"id": 2, "assigneeId": self.user.id + 1, "title": "Other"},
                {"id": 3, "title": "No assignee"},
            ],
            columns=["A"],
        )

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("subtasks", [])), 3)

    def test_projectant_put_users_planner_preserves_foreign_subtasks(self):
        self.authenticate()
        state = PlannerWorkspaceState.objects.create(
            enrollment_closed=False,
            participants=[],
            teams=[
                {"id": 10, "name": "Own team", "memberIds": [self.user.id, self.user.id + 1]},
                {"id": 20, "name": "Foreign team", "memberIds": [self.user.id + 2]},
            ],
            parent_tasks=[
                {"id": 1, "teamId": 10, "title": "Own parent old"},
                {"id": 2, "teamId": 20, "title": "Foreign keep"},
            ],
            subtasks=[
                {"id": 1, "teamId": 10, "assigneeId": self.user.id, "title": "Mine old"},
                {"id": 2, "teamId": 10, "assigneeId": self.user.id + 1, "title": "Teammate old"},
                {"id": 3, "teamId": 20, "assigneeId": self.user.id + 2, "title": "Foreign keep"},
            ],
            columns=["A"],
        )

        payload = {
            "enrollment_closed": False,
            "participants": [],
            "teams": [{"id": 10, "name": "Own changed", "memberIds": [self.user.id]}],
            "parent_tasks": [{"id": 1, "teamId": 10, "title": "Own parent new"}],
            "subtasks": [
                {"id": 1, "teamId": 10, "assigneeId": self.user.id + 1, "title": "Assigned to teammate"},
                {"id": 2, "teamId": 10, "assigneeId": self.user.id, "title": "Teammate task changed"},
            ],
            "columns": ["A"],
        }
        response = self.client.put(reverse("planner-state"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        state.refresh_from_db()
        self.assertEqual(state.teams[0]["name"], "Own team")
        parent_tasks_by_id = {item["id"]: item for item in state.parent_tasks}
        self.assertEqual(parent_tasks_by_id[1]["title"], "Own parent new")
        self.assertEqual(parent_tasks_by_id[2]["title"], "Foreign keep")
        subtasks_by_id = {item["id"]: item for item in state.subtasks}
        self.assertEqual(subtasks_by_id[1]["title"], "Assigned to teammate")
        self.assertEqual(subtasks_by_id[1]["assigneeId"], self.user.id + 1)
        self.assertEqual(subtasks_by_id[2]["title"], "Teammate task changed")
        self.assertEqual(subtasks_by_id[3]["title"], "Foreign keep")
