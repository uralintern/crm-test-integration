from django.core.management.base import BaseCommand

from users.automation_engine import run_due_crm_automation


class Command(BaseCommand):
    help = "Runs due delayed CRM automation jobs."

    def handle(self, *args, **options):
        result = run_due_crm_automation()
        self.stdout.write(self.style.SUCCESS(f"CRM pending jobs: {result}"))
