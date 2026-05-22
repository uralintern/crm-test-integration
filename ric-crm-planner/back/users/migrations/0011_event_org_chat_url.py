from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_normalize_status_mojibake"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="org_chat_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
