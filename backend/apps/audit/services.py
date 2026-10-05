from .models import AuditLog


SETTING_LABELS = {
    "work_start": "work start time",
    "work_end": "work end time",
    "checkout_allowed_after": "normal check-out available from",
    "nursing_mother_checkout_after": "nursing mother check-out available from",
    "grace_minutes": "late grace period (minutes)",
    "overtime_after_minutes": "overtime threshold (minutes)",
    "min_accuracy_m": "required GPS accuracy (metres)",
    "max_speed_mps": "maximum travel speed (m/s)",
    "max_devices": "maximum registered devices per staff member",
    "require_passkey": "biometric passkey requirement",
    "device_approval_required": "new-device approval requirement",
}

FIELD_LABELS = {
    "ippis_number": "IPPIS number", "file_number": "file number", "first_name": "first name",
    "middle_name": "middle name", "last_name": "last name", "email": "email address",
    "phone": "phone number", "department": "department", "primary_campus": "primary campus",
    "department_name": "department", "campus_name": "primary campus", "roles": "roles",
    "campus_policy": "campus policy", "designation": "designation", "grade_level": "grade level",
    "employment_status": "employment status", "is_nursing_mother": "nursing mother status",
    "mfa_enabled": "authenticator MFA requirement",
    "is_active": "active status", "role_ids": "roles", "permission_ids": "permissions",
    "name": "name", "latitude": "latitude", "longitude": "longitude", "is_active": "active status",
    "polygon": "geofence boundary", "kind": "type",
}

# Serializer payloads include relationship IDs for the API as well as their friendly
# names. Auditors should see the names, never internal database numbers.
TECHNICAL_CHANGE_FIELDS = {"id", "department", "primary_campus", "role_ids", "permission_ids", "member_count"}

ACTION_LABELS = {
    "auth.login": "Signed in", "auth.login_failed": "Unsuccessful sign-in attempt",
    "auth.login_locked": "Sign-in blocked because the account is locked",
    "staff.created": "Created staff member", "staff.updated": "Updated staff member",
    "staff.deactivated": "Deactivated staff member", "staff.activated": "Activated staff member",
    "staff.password_reset": "Reset staff password", "staff.devices_reset": "Revoked staff devices",
    "staff.bulk_import": "Bulk imported staff", "role.created": "Created role", "role.updated": "Updated role",
    "role.deleted": "Deleted role", "campus.updated": "Updated campus", "geofence.created": "Created geofence",
    "geofence.updated": "Updated geofence", "device.registered": "Registered device",
    "device.removal_requested": "Requested device removal", "activity.created": "Recorded activity",
    "activity.attachment_added": "Added activity attachment", "attendance.check_in": "Checked in",
    "attendance.check_out": "Checked out", "attendance.correction_requested": "Requested attendance correction",
    "attendance.correction_decided": "Reviewed attendance correction", "leave.requested": "Submitted leave request",
    "leave.decided": "Reviewed leave request", "official_duty.requested": "Submitted official-duty request",
    "official_duty.decided": "Reviewed official-duty request", "attendance.review_decision": "Reviewed attendance record",
    "reports.exported": "Exported report", "location.accuracy_insufficient": "Attendance blocked: insufficient location accuracy",
    "geofence.violation": "Attendance blocked: outside authorized geofence",
}


def _format_value(value):
    if value is None or value == "":
        return "not set"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_format_value(item) for item in value) if value else "none"
    if isinstance(value, dict):
        if value.get("name"):
            return str(value["name"])
        return ", ".join(f"{k}: {_format_value(v)}" for k, v in value.items())
    return str(value)


def _describe_changes(previous, new):
    changes = []
    for key, value in (new or {}).items():
        if key in TECHNICAL_CHANGE_FIELDS or (previous or {}).get(key) == value:
            continue
        label = FIELD_LABELS.get(key, key.replace("_", " ")).capitalize()
        changes.append(f"{label}: {_format_value((previous or {}).get(key))} → {_format_value(value)}")
    return "; ".join(changes)


def describe_settings_changes(previous, new):
    """Create a human-readable record from the immutable old/new audit payloads."""
    changes = []
    for key, value in (new or {}).items():
        old_value = (previous or {}).get(key)
        if old_value == value:
            continue
        label = SETTING_LABELS.get(key, key.replace("_", " "))
        changes.append(f"{label}: from {old_value} to {value}")
    return "; ".join(changes) if changes else "No settings values changed."


def describe_audit_event(action, description="", previous=None, new=None):
    """Turn technical audit values into a concise explanation for an auditor."""
    if action == "settings.updated":
        return describe_settings_changes(previous, new) if new else (description.removeprefix("Updated ") or "No settings values changed.")

    label = ACTION_LABELS.get(action)
    if not label and ".director_" in action:
        request_type, decision = action.split(".director_", 1)
        label = f"{decision.capitalize()} {request_type.replace('_', ' ')} request as department director"
    if not label:
        label = action.replace(".", " ").replace("_", " ").capitalize()

    changes = _describe_changes(previous, new)
    # Decision actions already state the actor and request type in the Action
    # column. Keep their descriptions short and free of internal request IDs.
    if ".director_" in action:
        decision = action.rsplit(".director_", 1)[1]
        return "Sent for administrator approval." if decision == "approved" else "Request rejected."
    if action.endswith(".decided"):
        decision = (new or {}).get("decision") or description
        if str(decision).lower() in {"approved", "rejected", "normal", "confirmed_issue"}:
            return f"Decision: {str(decision).replace('_', ' ').capitalize()}."
    # Historic entries may already contain their human-readable action wording.
    # Do not format that wording again when the audit list is rendered.
    if description.startswith(label):
        return description
    # The action column already says what changed (e.g. "Updated staff member").
    # Keep the description to the actual field differences, exactly once.
    if action.endswith(".updated") and changes:
        return f"{changes}."
    if action.endswith(".decided") and description:
        return f"{label}: {description.capitalize()}."
    if action in {"leave.requested", "official_duty.requested"} and description:
        return f"{label}: {description}."
    if description:
        return f"{label}: {description}."
    if changes:
        return f"{label}. Changed {changes}."
    return f"{label}."


def client_ip(request):
    # Only trust X-Forwarded-For if your reverse proxy overwrites it.
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def log(request, user, action, description="", previous=None, new=None):
    description = describe_audit_event(action, description, previous, new)
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action, description=description, previous_value=previous, new_value=new,
        ip_address=client_ip(request), user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
    )
