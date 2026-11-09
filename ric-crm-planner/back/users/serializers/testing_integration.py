"""Интеграция с сервисом тестирования: экспорт тестов, сессии, результаты, контекст заявки."""

import json
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, Serializer
from integrations.vk.crm_notifications import notify_application_testing_started
from ..models import (
    Answer,
    Application,
    Question,
    Status,
    Test,
    TestResult,
    TestSession,
    TrueAnswer,
)
from .common import (
    build_user_display_name,
    CHAT_LINK_SENT_APPLICATION_STATUS_NAME,
    FAILED_TESTING_APPLICATION_STATUS_NAME,
    resolve_testing_status,
)
from .events import SpecializationSerializer
from .applications import ApplicationSerializer


class IntegrationAnswerExportSerializer(ModelSerializer):
    class Meta:
        model = Answer
        fields = ("id", "answer", "count")


class IntegrationTrueAnswerExportSerializer(ModelSerializer):
    class Meta:
        model = TrueAnswer
        fields = ("id", "true_answer", "points")


class IntegrationQuestionExportSerializer(ModelSerializer):
    answers = IntegrationAnswerExportSerializer(many=True, read_only=True)
    true_answers = IntegrationTrueAnswerExportSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "name",
            "count",
            "points",
            "question_type",
            "answers",
            "true_answers",
        )


class IntegrationTestSummarySerializer(ModelSerializer):
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    specializationId = serializers.IntegerField(source="specialization_id", read_only=True)
    passingScore = serializers.IntegerField(source="passing_score", read_only=True)
    timeLimit = serializers.IntegerField(source="time_limit", read_only=True)
    questionCount = serializers.IntegerField(source="question_count", read_only=True)
    testType = serializers.CharField(source="test_type", read_only=True)

    class Meta:
        model = Test
        fields = (
            "id",
            "name",
            "description",
            "entry",
            "eventId",
            "specializationId",
            "passingScore",
            "timeLimit",
            "questionCount",
            "testType",
            "is_active",
        )


class IntegrationTestExportSerializer(IntegrationTestSummarySerializer):
    questions = IntegrationQuestionExportSerializer(many=True, read_only=True)

    class Meta(IntegrationTestSummarySerializer.Meta):
        fields = IntegrationTestSummarySerializer.Meta.fields + ("questions",)


class IntegrationTestSessionSerializer(ModelSerializer):
    applicationId = serializers.IntegerField(source="application_id", read_only=True)
    testId = serializers.IntegerField(source="test_id", read_only=True)
    userId = serializers.IntegerField(source="user_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)

    class Meta:
        model = TestSession
        fields = (
            "id",
            "session_id",
            "applicationId",
            "testId",
            "userId",
            "createdAt",
            "expiresAt",
            "status",
        )


class IntegrationTestResultSerializer(ModelSerializer):
    applicationId = serializers.IntegerField(source="application_id", read_only=True)
    sessionId = serializers.CharField(source="session.session_id", read_only=True)
    testId = serializers.IntegerField(source="test_id", read_only=True)
    userId = serializers.IntegerField(source="user_id", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    correctAnswers = serializers.IntegerField(source="correct_answers", read_only=True)
    totalQuestions = serializers.IntegerField(source="total_questions", read_only=True)
    timeSpentSeconds = serializers.IntegerField(source="time_spent_seconds", read_only=True)
    resultStatus = serializers.CharField(source="result_status", read_only=True)
    detailedResults = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = (
            "id",
            "applicationId",
            "sessionId",
            "testId",
            "userId",
            "score",
            "max_score",
            "is_passed",
            "startedAt",
            "completedAt",
            "correctAnswers",
            "totalQuestions",
            "percentage",
            "timeSpentSeconds",
            "resultStatus",
            "detailedResults",
        )

    def get_detailedResults(self, obj):
        if not obj.detailed_results:
            return None
        try:
            return json.loads(obj.detailed_results)
        except (TypeError, ValueError):
            return obj.detailed_results


class IntegrationApplicationTestingContextSerializer(Serializer):
    application = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()
    event = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()
    availableTests = serializers.SerializerMethodField()
    currentSession = serializers.SerializerMethodField()
    latestResult = serializers.SerializerMethodField()

    def get_application(self, obj):
        return ApplicationSerializer(obj, context=self.context).data

    def get_applicant(self, obj):
        display_name = build_user_display_name(obj.user) or obj.user.email
        return {
            "id": obj.user_id,
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "display_name": display_name,
        }

    def get_event(self, obj):
        if not obj.event_id:
            return None
        return {
            "id": obj.event_id,
            "name": obj.event.name,
            "start_date": obj.event.start_date,
            "end_date": obj.event.end_date,
            "end_app_date": obj.event.end_app_date,
        }

    def get_direction(self, obj):
        if not obj.direction_id:
            return None
        return {
            "id": obj.direction_id,
            "name": obj.direction.name,
            "leader_id": obj.direction.leader_id,
        }

    def get_specialization(self, obj):
        if not obj.specialization_id:
            return None
        return SpecializationSerializer(obj.specialization).data

    def get_availableTests(self, obj):
        tests = self.context.get("available_tests", [])
        return IntegrationTestSummarySerializer(tests, many=True).data

    def get_currentSession(self, obj):
        session = self.context.get("current_session")
        if not session:
            return None
        return IntegrationTestSessionSerializer(session).data

    def get_latestResult(self, obj):
        result = self.context.get("latest_result")
        if not result:
            return None
        return IntegrationTestResultSerializer(result).data


class IntegrationTestSessionUpsertSerializer(Serializer):
    test_id = serializers.PrimaryKeyRelatedField(queryset=Test.objects.filter(is_active=True), source="test")
    session_id = serializers.CharField(max_length=255)
    expires_at = serializers.DateTimeField()
    status = serializers.CharField(required=False, default="assigned", max_length=50)
    answers_data = serializers.JSONField(required=False)

    def validate(self, attrs):
        application: Application = self.context["application"]
        test: Test = attrs["test"]
        session_id = attrs["session_id"]

        existing_session = TestSession.objects.filter(session_id=session_id).exclude(
            application=application
        )
        if existing_session.exists():
            raise serializers.ValidationError(
                {"session_id": "Session with this id is already linked to another application."}
            )

        if test.event_id and application.event_id and test.event_id != application.event_id:
            raise serializers.ValidationError(
                {"test_id": "Test does not belong to the application event."}
            )

        if (
            test.specialization_id
            and application.specialization_id
            and test.specialization_id != application.specialization_id
        ):
            raise serializers.ValidationError(
                {"test_id": "Test does not match the application specialization."}
            )

        return attrs

    def create(self, validated_data):
        application: Application = self.context["application"]
        previous_status_id = application.status_id
        testing_status = resolve_testing_status()
        answers_data = validated_data.pop("answers_data", None)
        session_id = validated_data["session_id"]

        defaults = {
            "application": application,
            "test": validated_data["test"],
            "user": application.user,
            "expires_at": validated_data["expires_at"],
            "status": validated_data["status"],
        }
        if answers_data is not None:
            defaults["answers_data"] = json.dumps(answers_data, ensure_ascii=False)

        session, created = TestSession.objects.update_or_create(
            session_id=session_id,
            defaults=defaults,
        )

        application.tests_assigned = True
        if not application.tests_assigned_at:
            application.tests_assigned_at = timezone.now()
        application.test_session_id = session.session_id
        application.status = testing_status
        application.save(
            update_fields=[
                "tests_assigned",
                "tests_assigned_at",
                "test_session_id",
                "status",
            ]
        )
        notify_application_testing_started(application, previous_status_id=previous_status_id)

        self.context["created"] = created
        return session


class IntegrationTestResultCallbackSerializer(Serializer):
    session_id = serializers.CharField(max_length=255)
    test_id = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all(),
        source="test",
        required=False,
        allow_null=True,
    )
    score = serializers.IntegerField()
    max_score = serializers.IntegerField()
    is_passed = serializers.BooleanField(required=False)
    completed_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField()
    correct_answers = serializers.IntegerField(required=False, min_value=0)
    total_questions = serializers.IntegerField(required=False, min_value=0)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    time_spent_seconds = serializers.IntegerField(required=False, min_value=0, default=0)
    result_status = serializers.CharField(required=False, allow_blank=True, max_length=100)
    detailed_results = serializers.JSONField(required=False)
    answers_data = serializers.JSONField(required=False)
    session_status = serializers.CharField(required=False, default="completed", max_length=50)
    application_status = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        application: Application = self.context["application"]
        session_id = attrs["session_id"]

        try:
            session = TestSession.objects.select_related("test", "application", "user").get(
                session_id=session_id
            )
        except TestSession.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"session_id": "Test session with this id was not found."}
            ) from exc

        if session.application_id != application.id:
            raise serializers.ValidationError(
                {"session_id": "Test session does not belong to this application."}
            )

        test = attrs.get("test") or session.test
        if test.id != session.test_id:
            raise serializers.ValidationError(
                {"test_id": "Test does not match the stored session test."}
            )

        if attrs["completed_at"] < attrs["started_at"]:
            raise serializers.ValidationError(
                {"completed_at": "completed_at must be greater than or equal to started_at."}
            )

        if "correct_answers" not in attrs:
            attrs["correct_answers"] = 0

        if "total_questions" not in attrs:
            attrs["total_questions"] = session.test.question_count

        if "percentage" not in attrs:
            max_score = attrs["max_score"] or 0
            attrs["percentage"] = (
                Decimal("0")
                if max_score == 0
                else Decimal(str(round((attrs["score"] / max_score) * 100, 2)))
            )

        if "is_passed" not in attrs:
            attrs["is_passed"] = attrs["score"] >= session.test.passing_score

        if not attrs.get("result_status"):
            attrs["result_status"] = "passed" if attrs["is_passed"] else "failed"

        attrs["session"] = session
        attrs["test"] = test
        return attrs

    def create(self, validated_data):
        application: Application = self.context["application"]
        previous_status = application.status.name if application.status_id else ""
        session: TestSession = validated_data.pop("session")
        test: Test = validated_data.pop("test")
        validated_data.pop("session_id", None)
        detailed_results = validated_data.pop("detailed_results", None)
        answers_data = validated_data.pop("answers_data", None)
        session_status = validated_data.pop("session_status", "completed")
        application_status_value = validated_data.pop("application_status", None)

        if detailed_results is not None:
            validated_data["detailed_results"] = json.dumps(
                detailed_results, ensure_ascii=False
            )

        result, created = TestResult.objects.update_or_create(
            session=session,
            defaults={
                **validated_data,
                "application": application,
                "test": test,
                "user": application.user,
            },
        )

        session.status = session_status
        if answers_data is not None:
            session.answers_data = json.dumps(answers_data, ensure_ascii=False)
        session.save(update_fields=["status", "answers_data"])

        application.tests_assigned = True
        if not application.tests_assigned_at:
            application.tests_assigned_at = timezone.now()
        if application.test_session_id != session.session_id:
            application.test_session_id = session.session_id

        if not application_status_value and validated_data.get("is_passed"):
            application_status_value = CHAT_LINK_SENT_APPLICATION_STATUS_NAME
        if (
            not application_status_value
            and str(validated_data.get("result_status", "")).lower()
            in {"failed_all", "failed_final"}
        ):
            application_status_value = FAILED_TESTING_APPLICATION_STATUS_NAME

        update_fields = ["tests_assigned", "tests_assigned_at", "test_session_id"]
        status_changed = False
        if application_status_value:
            status_obj = None
            if str(application_status_value).isdigit():
                status_obj = Status.objects.filter(pk=int(application_status_value)).first()
            else:
                status_obj = Status.objects.filter(
                    name__iexact=str(application_status_value).strip()
                ).first()

            if not status_obj:
                raise serializers.ValidationError(
                    {"application_status": "Application status was not found."}
                )

            application.status = status_obj
            status_changed = previous_status != status_obj.name
            update_fields.append("status")

        application.save(update_fields=update_fields)

        if status_changed:
            from users.automation_engine import run_crm_automation

            application.refresh_from_db()
            run_crm_automation(
                application,
                "request.status_changed",
                previous_status=previous_status,
                request=self.context.get("request"),
            )

        self.context["created"] = created
        return result
