from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0008_testresult_session"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="application_form_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="event",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="event",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="event",
            name="organizers",
            field=models.ManyToManyField(blank=True, related_name="organized_events", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="application",
            name="custom_fields",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
