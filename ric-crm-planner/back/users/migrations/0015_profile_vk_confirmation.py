from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_crmautomationconfig_crmautomationexecutionlog_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="vk_user_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="vk_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
