from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannerAutomationConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(default="planner", max_length=32)),
                ("event_id", models.BigIntegerField()),
                ("stages", models.JSONField(default=list)),
                ("triggers", models.JSONField(default=list)),
                ("robots", models.JSONField(default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "CRM_PLANNER_AUTOMATION_CONFIG",
                "ordering": ("scope", "event_id"),
            },
        ),
        migrations.CreateModel(
            name="PlannerAutomationExecutionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.BigIntegerField()),
                ("team_id", models.BigIntegerField(blank=True, null=True)),
                ("entity_type", models.CharField(max_length=32)),
                ("entity_id", models.CharField(max_length=64)),
                ("event_code", models.CharField(max_length=100)),
                ("rule_kind", models.CharField(max_length=16)),
                ("rule_id", models.CharField(max_length=120)),
                ("run_key", models.CharField(max_length=255, unique=True)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("message", models.TextField(blank=True)),
                ("context", models.JSONField(default=dict)),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="execution_logs",
                        to="planner.plannerautomationconfig",
                    ),
                ),
            ],
            options={
                "db_table": "CRM_PLANNER_AUTOMATION_EXECUTION_LOG",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddConstraint(
            model_name="plannerautomationconfig",
            constraint=models.UniqueConstraint(
                fields=("scope", "event_id"),
                name="unique_planner_automation_config_scope_event",
            ),
        ),
        migrations.AddIndex(
            model_name="plannerautomationexecutionlog",
            index=models.Index(fields=["event_id", "status"], name="CRM_PLANN_event_i_56b711_idx"),
        ),
        migrations.AddIndex(
            model_name="plannerautomationexecutionlog",
            index=models.Index(fields=["scheduled_for", "status"], name="CRM_PLANN_schedul_51505a_idx"),
        ),
    ]
