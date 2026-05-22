from django.db import migrations


CANONICAL_SPECIALIZATIONS = (
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


def normalize_specializations(apps, schema_editor):
    Specialization = apps.get_model("users", "Specialization")

    for name in CANONICAL_SPECIALIZATIONS:
        Specialization.objects.get_or_create(name=name, defaults={"description": ""})


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_seed_specializations"),
    ]

    operations = [
        migrations.RunPython(normalize_specializations, migrations.RunPython.noop),
    ]
