"""Характеризационные тесты API планировщика.

Фиксируют текущее поведение эндпоинтов /api/users/planner/ и /api/planner/...
перед реорганизацией кода. Поведение, помеченное в doc/REFACTOR_SPEC.md как
дефект (S2, S8, R1), здесь намеренно не проверяется.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner import realtime
from planner.models import (
    PlannerAutomationConfig,
    PlannerAutomationExecutionLog,
    PlannerWorkspaceState,
    TeamPlannerDesk,
)
from planner.serializers import (
    PlannerAutomationConfigPayloadSerializer,
    PlannerAutomationConfigSerializer,
    PlannerWorkspaceStateSerializer,
    serialize_default_planner_automation_config,
)
from users.models import (
    Application,
    CRMRole,
    Direction,
    Event,
    Profile,
    Project,
    ROLE_CURATOR,
    Specialization,
)

DESK_KEYS = {
    "team_id",
    "team_name",
    "curator_id",
    "member_ids",
    "parent_tasks",
    "subtasks",
    "columns",
    "updated_at",
}

LOG_KEYS = {
    "id",
    "eventId",
    "teamId",
    "entityType",
    "entityId",
    "eventCode",
    "ruleKind",
    "ruleId",
    "runKey",
    "status",
    "message",
    "context",
    "scheduledFor",
    "executedAt",
    "createdAt",
}


class PlannerApiTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def make_user(self, slug, **extra):
        email = f"{slug}@example.test"
        return get_user_model().objects.create_user(
            email=email,
            username=email,
            password="StrongPass123",
            is_active=True,
            **extra,
        )

    def make_curator(self, slug="curator"):
        user = self.make_user(slug)
        CRMRole.objects.create(
            user=user,
            role_type=ROLE_CURATOR,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=user.crm_profile.pk,
        )
        return user

    def make_event(self, name="Планировщик", leader=None, organizers=()):
        event = Event.objects.create(
            name=name,
            description="",
            stage="active",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now(),
            leader=leader,
        )
        if organizers:
            event.organizers.set(organizers)
        return event

    def desk_url(self, team_id):
        return reverse("planner-team-desk-detail", kwargs={"team_id": team_id})


class TeamDeskAccessTests(PlannerApiTestBase):
    """Кто может открыть доску команды."""

    def test_curator_gets_desk_with_contract_keys(self):
        curator = self.make_curator()
        TeamPlannerDesk.objects.create(team_id=17, team_name="Команда 17")
        self.client.force_authenticate(curator)

        response = self.client.get(self.desk_url(17))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), DESK_KEYS)
        self.assertEqual(response.data["team_id"], 17)
        self.assertEqual(response.data["team_name"], "Команда 17")

    def test_desk_member_gets_desk_without_workspace(self):
        member = self.make_user("member")
        TeamPlannerDesk.objects.create(team_id=21, member_ids=[member.id])
        self.client.force_authenticate(member)

        response = self.client.get(self.desk_url(21))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["member_ids"], [member.id])

    def test_desk_curator_id_gets_desk(self):
        user = self.make_user("desk-curator")
        TeamPlannerDesk.objects.create(team_id=22, curator_id=user.id)
        self.client.force_authenticate(user)

        response = self.client.get(self.desk_url(22))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_workspace_team_member_gets_desk(self):
        user = self.make_user("ws-member")
        PlannerWorkspaceState.objects.create(teams=[{"id": 23, "memberIds": [user.id]}])
        TeamPlannerDesk.objects.create(team_id=23)
        self.client.force_authenticate(user)

        response = self.client.get(self.desk_url(23))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_event_organizer_gets_desk_of_event_team(self):
        organizer = self.make_user("organizer")
        event = self.make_event(organizers=[organizer])
        PlannerWorkspaceState.objects.create(teams=[{"id": 24, "eventId": event.id, "memberIds": []}])
        TeamPlannerDesk.objects.create(team_id=24)
        self.client.force_authenticate(organizer)

        response = self.client.get(self.desk_url(24))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stranger_gets_403_for_existing_desk(self):
        stranger = self.make_user("stranger")
        other = self.make_user("other")
        PlannerWorkspaceState.objects.create(teams=[{"id": 25, "memberIds": [other.id]}])
        TeamPlannerDesk.objects.create(team_id=25, member_ids=[other.id], curator_id=other.id)
        self.client.force_authenticate(stranger)

        response = self.client.get(self.desk_url(25))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TeamDeskUpdateTests(PlannerApiTestBase):
    """Сохранение доски и синхронизация с общим workspace."""

    def setUp(self):
        super().setUp()
        self.member = self.make_user("desk-writer")
        self.client.force_authenticate(self.member)

    def test_put_creates_workspace_and_adds_missing_team(self):
        TeamPlannerDesk.objects.create(team_id=30, member_ids=[self.member.id])

        response = self.client.put(
            self.desk_url(30),
            {
                "team_name": "",
                "curator_id": None,
                "member_ids": [self.member.id],
                "parent_tasks": [{"id": 1, "teamId": 30, "title": "P"}],
                "subtasks": [{"id": 2, "teamId": 30, "title": "S"}],
                "columns": ["A", "B"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.get()
        self.assertEqual(
            workspace.teams,
            [
                {
                    "id": 30,
                    "name": "Команда #30",
                    "curatorId": None,
                    "memberIds": [self.member.id],
                    "confirmed": False,
                }
            ],
        )
        self.assertEqual(workspace.parent_tasks, [{"id": 1, "teamId": 30, "title": "P"}])
        self.assertEqual(workspace.subtasks, [{"id": 2, "teamId": 30, "title": "S"}])
        self.assertEqual(workspace.columns, ["A", "B"])

    def test_put_updates_existing_team_and_keeps_other_teams_tasks(self):
        PlannerWorkspaceState.objects.create(
            teams=[
                {"id": 31, "name": "Старое имя", "memberIds": [self.member.id], "confirmed": True},
                {"id": 32, "name": "Чужая", "memberIds": []},
            ],
            parent_tasks=[{"id": 1, "teamId": 31, "title": "old"}, {"id": 2, "teamId": 32, "title": "foreign"}],
            subtasks=[{"id": 5, "teamId": 32, "title": "foreign sub"}],
            columns=["X"],
        )
        TeamPlannerDesk.objects.create(team_id=31, member_ids=[self.member.id])

        response = self.client.put(
            self.desk_url(31),
            {
                "team_name": "Новое имя",
                "curator_id": 7,
                "member_ids": [self.member.id],
                "parent_tasks": [{"id": 3, "teamId": 31, "title": "new"}],
                "subtasks": [],
                "columns": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.get()
        teams = {team["id"]: team for team in workspace.teams}
        self.assertEqual(teams[31]["name"], "Новое имя")
        self.assertEqual(teams[31]["curatorId"], 7)
        self.assertTrue(teams[31]["confirmed"])
        self.assertEqual(teams[32]["name"], "Чужая")
        self.assertEqual(
            workspace.parent_tasks,
            [{"id": 2, "teamId": 32, "title": "foreign"}, {"id": 3, "teamId": 31, "title": "new"}],
        )
        self.assertEqual(workspace.subtasks, [{"id": 5, "teamId": 32, "title": "foreign sub"}])
        # Пустой список колонок доски не затирает колонки workspace.
        self.assertEqual(workspace.columns, ["X"])

    def test_put_broadcasts_desk_update(self):
        TeamPlannerDesk.objects.create(team_id=33, member_ids=[self.member.id])

        with mock.patch("planner.views.desks.broadcast_team_desk_update") as broadcast_mock:
            response = self.client.patch(self.desk_url(33), {"team_name": "Эфир"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        broadcast_mock.assert_called_once()
        self.assertEqual(broadcast_mock.call_args.args[0].team_id, 33)

    def test_stale_put_merges_tasks_and_keeps_desk_fields(self):
        desk = TeamPlannerDesk.objects.create(
            team_id=34,
            team_name="Исходное",
            member_ids=[self.member.id],
            parent_tasks=[{"id": 1, "teamId": 34, "title": "old"}],
            subtasks=[{"id": 9, "teamId": 34, "title": "sub"}],
            columns=["A"],
        )
        TeamPlannerDesk.objects.filter(pk=desk.pk).update(updated_at=timezone.now())

        response = self.client.put(
            self.desk_url(34),
            {
                # Наивная дата из прошлого: клиент работал со старой версией.
                "updated_at": "2000-01-01T00:00:00",
                "team_name": "Перезапись",
                "member_ids": [],
                "columns": ["Z"],
                "parent_tasks": [
                    {"id": 1, "teamId": 34, "title": "changed"},
                    {"id": 2, "teamId": 34, "title": "added"},
                    {"teamId": 34, "title": "без id"},
                    "мусор",
                ],
                "subtasks": [{"id": 10, "teamId": 34, "title": "new sub"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        desk.refresh_from_db()
        self.assertEqual(desk.team_name, "Исходное")
        self.assertEqual(desk.member_ids, [self.member.id])
        self.assertEqual(desk.columns, ["A"])
        self.assertEqual(
            desk.parent_tasks,
            [
                {"id": 1, "teamId": 34, "title": "old"},
                {"id": 2, "teamId": 34, "title": "added"},
                {"teamId": 34, "title": "без id"},
            ],
        )
        self.assertEqual([item["id"] for item in desk.subtasks], [9, 10])

    def test_fresh_put_with_camel_case_updated_at_replaces_fields(self):
        desk = TeamPlannerDesk.objects.create(team_id=35, team_name="Было", member_ids=[self.member.id])
        fresh = (desk.updated_at + timedelta(seconds=1)).isoformat()

        response = self.client.patch(
            self.desk_url(35),
            {"updatedAt": fresh, "team_name": "Стало", "parent_tasks": [{"id": 1, "teamId": 35}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        desk.refresh_from_db()
        self.assertEqual(desk.team_name, "Стало")
        self.assertEqual(desk.parent_tasks, [{"id": 1, "teamId": 35}])

    def test_unparseable_updated_at_is_not_treated_as_stale(self):
        desk = TeamPlannerDesk.objects.create(team_id=36, team_name="Было", member_ids=[self.member.id])

        response = self.client.patch(
            self.desk_url(36),
            {"updated_at": "не дата", "team_name": "Стало"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        desk.refresh_from_db()
        self.assertEqual(desk.team_name, "Стало")


class TeamDeskListTests(PlannerApiTestBase):
    def test_curator_sees_all_desks_as_list(self):
        curator = self.make_curator()
        TeamPlannerDesk.objects.create(team_id=1)
        TeamPlannerDesk.objects.create(team_id=2)
        self.client.force_authenticate(curator)

        response = self.client.get(reverse("planner-team-desk-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual([desk["team_id"] for desk in response.data], [1, 2])
        self.assertEqual(set(response.data[0].keys()), DESK_KEYS)

    def test_restricted_user_sees_only_own_desks(self):
        user = self.make_user("lister")
        PlannerWorkspaceState.objects.create(teams=[{"id": 3, "memberIds": [user.id]}])
        TeamPlannerDesk.objects.create(team_id=1, curator_id=user.id)
        TeamPlannerDesk.objects.create(team_id=2, member_ids=[user.id])
        TeamPlannerDesk.objects.create(team_id=3)
        TeamPlannerDesk.objects.create(team_id=4, member_ids=[user.id + 1000])
        self.client.force_authenticate(user)

        response = self.client.get(reverse("planner-team-desk-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(sorted(desk["team_id"] for desk in response.data), [1, 2, 3])


class PlannerWorkspaceStateTests(PlannerApiTestBase):
    """GET/PATCH /api/users/planner/."""

    def test_curator_patch_keeps_items_missing_from_payload(self):
        curator = self.make_curator()
        PlannerWorkspaceState.objects.create(
            teams=[],
            parent_tasks=[{"id": 1, "teamId": 1, "title": "P1"}, {"id": 2, "teamId": 1, "title": "P2"}],
            subtasks=[{"id": 10, "teamId": 1, "title": "S1"}, {"id": 11, "teamId": 1, "title": "S2"}],
        )
        self.client.force_authenticate(curator)

        response = self.client.patch(
            reverse("planner-state"),
            {
                "parent_tasks": [{"id": 2, "teamId": 1, "title": "P2 changed"}],
                "subtasks": [{"id": 11, "teamId": 1, "title": "S2 changed"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.get()
        self.assertEqual(
            workspace.parent_tasks,
            [{"id": 2, "teamId": 1, "title": "P2 changed"}, {"id": 1, "teamId": 1, "title": "P1"}],
        )
        self.assertEqual(
            workspace.subtasks,
            [{"id": 11, "teamId": 1, "title": "S2 changed"}, {"id": 10, "teamId": 1, "title": "S1"}],
        )

    def test_get_response_has_contract_keys(self):
        user = self.make_user("reader")
        self.client.force_authenticate(user)

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {"enrollment_closed", "participants", "teams", "parent_tasks", "subtasks", "columns"},
        )

    def test_curator_get_enriches_roles_by_event_direction_and_project(self):
        curator = self.make_curator()
        member = self.make_user("enriched")
        event = self.make_event()
        direction = Direction.objects.create(name="Направление", event=event)
        project = Project.objects.create(name="Проект", direction=direction)
        backend = Specialization.objects.create(name="Backend")
        Application.objects.create(
            user=member,
            event=event,
            direction=direction,
            project=project,
            specialization=backend,
            date_sub=timezone.now(),
            date_end=timezone.now(),
        )
        Application.objects.create(
            user=member,
            event=event,
            date_sub=timezone.now() - timedelta(days=1),
            date_end=timezone.now(),
        )
        PlannerWorkspaceState.objects.create(
            teams=[
                {
                    "id": 40,
                    "memberIds": [member.id],
                    "eventId": event.id,
                    "directionId": direction.id,
                    "projectId": project.id,
                    "memberRoles": {str(curator.id): "Куратор", "999": "  "},
                },
                "не команда",
            ]
        )
        self.client.force_authenticate(curator)

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team, junk = response.data["teams"]
        self.assertEqual(team["memberRoles"], {str(curator.id): "Куратор", str(member.id): "Backend"})
        self.assertEqual(junk, "не команда")

    def test_organizer_sees_teams_of_own_event(self):
        organizer = self.make_user("ws-organizer")
        event = self.make_event(leader=organizer)
        PlannerWorkspaceState.objects.create(
            teams=[{"id": 41, "eventId": event.id, "memberIds": []}, {"id": 42, "eventId": event.id + 1000}],
            parent_tasks=[{"id": 1, "teamId": 41}, {"id": 2, "teamId": 42}],
        )
        self.client.force_authenticate(organizer)

        response = self.client.get(reverse("planner-state"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([team["id"] for team in response.data["teams"]], [41])
        self.assertEqual([task["id"] for task in response.data["parent_tasks"]], [1])

    def test_organizer_patch_changes_only_teams_of_own_event(self):
        organizer = self.make_user("ws-editor")
        event = self.make_event(organizers=[organizer])
        foreign_event = self.make_event(name="Чужое")
        PlannerWorkspaceState.objects.create(
            teams=[
                {"id": 50, "name": "Своя", "eventId": event.id, "memberIds": []},
                {"id": 51, "name": "Чужая", "eventId": foreign_event.id, "memberIds": []},
            ],
            subtasks=[{"id": 1, "teamId": 50, "title": "own"}, {"id": 2, "teamId": 51, "title": "foreign"}],
        )
        self.client.force_authenticate(organizer)

        response = self.client.patch(
            reverse("planner-state"),
            {
                "teams": [
                    {"id": 50, "name": "Своя новая", "eventId": event.id, "memberIds": []},
                    {"id": 51, "name": "Взлом", "eventId": foreign_event.id, "memberIds": []},
                ],
                "subtasks": [
                    {"id": 1, "teamId": 50, "title": "own changed"},
                    {"id": 2, "teamId": 51, "title": "foreign changed"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace = PlannerWorkspaceState.objects.get()
        teams = {team["id"]: team["name"] for team in workspace.teams}
        self.assertEqual(teams, {50: "Своя новая", 51: "Чужая"})
        subtasks = {item["id"]: item["title"] for item in workspace.subtasks}
        self.assertEqual(subtasks, {1: "own changed", 2: "foreign"})


class PlannerAutomationApiTests(PlannerApiTestBase):
    def test_get_returns_existing_config(self):
        curator = self.make_curator()
        config = PlannerAutomationConfig.objects.create(event_id=5, stages=[{"id": "s"}], triggers=[], robots=[])
        self.client.force_authenticate(curator)

        response = self.client.get(reverse("planner-automation-config", kwargs={"event_id": 5}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], config.id)
        self.assertEqual(
            set(response.data.keys()),
            {"id", "scope", "eventId", "updatedAt", "stages", "triggers", "robots"},
        )
        self.assertEqual(response.data["stages"], [{"id": "s"}])

    def test_patch_updates_only_passed_fields(self):
        curator = self.make_curator()
        PlannerAutomationConfig.objects.create(event_id=6, stages=[{"id": "keep"}], triggers=[{"id": "t"}], robots=[])
        self.client.force_authenticate(curator)

        response = self.client.patch(
            reverse("planner-automation-config", kwargs={"event_id": 6}),
            {"robots": [{"id": "r1"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = PlannerAutomationConfig.objects.get(event_id=6)
        self.assertEqual(config.stages, [{"id": "keep"}])
        self.assertEqual(config.triggers, [{"id": "t"}])
        self.assertEqual(config.robots, [{"id": "r1"}])

    def test_put_with_foreign_scope_is_rejected(self):
        curator = self.make_curator()
        self.client.force_authenticate(curator)

        response = self.client.put(
            reverse("planner-automation-config", kwargs={"event_id": 7}),
            {"scope": "crm", "stages": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scope", response.data)

    def test_event_organizer_can_read_config_of_own_event(self):
        organizer = self.make_user("auto-organizer")
        event = self.make_event(organizers=[organizer])
        self.client.force_authenticate(organizer)

        response = self.client.get(reverse("planner-automation-config", kwargs={"event_id": event.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["eventId"], event.id)

    def test_student_cannot_use_automation_endpoints(self):
        student = self.make_user("auto-student")
        event = self.make_event()
        self.client.force_authenticate(student)

        urls = [
            ("get", reverse("planner-automation-config", kwargs={"event_id": event.id})),
            ("get", reverse("planner-automation-log-list", kwargs={"event_id": event.id})),
            ("post", reverse("planner-automation-deadline-scan")),
            ("post", reverse("planner-automation-run-pending")),
        ]
        for method, url in urls:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_logs_are_listed_for_event_with_contract_keys(self):
        curator = self.make_curator()
        config = PlannerAutomationConfig.objects.create(event_id=8)
        other_config = PlannerAutomationConfig.objects.create(event_id=9)
        PlannerAutomationExecutionLog.objects.create(
            config=config,
            event_id=8,
            team_id=3,
            entity_type="subtask",
            entity_id="10",
            event_code="task.created",
            rule_kind="trigger",
            rule_id="t1",
            run_key="run-8",
        )
        PlannerAutomationExecutionLog.objects.create(
            config=other_config,
            event_id=9,
            entity_type="subtask",
            entity_id="11",
            event_code="task.created",
            rule_kind="trigger",
            rule_id="t1",
            run_key="run-9",
        )
        self.client.force_authenticate(curator)

        response = self.client.get(reverse("planner-automation-log-list", kwargs={"event_id": 8}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(set(response.data[0].keys()), LOG_KEYS)
        self.assertEqual(response.data[0]["runKey"], "run-8")
        self.assertEqual(response.data[0]["teamId"], 3)

    def test_deadline_scan_without_workspace_returns_zero_counters(self):
        curator = self.make_curator()
        self.client.force_authenticate(curator)

        response = self.client.post(reverse("planner-automation-deadline-scan"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"events": 0, "changed": 0})

    def test_run_pending_without_workspace_returns_zero_counters(self):
        curator = self.make_curator()
        self.client.force_authenticate(curator)

        response = self.client.post(reverse("planner-automation-run-pending"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"processed": 0, "changed": 0})


class PlannerSerializerTests(TestCase):
    def test_workspace_serializer_create_ignores_prune_flag(self):
        serializer = PlannerWorkspaceStateSerializer(
            data={"teams": [{"id": 1}], "prune_missing_team_desks": True}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        workspace = serializer.save()

        self.assertEqual(workspace.teams, [{"id": 1}])
        self.assertNotIn("prune_missing_team_desks", serializer.data)

    def test_config_serializer_accepts_only_planner_scope(self):
        invalid = PlannerAutomationConfigSerializer(data={"scope": "crm", "eventId": 1})
        self.assertFalse(invalid.is_valid())
        self.assertIn("scope", invalid.errors)

        # scope обязателен из-за уникального ограничения (scope, event_id).
        valid = PlannerAutomationConfigSerializer(
            data={"scope": "planner", "eventId": 1, "stages": [], "triggers": [], "robots": []}
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.validated_data["scope"], PlannerAutomationConfig.SCOPE_PLANNER)

    def test_payload_serializer_represents_model_instance_as_config(self):
        config = PlannerAutomationConfig.objects.create(event_id=3)

        data = PlannerAutomationConfigPayloadSerializer(config).data

        self.assertEqual(data["eventId"], 3)
        self.assertEqual(data["scope"], "planner")
        self.assertIn("id", data)

    def test_payload_serializer_represents_plain_dict(self):
        data = PlannerAutomationConfigPayloadSerializer({"scope": "planner", "eventId": 4}).data

        self.assertEqual(data["eventId"], 4)
        self.assertNotIn("id", data)

    def test_default_config_contains_stages_triggers_and_robots(self):
        config = serialize_default_planner_automation_config(12)

        self.assertTrue(config["stages"])
        self.assertTrue(config["triggers"])
        self.assertTrue(config["robots"])


class PlannerModelStrTests(TestCase):
    def test_model_string_representations(self):
        config = PlannerAutomationConfig.objects.create(event_id=2)
        log = PlannerAutomationExecutionLog(config=config, rule_kind="robot", rule_id="r1", status="success")

        self.assertEqual(str(PlannerWorkspaceState()), "Состояние планировщика")
        self.assertEqual(str(TeamPlannerDesk(team_id=5)), "Доска команды #5")
        self.assertEqual(str(config), "Автоматизация планировщика: planner:2")
        self.assertEqual(str(log), "robot:r1 — success")


class PlannerRealtimeTests(TestCase):
    def test_broadcast_is_skipped_without_channel_layer(self):
        desk = TeamPlannerDesk.objects.create(team_id=60)

        with mock.patch.object(realtime, "get_channel_layer", return_value=None), self.assertLogs(
            "planner.realtime", level="WARNING"
        ) as logs:
            realtime.broadcast_team_desk_update(desk)

        self.assertIn("channel layer is not configured", logs.output[0])

    def test_broadcast_error_is_logged_and_not_raised(self):
        desk = TeamPlannerDesk.objects.create(team_id=61)
        layer = mock.Mock()
        layer.group_send = mock.AsyncMock(side_effect=RuntimeError("layer down"))

        with mock.patch.object(realtime, "get_channel_layer", return_value=layer), self.assertLogs(
            "planner.realtime", level="ERROR"
        ) as logs:
            realtime.broadcast_team_desk_update(desk, action="deleted")

        self.assertIn("team_id=61", logs.output[0])
        group, message = layer.group_send.call_args.args
        self.assertEqual(group, "planner_team_61")
        self.assertEqual(message["type"], "desk.updated")
        self.assertEqual(message["action"], "deleted")
        self.assertEqual(message["teamId"], 61)
