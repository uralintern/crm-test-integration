from django.db import migrations


def make_mojibake(value: str) -> str:
    return value.encode("utf-8").decode("cp1251")


def make_double_mojibake(value: str) -> str:
    return make_mojibake(make_mojibake(value))


STATUS_NAMES = (
    "Прислал заявку",
    "Прохождение тестирования",
    "Добавился в орг чат",
    "Приступил к ПШ",
)


def build_status_name_map() -> dict[str, str]:
    status_name_map: dict[str, str] = {}

    for status_name in STATUS_NAMES:
        status_name_map[make_mojibake(status_name)] = status_name
        status_name_map[make_double_mojibake(status_name)] = status_name

    return status_name_map


def normalize_status_names(apps, schema_editor):
    Status = apps.get_model("users", "Status")
    Application = apps.get_model("users", "Application")

    for bad_name, good_name in build_status_name_map().items():
        good_status, _ = Status.objects.get_or_create(
            name=good_name,
            defaults={"description": "", "is_positive": True},
        )
        bad_statuses = Status.objects.filter(name=bad_name).exclude(pk=good_status.pk)

        for bad_status in bad_statuses:
            Application.objects.filter(status_id=bad_status.pk).update(status=good_status)
            bad_status.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_event_archive_organizers_form_fields"),
    ]

    operations = [
        migrations.RunPython(normalize_status_names, migrations.RunPython.noop),
    ]
