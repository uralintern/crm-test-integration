from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_add_negative_application_statuses"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="org_chat_peer_id",
            field=models.PositiveBigIntegerField(blank=True, default=0),
        ),
    ]
