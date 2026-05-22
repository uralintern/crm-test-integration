from django.db import migrations


REMOVED_FROM_PSH_STATUS = "Удален с ПШ"


def seed_status(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Status.objects.get_or_create(
        name=REMOVED_FROM_PSH_STATUS,
        defaults={
            "description": "Проектант отказался от участия после приглашения в планировщик.",
            "is_positive": False,
        },
    )


def unseed_status(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Status.objects.filter(name=REMOVED_FROM_PSH_STATUS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0012_chat_link_statuses"),
    ]

    operations = [
        migrations.RunPython(seed_status, unseed_status),
    ]
