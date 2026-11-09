"""Общие помощники для тестов бэклога (не содержит тестов)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from planner.models import (
    BacklogStage,
    BacklogSprint,
    BacklogSubtask,
    BacklogTask,
    BacklogWorkItem,
    PlannerWorkspaceState,
)
from users.models import CRMRole, Event, Profile, ROLE_ADMIN, ROLE_CURATOR

TEAM_ID = 101
OTHER_TEAM_ID = 202


class BacklogTestBase(TestCase):
    """Команда TEAM_ID с участниками, куратором и мероприятием; чужая команда OTHER_TEAM_ID."""

    def setUp(self):
        self.client = APIClient()
        self.leader = self.make_user("leader", first_name="Лидия", last_name="Лидерова")
        self.event = self.make_event(leader=self.leader)
        self.member = self.make_user("member", first_name="Мария", last_name="Участникова")
        self.member2 = self.make_user("member2", first_name="Павел", last_name="Второв")
        self.curator = self.make_user("curator", first_name="Кира", last_name="Кураторова")
        self.outsider = self.make_user("outsider", first_name="Остап", last_name="Посторонний")
        self.other_member = self.make_user("other", first_name="Олег", last_name="Чужой")
        self.workspace = PlannerWorkspaceState.objects.create(
            teams=[
                {
                    "id": TEAM_ID,
                    "name": "Команда А",
                    "memberIds": [self.member.id, self.member2.id],
                    "curatorId": self.curator.id,
                    "eventId": self.event.id,
                    "confirmed": True,
                },
                {
                    "id": OTHER_TEAM_ID,
                    "name": "Команда Б",
                    "memberIds": [self.other_member.id],
                    "curatorId": None,
                    "confirmed": True,
                },
            ]
        )

    # --- пользователи и роли -------------------------------------------------

    def make_user(self, slug, **extra):
        email = f"{slug}@example.test"
        return get_user_model().objects.create_user(
            email=email, username=email, password="StrongPass123", is_active=True, **extra
        )

    def give_crm_role(self, user, role_type):
        CRMRole.objects.create(
            user=user,
            role_type=role_type,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=user.crm_profile.pk,
        )
        return user

    def make_global_curator(self, slug="global-curator"):
        return self.give_crm_role(self.make_user(slug), ROLE_CURATOR)

    def make_admin(self, slug="admin"):
        return self.give_crm_role(self.make_user(slug), ROLE_ADMIN)

    def make_event(self, leader=None, organizers=()):
        event = Event.objects.create(
            name="Мероприятие бэклога",
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

    # --- объекты бэклога -----------------------------------------------------

    def make_sprint(self, team_id=TEAM_ID, title="Спринт 1", start=date(2026, 11, 2), end=date(2026, 11, 8)):
        return BacklogSprint.objects.create(team_id=team_id, title=title, start_date=start, end_date=end)

    def make_stage(self, team_id=TEAM_ID, title="Этап 1", position=0, **extra):
        return BacklogStage.objects.create(team_id=team_id, title=title, position=position, **extra)

    def make_task(
        self,
        stage,
        title="Задача",
        responsible=None,
        start=date(2026, 11, 1),
        end=date(2026, 11, 20),
        position=0,
        **extra,
    ):
        return BacklogTask.objects.create(
            stage=stage,
            team_id=stage.team_id,
            title=title,
            responsible=responsible if responsible is not None else self.member,
            start_date=start,
            end_date=end,
            position=position,
            **extra,
        )

    def make_subtask(
        self,
        task,
        title="Подзадача",
        executor=None,
        start=date(2026, 11, 3),
        end=date(2026, 11, 10),
        position=0,
        **extra,
    ):
        return BacklogSubtask.objects.create(
            task=task,
            team_id=task.team_id,
            title=title,
            executor=executor if executor is not None else self.member2,
            start_date=start,
            end_date=end,
            position=position,
            **extra,
        )

    def make_work(self, subtask, title="Работа", is_done=False, position=0, **extra):
        return BacklogWorkItem.objects.create(
            subtask=subtask, title=title, is_done=is_done, position=position, **extra
        )
