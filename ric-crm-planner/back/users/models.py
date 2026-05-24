
from django.utils import timezone
from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings

ROLE_ADMIN = "admin"
ROLE_CURATOR = "curator"
ROLE_PROJECTANT = "projectant"
ROLE_CHOICES = (
    (ROLE_ADMIN, "Админ"),
    (ROLE_CURATOR, "Куратор"),
    (ROLE_PROJECTANT, "Проектант"),
)

'''
class User(AbstractUser):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    email = models.CharField(max_length=255, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    class Meta:
        db_table = "AUTH_USER"

    def __str__(self):
        return self.username
'''

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="crm_profile",
    )
    surname = models.CharField(max_length=150)
    name = models.CharField(max_length=150)
    patronymic = models.CharField(max_length=150, blank=True)
    telegram = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    course = models.PositiveIntegerField(blank=True)
    university = models.CharField(max_length=255, blank=True)
    vk = models.CharField(max_length=255, blank=True)
    vk_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    vk_confirmed_at = models.DateTimeField(blank=True, null=True)
    job = models.CharField(max_length=255, blank=True)
    workplace = models.CharField(max_length=255, blank=True)
    specialty = models.CharField(max_length=255, blank=True)
    about = models.TextField(blank=True)
    password_reset_token = models.CharField(max_length=255, blank=True, null=True)
    password_reset_token_created = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "CRM_PROFILE"

    def __str__(self):
        return f"{self.surname} {self.name} ({self.user.username})"


class Contact(models.Model):
    TYPE_CHOICES = (
        ("email", "Email"),
        ("phone", "Phone"),
        ("tg", "Telegram"),
        ("vk", "VK"),
    )

    id = models.BigAutoField(primary_key=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    data = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    verified_token = models.CharField(max_length=255, blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="contacts"
    )

    class Meta:
        db_table = "CRM_CONTACT"

    def __str__(self):
        return f"{self.profile} — {self.type}: {self.data}"


class CRMRole(models.Model):
    id = models.BigAutoField(primary_key=True)
    role_type = models.CharField(max_length=50, choices=ROLE_CHOICES)
    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey("content_type", "object_id")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crm_roles",
    )

    class Meta:
        db_table = "CRM_ROLE"

    def __str__(self):
        return f"{self.user} — {self.role_type} ({self.content_type} #{self.object_id})"


class Status(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_positive = models.BooleanField(default=True)

    class Meta:
        db_table = "CRM_STATUS"

    def __str__(self):
        return self.name


class Specialization(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "CRM_SPECIALIZATION"

    def __str__(self):
        return self.name


class Event(models.Model):
    id = models.BigAutoField(primary_key=True)
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_events",
    )
    organizers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="organized_events",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    stage = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    end_app_date = models.DateTimeField()
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    org_chat_url = models.URLField(max_length=500, blank=True)
    org_chat_peer_id = models.PositiveBigIntegerField(default=0, blank=True)
    application_form_fields = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "CRM_EVENT"

    def __str__(self):
        return self.name


class Direction(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="directions"
    )
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_directions",
    )

    class Meta:
        db_table = "CRM_DIRECTION"

    def __str__(self):
        return f"{self.name} ({self.event.name})"


class Project(models.Model):
    """
    Проект внутри направления мероприятия
    """

    direction = models.ForeignKey(
        "Direction",
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name="Направление",
    )

    name = models.CharField(
        max_length=255,
        verbose_name="Название проекта",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание проекта",
    )

    curator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="curated_projects",
        verbose_name="Куратор проекта",
    )

    teams = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Количество команд",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"
        ordering = ("name",)

    def __str__(self):
        return self.name



class EventSpecialization(models.Model):
    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="event_specializations"
    )
    specialization = models.ForeignKey(
        Specialization, on_delete=models.CASCADE, related_name="event_specializations"
    )

    class Meta:
        db_table = "CRM_EVENT_SPECIALIZATIONS"
        unique_together = ("event", "specialization")

    def __str__(self):
        return f"{self.event} — {self.specialization}"



class Application(models.Model):
    id = models.BigAutoField(primary_key=True)
    message = models.TextField(blank=True)
    is_link = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    comment = models.TextField(blank=True)

    date_sub = models.DateTimeField()
    date_end = models.DateTimeField()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    direction = models.ForeignKey(
        Direction, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications"
    )
    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications"
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    specialization = models.ForeignKey(
        Specialization, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications"
    )
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications"
    )
    team_id = models.BigIntegerField(null=True, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)

    tests_assigned = models.BooleanField(default=False)
    tests_assigned_at = models.DateTimeField(blank=True, null=True)
    test_session_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "CRM_APPLICATION"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "direction"],
                condition=Q(direction__isnull=False),
                name="unique_application_per_direction",
            )
        ]

    def __str__(self):
        return f"Заявка #{self.id} — {self.user}"


class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crm_notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CRM_NOTIFICATION"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Уведомление #{self.id} для {self.user}"


class CRMAutomationConfig(models.Model):
    SCOPE_CRM = "crm"

    id = models.BigAutoField(primary_key=True)
    scope = models.CharField(max_length=32, default=SCOPE_CRM)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="crm_automation_configs",
    )
    stages = models.JSONField(default=list)
    triggers = models.JSONField(default=list)
    robots = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_AUTOMATION_CONFIG"
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "event"],
                name="unique_crm_automation_config_scope_event",
            )
        ]

    def __str__(self):
        return f"{self.scope}:{self.event_id}"


class CRMAutomationExecutionLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_FAILED, "Failed"),
    )

    id = models.BigAutoField(primary_key=True)
    config = models.ForeignKey(
        CRMAutomationConfig,
        on_delete=models.CASCADE,
        related_name="execution_logs",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="automation_logs",
    )
    event_id = models.BigIntegerField()
    entity_type = models.CharField(max_length=32, default="application")
    entity_id = models.CharField(max_length=64)
    event_code = models.CharField(max_length=100)
    rule_kind = models.CharField(max_length=16)
    rule_id = models.CharField(max_length=120)
    run_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message = models.TextField(blank=True)
    context = models.JSONField(default=dict)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CRM_AUTOMATION_EXECUTION_LOG"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["event_id", "created_at"]),
            models.Index(fields=["scheduled_for", "status"]),
        ]

    def __str__(self):
        return f"{self.rule_kind}:{self.rule_id}:{self.status}"


class Test(models.Model):
    TEST_TYPE_CHOICES = (
        ("online", "Онлайн"),
        ("offline", "Офлайн"),
    )

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    entry = models.IntegerField()
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="tests")
    specialization = models.ForeignKey(Specialization, on_delete=models.SET_NULL, null=True, blank=True, related_name="tests")
    passing_score = models.IntegerField()
    time_limit = models.IntegerField()
    is_active = models.BooleanField(default=True)
    question_count = models.IntegerField()
    test_type = models.CharField(max_length=50, choices=TEST_TYPE_CHOICES)

    class Meta:
        db_table = "CRM_TEST"

    def __str__(self):
        return self.name


class TestSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField(max_length=255)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="test_sessions")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="sessions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=50)
    answers_data = models.TextField(blank=True)

    class Meta:
        db_table = "CRM_TEST_SESSION"

    def __str__(self):
        return f"Сессия {self.session_id} — {self.user}"


class TestResult(models.Model):
    id = models.BigAutoField(primary_key=True)
    score = models.IntegerField()
    max_score = models.IntegerField()
    is_passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField()
    started_at = models.DateTimeField()
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="test_results")
    session = models.OneToOneField(
        TestSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="result",
    )
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_results")
    correct_answers = models.IntegerField()
    total_questions = models.IntegerField()
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    time_spent_seconds = models.IntegerField()
    result_status = models.CharField(max_length=100)
    detailed_results = models.TextField(blank=True)

    class Meta:
        db_table = "CRM_TEST_RESULT"

    def __str__(self):
        return f"Результат {self.user} — {self.test.name}: {self.score}/{self.max_score}"


class Question(models.Model):
    QUESTION_TYPE_CHOICES = (
        ("single", "Один вариант"),
        ("multi", "Несколько вариантов"),
        ("text", "Текстовый ответ"),
    )

    id = models.BigAutoField(primary_key=True)
    name = models.TextField()
    count = models.IntegerField()
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="questions")
    points = models.IntegerField()
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPE_CHOICES)

    class Meta:
        db_table = "CRM_QUESTION"

    def __str__(self):
        return f"Вопрос {self.count}: {self.name[:40]}..."


class TrueAnswer(models.Model):
    id = models.BigAutoField(primary_key=True)
    true_answer = models.CharField(max_length=255)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="true_answers")
    points = models.IntegerField()

    class Meta:
        db_table = "CRM_TRUE_ANSWER"

    def __str__(self):
        return f"Правильный ответ: {self.true_answer}"


class Answer(models.Model):
    id = models.BigAutoField(primary_key=True)
    answer = models.CharField(max_length=255)
    count = models.IntegerField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="answers")
    is_selected = models.BooleanField(default=False)
    answered_at = models.DateTimeField()

    class Meta:
        db_table = "CRM_ANSWER"

    def __str__(self):
        return f"Ответ {self.user} на '{self.question}': {self.answer}"


class CRMAutomationAttachment(models.Model):
    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="crm_automation_attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_automation_attachments",
    )
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CRM_AUTOMATION_ATTACHMENT"
        ordering = ("-created_at",)

    def __str__(self):
        return self.file_name
