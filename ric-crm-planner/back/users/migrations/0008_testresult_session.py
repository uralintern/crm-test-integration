from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0007_notification_and_status_seed"),
    ]

    operations = [
        migrations.AddField(
            model_name="testresult",
            name="session",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="result",
                to="users.testsession",
            ),
        ),
    ]
