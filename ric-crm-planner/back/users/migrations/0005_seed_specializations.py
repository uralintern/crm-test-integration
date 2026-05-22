from django.db import migrations


DEFAULT_SPECIALIZATIONS = (
    "Frontend разработчик",
    "Backend разработчик",
    "Fullstack разработчик",
    "Веб-дизайнер",
    "ML-разработчик",
    "DevOps",
    "1С-разработчик",
    "GameDev",
    "Гейм-дизайнер",
    "Аналитик",
    "Тимлид",
    "Тестировщик",
)


def seed_specializations(apps, schema_editor):
    Specialization = apps.get_model("users", "Specialization")

    for name in DEFAULT_SPECIALIZATIONS:
        Specialization.objects.get_or_create(name=name, defaults={"description": ""})


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_profile_extra_fields_event_leader"),
    ]

    operations = [
        migrations.RunPython(seed_specializations, migrations.RunPython.noop),
    ]
