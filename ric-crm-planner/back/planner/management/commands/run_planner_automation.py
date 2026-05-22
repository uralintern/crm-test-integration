from django.core.management.base import BaseCommand

from planner.automation_engine import run_due_planner_automation, scan_planner_deadlines


class Command(BaseCommand):
    help = "Runs due planner automation jobs and scans deadline-based planner triggers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deadlines-only",
            action="store_true",
            help="Only scan deadline triggers.",
        )
        parser.add_argument(
            "--pending-only",
            action="store_true",
            help="Only run pending delayed automation jobs.",
        )

    def handle(self, *args, **options):
        if not options["pending_only"]:
            deadline_result = scan_planner_deadlines()
            self.stdout.write(self.style.SUCCESS(f"Deadline scan: {deadline_result}"))

        if not options["deadlines_only"]:
            pending_result = run_due_planner_automation()
            self.stdout.write(self.style.SUCCESS(f"Pending jobs: {pending_result}"))
