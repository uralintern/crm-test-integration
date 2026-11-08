"""Тесты WebSocket доски команды: /ws/planner/teams/<team_id>/.

Проверяют всю цепочку из api.asgi: cookie access_token -> CookieJWTAuthMiddleware
-> маршрут -> PlannerTeamDeskConsumer.

Используется TransactionTestCase: consumer ходит в БД через
database_sync_to_async, а он закрывает «старые» соединения, что ломает
транзакцию обычного TestCase. serialized_rollback=True возвращает данные
миграций (статусы и т.п.) для тестов, которые запустятся после этих.
"""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from api.asgi import application
from planner.models import PlannerWorkspaceState, TeamPlannerDesk
from planner.realtime import broadcast_team_desk_update
from users.models import CRMRole, Event, Profile, ROLE_CURATOR

FORBIDDEN_CLOSE_CODE = 4403
RECEIVE_TIMEOUT_SECONDS = 2


class PlannerTeamDeskWebSocketTests(TransactionTestCase):
    serialized_rollback = True

    def make_user(self, slug):
        email = f"ws-{slug}@example.test"
        return get_user_model().objects.create_user(
            email=email,
            username=email,
            password="StrongPass123",
            is_active=True,
        )

    def make_curator(self):
        user = self.make_user("curator")
        CRMRole.objects.create(
            user=user,
            role_type=ROLE_CURATOR,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=user.crm_profile.pk,
        )
        return user

    def make_event(self, organizers=()):
        event = Event.objects.create(
            name="WS event",
            description="",
            stage="active",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now(),
        )
        event.organizers.set(organizers)
        return event

    def communicator(self, team_id, user=None, token=None):
        headers = []
        if user is not None:
            token = str(AccessToken.for_user(user))
        if token is not None:
            headers.append((b"cookie", f"access_token={token}".encode()))
        return WebsocketCommunicator(application, f"/ws/planner/teams/{team_id}/", headers=headers)

    async def assert_rejected(self, communicator):
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, FORBIDDEN_CLOSE_CODE)

    async def assert_accepted(self, communicator, team_id):
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        snapshot = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT_SECONDS)
        self.assertEqual(snapshot["type"], "desk.snapshot")
        self.assertEqual(snapshot["teamId"], team_id)
        self.assertEqual(snapshot["desk"]["team_id"], team_id)
        await communicator.disconnect()

    async def test_anonymous_is_rejected(self):
        await self.assert_rejected(self.communicator(1))

    async def test_invalid_token_is_rejected(self):
        await self.assert_rejected(self.communicator(1, token="not-a-jwt"))

    async def test_stranger_is_rejected(self):
        stranger = await sync_to_async(self.make_user)("stranger")
        await sync_to_async(TeamPlannerDesk.objects.create)(team_id=2, member_ids=[stranger.id + 1000])
        await sync_to_async(PlannerWorkspaceState.objects.create)(teams=[{"id": 2, "memberIds": []}])

        await self.assert_rejected(self.communicator(2, user=stranger))

    async def test_user_not_organizer_of_team_event_is_rejected(self):
        user = await sync_to_async(self.make_user)("not-organizer")
        event = await sync_to_async(self.make_event)()
        await sync_to_async(PlannerWorkspaceState.objects.create)(teams=[{"id": 3, "eventId": event.id}])

        await self.assert_rejected(self.communicator(3, user=user))

    async def test_desk_member_and_desk_curator_are_accepted(self):
        member = await sync_to_async(self.make_user)("member")
        desk_curator = await sync_to_async(self.make_user)("desk-curator")
        await sync_to_async(TeamPlannerDesk.objects.create)(team_id=4, member_ids=[member.id])
        await sync_to_async(TeamPlannerDesk.objects.create)(team_id=5, curator_id=desk_curator.id)

        await self.assert_accepted(self.communicator(4, user=member), 4)
        await self.assert_accepted(self.communicator(5, user=desk_curator), 5)

    async def test_workspace_member_and_event_organizer_are_accepted(self):
        member = await sync_to_async(self.make_user)("ws-member")
        organizer = await sync_to_async(self.make_user)("organizer")
        event = await sync_to_async(self.make_event)(organizers=[organizer])
        await sync_to_async(PlannerWorkspaceState.objects.create)(
            teams=[{"id": 6, "memberIds": [member.id]}, {"id": 7, "eventId": event.id, "memberIds": []}]
        )

        await self.assert_accepted(self.communicator(6, user=member), 6)
        await self.assert_accepted(self.communicator(7, user=organizer), 7)

    async def test_curator_gets_snapshot_pong_and_broadcast(self):
        curator = await sync_to_async(self.make_curator)()
        desk = await sync_to_async(TeamPlannerDesk.objects.create)(team_id=8, team_name="Эфир")
        communicator = self.communicator(8, user=curator)

        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        snapshot = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT_SECONDS)
        self.assertEqual(snapshot["desk"]["team_name"], "Эфир")

        await communicator.send_json_to({"type": "ping"})
        self.assertEqual(
            await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT_SECONDS),
            {"type": "pong", "teamId": 8},
        )

        # Неизвестные сообщения игнорируются.
        await communicator.send_json_to({"type": "unknown"})
        self.assertTrue(await communicator.receive_nothing())

        await sync_to_async(broadcast_team_desk_update)(desk)
        update = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT_SECONDS)
        self.assertEqual(update["type"], "desk.updated")
        self.assertEqual(update["teamId"], 8)
        self.assertEqual(update["action"], "updated")
        self.assertEqual(update["desk"]["team_name"], "Эфир")

        await communicator.disconnect()
