"""Тесты management-команд автоматизации.

Команды вызываются воркером (run_automation) и вручную при отладке,
поэтому фиксируем их имена, флаги и то, какие шаги они запускают.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

CRM_COMMAND = "users.management.commands.run_crm_automation"
PLANNER_COMMAND = "planner.management.commands.run_planner_automation"


class RunCrmAutomationCommandTests(TestCase):
    def test_runs_due_crm_jobs_and_prints_result(self):
        out = StringIO()
        with mock.patch(f"{CRM_COMMAND}.run_due_crm_automation", return_value={"processed": 2}) as run_due:
            call_command("run_crm_automation", stdout=out)

        run_due.assert_called_once_with()
        self.assertIn("CRM pending jobs: {'processed': 2}", out.getvalue())

    def test_runs_on_empty_database_without_mocks(self):
        out = StringIO()

        call_command("run_crm_automation", stdout=out)

        self.assertIn("CRM pending jobs:", out.getvalue())


class RunPlannerAutomationCommandTests(TestCase):
    def call(self, *args):
        out = StringIO()
        with mock.patch(f"{PLANNER_COMMAND}.scan_planner_deadlines", return_value={"scan": 1}) as scan, mock.patch(
            f"{PLANNER_COMMAND}.run_due_planner_automation", return_value={"due": 2}
        ) as run_due:
            call_command("run_planner_automation", *args, stdout=out)
        return out.getvalue(), scan, run_due

    def test_without_flags_runs_scan_then_pending(self):
        output, scan, run_due = self.call()

        scan.assert_called_once_with()
        run_due.assert_called_once_with()
        self.assertIn("Deadline scan: {'scan': 1}", output)
        self.assertIn("Pending jobs: {'due': 2}", output)
        self.assertLess(output.index("Deadline scan"), output.index("Pending jobs"))

    def test_deadlines_only_skips_pending(self):
        output, scan, run_due = self.call("--deadlines-only")

        scan.assert_called_once_with()
        run_due.assert_not_called()
        self.assertNotIn("Pending jobs", output)

    def test_pending_only_skips_scan(self):
        output, scan, run_due = self.call("--pending-only")

        scan.assert_not_called()
        run_due.assert_called_once_with()
        self.assertNotIn("Deadline scan", output)

    def test_runs_on_empty_database_without_mocks(self):
        out = StringIO()

        call_command("run_planner_automation", stdout=out)

        self.assertIn("Deadline scan:", out.getvalue())
        self.assertIn("Pending jobs:", out.getvalue())
