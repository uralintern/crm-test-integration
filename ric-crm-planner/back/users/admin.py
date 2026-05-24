from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Answer,
    Application,
    Contact,
    CRMAutomationConfig,
    CRMAutomationAttachment,
    CRMAutomationExecutionLog,
    Direction,
    Event,
    EventSpecialization,
    Project,
    Profile,
    Question,
    CRMRole,
    Status,
    Specialization,
    Test,
    TestResult,
    TestSession,
    TrueAnswer,
)

User = get_user_model()
admin.site.unregister(User)

class CRMRoleInline(admin.TabularInline):
    model = CRMRole
    extra = 1


@admin.register(CRMRole)
class CRMRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role_type", "content_type", "object_id")
    list_filter = ("role_type", "content_type")
    search_fields = ("user__username", "user__email")


@admin.register(Profile)
class CRMProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "surname", "name", "course")
    search_fields = ("user__username", "user__email", "email", "surname", "name")


@admin.register(User)
class CRMUserAdmin(BaseUserAdmin):
    inlines = (CRMRoleInline,)


admin.site.register(Contact)
admin.site.register(Event)
admin.site.register(Specialization)
admin.site.register(EventSpecialization)
admin.site.register(Direction)
admin.site.register(Status)
admin.site.register(Application)
admin.site.register(CRMAutomationConfig)
admin.site.register(CRMAutomationExecutionLog)
admin.site.register(Test)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(TrueAnswer)
admin.site.register(TestResult)
admin.site.register(TestSession)
admin.site.register(Project)

admin.site.register(CRMAutomationAttachment)
