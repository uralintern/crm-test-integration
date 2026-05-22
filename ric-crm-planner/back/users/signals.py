from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CRMRole, Profile, ROLE_PROJECTANT


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile, _ = Profile.objects.get_or_create(
            user=instance,
            defaults={
                "email": instance.email or "",
                "surname": instance.last_name or "",
                "name": instance.first_name or "",
                "patronymic": "",
                "telegram": "",
                "course": 0,
                "university": "",
                "vk": "",
                "vk_user_id": None,
                "vk_confirmed_at": None,
                "job": "",
                "workplace": "",
                "specialty": "",
                "about": "",
                "password_reset_token": "",
            },
        )

        CRMRole.objects.get_or_create(
            user=instance,
            role_type=ROLE_PROJECTANT,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=profile.pk,
        )
