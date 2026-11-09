"""Сериализаторы приложения users, разложенные по доменам.

Все прежние имена доступны как `users.serializers.<имя>`.
"""

from .common import (  # noqa: F401
    DEFAULT_APPLICATION_STATUS_NAME,
    DEFAULT_APPLICATION_STATUS_NAMES,
    TESTING_APPLICATION_STATUS_NAME,
    CHAT_LINK_SENT_APPLICATION_STATUS_NAME,
    FAILED_TESTING_APPLICATION_STATUS_NAME,
    build_user_display_name,
    resolve_application_status,
    resolve_status_by_name,
    resolve_testing_status,
    FlexibleSpecializationField,
    FlexibleStatusField,
)
from .accounts import (  # noqa: F401
    UserSerializer,
    RegisterUserSerializer,
    LoginUserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailConfirmationSerializer,
    ProfileSerializer,
)
from .events import (  # noqa: F401
    EventSerializer,
    DirectionSerializer,
    ProjectSerializer,
    StatusSerializer,
    SpecializationSerializer,
)
from .applications import (  # noqa: F401
    ApplicationCreateSerializer,
    ApplicationSerializer,
)
from .notifications import (  # noqa: F401
    NotificationSerializer,
    NotificationCreateSerializer,
)
from .automation import (  # noqa: F401
    CRMAutomationAttachmentSerializer,
    CRMAutomationConfigSerializer,
    CRMAutomationConfigPayloadSerializer,
    CRMAutomationExecutionLogSerializer,
    serialize_default_crm_automation_config,
)
from .testing_integration import (  # noqa: F401
    IntegrationAnswerExportSerializer,
    IntegrationTrueAnswerExportSerializer,
    IntegrationQuestionExportSerializer,
    IntegrationTestSummarySerializer,
    IntegrationTestExportSerializer,
    IntegrationTestSessionSerializer,
    IntegrationTestResultSerializer,
    IntegrationApplicationTestingContextSerializer,
    IntegrationTestSessionUpsertSerializer,
    IntegrationTestResultCallbackSerializer,
)
