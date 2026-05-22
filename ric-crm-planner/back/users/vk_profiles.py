from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from integrations.vk.services import (
    VKAPIError,
    VKConfigurationError,
    extract_vk_user_id,
    normalize_vk_group_id,
    resolve_vk_user_id,
)

from .models import Profile


def get_vk_bot_url() -> str:
    group_id = normalize_vk_group_id()
    if not group_id:
        return ""
    return f"https://vk.com/im?sel=-{group_id}"


def resolve_profile_vk_user_id(vk_value: str | int | None) -> int | None:
    extracted = extract_vk_user_id(vk_value)
    if extracted:
        return extracted

    if not settings.VK_ENABLED or not settings.VK_ACCESS_TOKEN:
        return None

    try:
        return resolve_vk_user_id(vk_value)
    except (VKConfigurationError, VKAPIError, ValueError):
        return None


def refresh_profile_vk_user_id(profile: Profile, *, force: bool = False) -> int | None:
    if profile.vk_user_id and not force:
        return int(profile.vk_user_id)

    vk_user_id = resolve_profile_vk_user_id(profile.vk)
    if vk_user_id and profile.vk_user_id != vk_user_id:
        profile.vk_user_id = vk_user_id
        profile.save(update_fields=["vk_user_id"])
    return vk_user_id


def reset_profile_vk_confirmation_if_changed(profile: Profile, old_vk: str) -> None:
    if (old_vk or "").strip() == (profile.vk or "").strip():
        return

    profile.vk_user_id = resolve_profile_vk_user_id(profile.vk)
    profile.vk_confirmed_at = None
    profile.save(update_fields=["vk_user_id", "vk_confirmed_at"])


def confirm_profile_by_vk_user_id(vk_user_id: int) -> Profile | None:
    confirmed_at = timezone.now()
    matched_profiles = list(Profile.objects.filter(vk_user_id=vk_user_id).select_related("user"))
    for profile in matched_profiles:
        if not profile.vk_confirmed_at:
            profile.vk_confirmed_at = confirmed_at
            profile.save(update_fields=["vk_confirmed_at"])

    candidates = Profile.objects.exclude(vk="").select_related("user")
    for candidate in candidates:
        if any(profile.pk == candidate.pk for profile in matched_profiles):
            continue
        resolved_user_id = refresh_profile_vk_user_id(candidate, force=True)
        if resolved_user_id == vk_user_id:
            candidate.vk_confirmed_at = confirmed_at
            candidate.save(update_fields=["vk_user_id", "vk_confirmed_at"])
            matched_profiles.append(candidate)

    return matched_profiles[0] if matched_profiles else None
