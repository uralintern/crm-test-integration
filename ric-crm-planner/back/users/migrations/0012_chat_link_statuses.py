from django.db import migrations


CHAT_LINK_SENT_STATUS = "Отправлена ссылка на орг. чат"
OLD_CHAT_JOINED_STATUS = "Добавился в орг чат"
CHAT_JOINED_STATUS = "Добавился в орг. чат"


def seed_chat_link_statuses(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Application = apps.get_model("users", "Application")

    Status.objects.get_or_create(
        name=CHAT_LINK_SENT_STATUS,
        defaults={
            "description": "Проектанту отправлена индивидуальная ссылка на организационный чат.",
            "is_positive": True,
        },
    )
    joined_status, _ = Status.objects.get_or_create(
        name=CHAT_JOINED_STATUS,
        defaults={
            "description": "Проектант перешел по индивидуальной ссылке на организационный чат.",
            "is_positive": True,
        },
    )

    old_statuses = Status.objects.filter(name=OLD_CHAT_JOINED_STATUS).exclude(pk=joined_status.pk)
    for old_status in old_statuses:
        Application.objects.filter(status_id=old_status.pk).update(status=joined_status)
        old_status.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_event_org_chat_url"),
    ]

    operations = [
        migrations.RunPython(seed_chat_link_statuses, migrations.RunPython.noop),
    ]
