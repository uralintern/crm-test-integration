"""API-представления приложения users, разложенные по доменам.

Все прежние имена доступны как `users.views.<имя>`.
"""

from .schema import (  # noqa: F401
    TAG_AUTH,
    TAG_USERS,
    TAG_PROFILE,
    TAG_EVENTS,
    TAG_DIRECTIONS,
    TAG_PROJECTS,
    TAG_APPLICATIONS,
    TAG_NOTIFICATIONS,
    TAG_REFERENCE,
    TAG_INTEGRATION,
    MESSAGE_RESPONSE_SCHEMA,
    ERROR_RESPONSE_SCHEMA,
    LOGIN_RESPONSE_SCHEMA,
    REFRESH_RESPONSE_SCHEMA,
    INTEGRATION_TOKEN_PARAMETER,
)
from .access import (  # noqa: F401
    _user_can_access_application,
)
from .auth import (  # noqa: F401
    UserRegistrationView,
    _set_auth_cookies,
    _set_csrf_cookie,
    LoginView,
    LogoutView,
    CookieTokenRefreshView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    EmailConfirmationView,
)
from .accounts import (  # noqa: F401
    UserInfoView,
    UserListView,
    ProfileView,
)
from .events import (  # noqa: F401
    EventListCreateView,
    EventDetailView,
    _can_export_event,
    EventDetailsExportView,
    EventApplicationsExportView,
    StatusListView,
    SpecializationListView,
)
from .directions import (  # noqa: F401
    DirectionListCreateView,
    DirectionDetailView,
    ProjectListCreateView,
    ProjectDetailView,
    UserProjectListCreateView,
    UserDirectionListView,
)
from .testing_integration import (  # noqa: F401
    TESTING_SSO_SIGNER_SALT,
    TESTING_SSO_CACHE_PREFIX,
    _get_available_tests_for_application,
    _get_application_current_session,
    _get_application_latest_result,
    _get_testing_sso_signer,
    _get_testing_sso_cache_key,
    _build_testing_sso_user_payload,
    _build_testing_application_context,
    IntegrationApplicationMixin,
    IntegrationApplicationTestingContextView,
    TestingSSOLinkView,
    TestingSSOExchangeView,
    IntegrationTestExportView,
    IntegrationApplicationTestSessionView,
    IntegrationApplicationTestResultView,
    IntegrationApplicationStatusView,
)
from .applications import (  # noqa: F401
    ApplicationListView,
    ApplicationDetailView,
    DirectionApplicationCreateView,
)
from .automation import (  # noqa: F401
    ALLOWED_CRM_AUTOMATION_ATTACHMENT_EXTENSIONS,
    CRM_AUTOMATION_ATTACHMENT_MAX_SIZE,
    CRMAutomationAttachmentListCreateView,
    CRMAutomationConfigView,
    CRMAutomationExecutionLogListView,
    CRMAutomationPendingRunView,
)
from .notifications import (  # noqa: F401
    NotificationListCreateView,
    NotificationDetailView,
    NotificationMarkAllReadView,
    NotificationClearView,
)
