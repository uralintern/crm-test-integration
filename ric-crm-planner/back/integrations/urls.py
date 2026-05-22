from django.urls import include, path

urlpatterns = [
    path("vk/", include("integrations.vk.urls")),
]
