from datetime import datetime

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.scope import HasAnyPerm
from apps.audit.services import describe_settings_changes, log
from apps.core.errors import DomainError
from .models import DEFAULTS, SystemSetting, get_setting


TIME_KEYS = {"work_start", "work_end", "checkin_late_after", "checkin_closes_after", "checkout_allowed_after", "nursing_mother_checkout_after"}
INTEGER_KEYS = {"grace_minutes", "overtime_after_minutes", "min_accuracy_m", "max_devices", "max_speed_mps"}
BOOLEAN_KEYS = {"require_passkey", "device_approval_required"}


class SystemSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.settings_manage"]

    def get(self, request):
        return Response({key: get_setting(key) for key in DEFAULTS})

    def patch(self, request):
        incoming = request.data
        if not isinstance(incoming, dict):
            raise DomainError("INVALID_SETTINGS", "Settings must be an object.")
        unknown = set(incoming) - set(DEFAULTS)
        if unknown:
            raise DomainError("INVALID_SETTINGS", f"Unknown setting(s): {', '.join(sorted(unknown))}.")
        cleaned = {}
        for key, value in incoming.items():
            if key in TIME_KEYS:
                if not isinstance(value, str):
                    raise DomainError("INVALID_SETTINGS", f"{key} must be a time.")
                try:
                    datetime.strptime(value, "%H:%M")
                except ValueError:
                    raise DomainError("INVALID_SETTINGS", f"{key} must use HH:MM format.")
            elif key in INTEGER_KEYS:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise DomainError("INVALID_SETTINGS", f"{key} must be a non-negative number.")
                value = int(value) if key != "max_speed_mps" else float(value)
            elif key in BOOLEAN_KEYS and not isinstance(value, bool):
                raise DomainError("INVALID_SETTINGS", f"{key} must be true or false.")
            cleaned[key] = value

        effective = {key: cleaned.get(key, get_setting(key)) for key in DEFAULTS}
        if effective["checkin_late_after"] >= effective["checkin_closes_after"]:
            raise DomainError("INVALID_SETTINGS", "Late check-in must start before check-in closes.")

        old = {key: get_setting(key) for key in cleaned}
        changed = {key: value for key, value in cleaned.items() if old[key] != value}
        for key, value in changed.items():
            SystemSetting.objects.update_or_create(key=key, defaults={"value": value})
        if changed:
            previous = {key: old[key] for key in changed}
            log(request, request.user, "settings.updated", describe_settings_changes(previous, changed), previous=previous, new=changed)
        return Response({key: get_setting(key) for key in DEFAULTS})
