from django.core.management.base import BaseCommand

from planner.automation_engine import run_due_planner_automation, scan_planner_deadlines
from users.automation_engine import run_due_crm_automation


class Command(BaseCommand):
    help = "Runs due CRM and planner automation jobs."

    def handle(self, *args, **options):
        crm_result = run_due_crm_automation()
        planner_deadline_result = scan_planner_deadlines()
        planner_pending_result = run_due_planner_automation()
        self.stdout.write(self.style.SUCCESS(f"CRM pending jobs: {crm_result}"))
        self.stdout.write(self.style.SUCCESS(f"Planner deadline scan: {planner_deadline_result}"))
        self.stdout.write(self.style.SUCCESS(f"Planner pending jobs: {planner_pending_result}"))
