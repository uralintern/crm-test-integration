"""CRM-автоматизация: конфигурация, вложения, журнал, запуск отложенных правил."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import CuratorOrAdminPermission
from users.serializers import (
    CRMAutomationAttachmentSerializer,
    CRMAutomationConfigPayloadSerializer,
    CRMAutomationConfigSerializer,
    CRMAutomationExecutionLogSerializer,
)
from users.models import (
    CRMAutomationConfig,
    CRMAutomationAttachment,
    CRMAutomationExecutionLog,
    Event,
)
from users.automation_defaults import create_default_crm_automation_config
from users.automation_engine import normalize_crm_automation_config_dict, run_due_crm_automation


ALLOWED_CRM_AUTOMATION_ATTACHMENT_EXTENSIONS = {"docx", "pdf", "pptx", "txt"}
CRM_AUTOMATION_ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024


class CRMAutomationAttachmentListCreateView(APIView):
    permission_classes = (CuratorOrAdminPermission,)
    parser_classes = (MultiPartParser, FormParser)

    def get_event(self):
        return get_object_or_404(Event, pk=int(self.kwargs["event_id"]), is_archived=False)

    def get(self, request, *args, **kwargs):
        event = self.get_event()
        attachments = CRMAutomationAttachment.objects.filter(event=event)
        return Response(CRMAutomationAttachmentSerializer(attachments, many=True).data)

    def post(self, request, *args, **kwargs):
        event = self.get_event()
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"file": "Файл не передан."}, status=status.HTTP_400_BAD_REQUEST)

        file_name = uploaded_file.name or "attachment"
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if extension not in ALLOWED_CRM_AUTOMATION_ATTACHMENT_EXTENSIONS:
            return Response(
                {"file": "Поддерживаются только docx, pdf, pptx, txt."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded_file.size > CRM_AUTOMATION_ATTACHMENT_MAX_SIZE:
            return Response({"file": "Файл должен быть не больше 10 МБ."}, status=status.HTTP_400_BAD_REQUEST)

        attachment = CRMAutomationAttachment.objects.create(
            event=event,
            uploaded_by=request.user if request.user.is_authenticated else None,
            file_name=file_name[:255],
            content_type=(uploaded_file.content_type or "")[:120],
            size=uploaded_file.size,
            content=uploaded_file.read(),
        )
        return Response(CRMAutomationAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class CRMAutomationConfigView(RetrieveUpdateAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = CRMAutomationConfigSerializer

    def get_object(self):
        event_id = int(self.kwargs["event_id"])
        config = CRMAutomationConfig.objects.filter(
            scope=CRMAutomationConfig.SCOPE_CRM,
            event_id=event_id,
        ).first()
        if config:
            return config
        event = get_object_or_404(Event, pk=event_id, is_archived=False)
        defaults = create_default_crm_automation_config(event_id)
        return CRMAutomationConfig.objects.create(
            scope=CRMAutomationConfig.SCOPE_CRM,
            event=event,
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
        event = get_object_or_404(Event, pk=event_id, is_archived=False)
        config = self.get_object()
        serializer = CRMAutomationConfigPayloadSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config.scope = CRMAutomationConfig.SCOPE_CRM
        config.event = event
        if "stages" in data:
            config.stages = data["stages"]
        if "triggers" in data:
            config.triggers = data["triggers"]
        if "robots" in data:
            config.robots = data["robots"]
        normalized = normalize_crm_automation_config_dict(
            {
                "scope": config.scope,
                "eventId": event_id,
                "stages": config.stages,
                "triggers": config.triggers,
                "robots": config.robots,
            }
        )
        config.stages = normalized["stages"]
        config.triggers = normalized["triggers"]
        config.robots = normalized["robots"]
        config.save()
        return Response(CRMAutomationConfigSerializer(config).data)


class CRMAutomationExecutionLogListView(ListAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = CRMAutomationExecutionLogSerializer

    def get_queryset(self):
        return CRMAutomationExecutionLog.objects.filter(
            event_id=self.kwargs["event_id"],
            config__scope=CRMAutomationConfig.SCOPE_CRM,
        ).select_related("config", "application")


class CRMAutomationPendingRunView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(run_due_crm_automation())
