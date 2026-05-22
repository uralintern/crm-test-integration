from django.db import migrations


APPLICATION_STATUSES = (
    ("Не перешёл к тестированию", "Проектант не перешёл к этапу тестирования."),
    ("Не прошел тестирование", "Проектант не прошел тестирование."),
    ("Не добавился в орг чат", "Проектант не добавился в организационный чат."),
    ("Отказался от ПШ", "Проектант отказался от участия в проектной школе."),
)


def seed_statuses(apps, schema_editor):
    Status = apps.get_model("users", "Status")

    for name, description in APPLICATION_STATUSES:
        Status.objects.get_or_create(
            name=name,
            defaults={
                "description": description,
                "is_positive": False,
            },
        )


def unseed_statuses(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Status.objects.filter(name__in=[name for name, _ in APPLICATION_STATUSES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_profile_vk_confirmation"),
    ]

    operations = [
        migrations.RunPython(seed_statuses, unseed_statuses),
    ]
