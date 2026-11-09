"""Автоматизация планировщика: конфигурация, журнал, скан дедлайнов, отложенные правила."""

from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from planner.automation_defaults import create_default_planner_automation_config
from planner.automation_engine import run_due_planner_automation, scan_planner_deadlines
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog
from planner.serializers import (
    PlannerAutomationConfigPayloadSerializer,
    PlannerAutomationConfigSerializer,
    PlannerAutomationExecutionLogSerializer,
)
from users.permissions import CuratorOrAdminPermission


class PlannerAutomationConfigView(RetrieveUpdateAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = PlannerAutomationConfigSerializer

    def get_object(self):
        event_id = int(self.kwargs["event_id"])
        config = PlannerAutomationConfig.objects.filter(
            scope=PlannerAutomationConfig.SCOPE_PLANNER,
            event_id=event_id,
        ).first()
        if config:
            return config
        defaults = create_default_planner_automation_config(event_id)
        return PlannerAutomationConfig.objects.create(
            scope=PlannerAutomationConfig.SCOPE_PLANNER,
            event_id=event_id,
            stages=defaults["stages"],
            triggers=defaults["triggers"],
            robots=defaults["robots"],
        )

    def put(self, request, *args, **kwargs):
        return self._save_config(request)

    def patch(self, request, *args, **kwargs):
        return self._save_config(request, partial=True)

    def _save_config(self, request, partial=False):
        event_id = int(self.kwargs["event_id"])
        config = self.get_object()
        serializer = PlannerAutomationConfigPayloadSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config.scope = PlannerAutomationConfig.SCOPE_PLANNER
        config.event_id = event_id
        if "stages" in data:
            config.stages = data["stages"]
        if "triggers" in data:
            config.triggers = data["triggers"]
        if "robots" in data:
            config.robots = data["robots"]
        config.save()
        return Response(PlannerAutomationConfigSerializer(config).data)


class PlannerAutomationExecutionLogListView(ListAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = PlannerAutomationExecutionLogSerializer

    def get_queryset(self):
        return PlannerAutomationExecutionLog.objects.filter(
            event_id=self.kwargs["event_id"],
            config__scope=PlannerAutomationConfig.SCOPE_PLANNER,
        ).select_related("config")


class PlannerAutomationDeadlineScanView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(scan_planner_deadlines())


class PlannerAutomationPendingRunView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(run_due_planner_automation())
