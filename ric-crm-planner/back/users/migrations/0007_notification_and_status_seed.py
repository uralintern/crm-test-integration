from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


APPLICATION_STATUSES = (
    "Прислал заявку",
    "Прохождение тестирования",
    "Добавился в орг чат",
    "Приступил к ПШ",
)


def seed_statuses(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    for name in APPLICATION_STATUSES:
        Status.objects.get_or_create(
            name=name,
            defaults={"description": "", "is_positive": True},
        )


def unseed_statuses(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Status.objects.filter(name__in=APPLICATION_STATUSES).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("users", "0006_normalize_specializations"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField(blank=True)),
                ("link", models.CharField(blank=True, max_length=500)),
                ("read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crm_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "CRM_NOTIFICATION",
                "ordering": ("-created_at",),
            },
        ),
        migrations.RunPython(seed_statuses, unseed_statuses),
    ]
