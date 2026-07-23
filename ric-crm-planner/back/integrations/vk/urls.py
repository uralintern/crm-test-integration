from django.urls import path

from .views import (
    VKApplicationMessageView,
    VKBotStatusView,
    VKCallbackView,
    VKChatLinkRedirectView,
    VKPlannerInviteView,
    VKSendTestView,
    VKStartConfirmationPromptView,
)

urlpatterns = [
    path("callback/", VKCallbackView.as_view(), name="vk-callback"),
    path("send-test/", VKSendTestView.as_view(), name="vk-send-test"),
    path("bot-status/", VKBotStatusView.as_view(), name="vk-bot-status"),
    path("confirm-prompt/", VKStartConfirmationPromptView.as_view(), name="vk-confirm-prompt"),
    path("applications/<int:application_id>/message/", VKApplicationMessageView.as_view(), name="vk-application-message"),
    path("events/<int:event_id>/planner-invite/", VKPlannerInviteView.as_view(), name="vk-planner-invite"),
    path("chat-links/<str:token>/", VKChatLinkRedirectView.as_view(), name="vk-chat-link-redirect"),
]
