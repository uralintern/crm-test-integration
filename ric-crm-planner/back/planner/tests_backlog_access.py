"""Права в бэклоге (BL-32, BL-33, M-12, «Карточки» §8)."""

from django.contrib.auth.models import AnonymousUser

from planner.backlog.access import BacklogRole, get_team_access
from planner.backlog_test_utils import OTHER_TEAM_ID, TEAM_ID, BacklogTestBase
from planner.models import PlannerWorkspaceState


class TeamAccessTests(BacklogTestBase):
    def test_member_sees_and_edits_own_team(self):
        access = get_team_access(self.member, TEAM_ID)

        self.assertEqual(access.role, BacklogRole.MEMBER)
        self.assertTrue(access.can_view)
        self.assertTrue(access.can_edit)
        self.assertFalse(access.is_manager)
        self.assertEqual(access.team["name"], "Команда А")

    def test_member_has_no_access_to_other_team(self):
        access = get_team_access(self.member, OTHER_TEAM_ID)

        self.assertIsNone(access.role)
        self.assertFalse(access.can_view)
        self.assertFalse(access.can_edit)

    def test_team_curator_is_manager(self):
        access = get_team_access(self.curator, TEAM_ID)

        self.assertEqual(access.role, BacklogRole.CURATOR)
        self.assertTrue(access.can_view)
        self.assertTrue(access.is_manager)

    def test_curator_sees_only_curated_teams(self):
        access = get_team_access(self.curator, OTHER_TEAM_ID)

        self.assertFalse(access.can_view)

    def test_global_crm_curator_role_does_not_open_foreign_team(self):
        # Глобальная роль куратора CRM не делает куратором команды («Карточки» §8).
        global_curator = self.make_global_curator()

        access = get_team_access(global_curator, TEAM_ID)

        self.assertFalse(access.can_view)

    def test_event_leader_and_organizer_are_managers(self):
        organizer = self.make_user("organizer")
        self.event.organizers.add(organizer)

        for user in (self.leader, organizer):
            with self.subTest(user=user.email):
                access = get_team_access(user, TEAM_ID)
                self.assertEqual(access.role, BacklogRole.ORGANIZER)
                self.assertTrue(access.is_manager)

    def test_admin_role_staff_and_superuser_are_managers(self):
        crm_admin = self.make_admin()
        staff = self.make_user("staff", is_staff=True)
        superuser = self.make_user("super", is_superuser=True)

        for user in (crm_admin, staff, superuser):
            with self.subTest(user=user.email):
                access = get_team_access(user, OTHER_TEAM_ID)
                self.assertEqual(access.role, BacklogRole.ADMIN)
                self.assertTrue(access.can_view)
                self.assertTrue(access.is_manager)

    def test_outsider_and_anonymous_have_no_access(self):
        for user in (self.outsider, AnonymousUser()):
            with self.subTest(user=str(user)):
                access = get_team_access(user, TEAM_ID)
                self.assertFalse(access.can_view)
                self.assertFalse(access.can_edit)

    def test_unknown_team_is_not_found_even_for_admin(self):
        access = get_team_access(self.make_admin(), 999999)

        self.assertIsNone(access)

    def test_missing_workspace_means_no_teams(self):
        PlannerWorkspaceState.objects.all().delete()

        self.assertIsNone(get_team_access(self.member, TEAM_ID))

    def test_team_ids_and_member_ids_as_strings_are_understood(self):
        self.workspace.teams = [
            {"id": str(TEAM_ID), "memberIds": [str(self.member.id)], "curatorId": str(self.curator.id)}
        ]
        self.workspace.save()

        self.assertEqual(get_team_access(self.member, TEAM_ID).role, BacklogRole.MEMBER)
        self.assertEqual(get_team_access(self.curator, TEAM_ID).role, BacklogRole.CURATOR)
