import os
from calendar import monthrange
from datetime import date, datetime, timedelta
import secrets
import hashlib

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.http import HttpResponse
from axes.handlers.proxy import AxesProxyHandler
from . import reports as rpt
from apps.accounts.scope import HasAnyPerm, scoped_staff
from apps.audit.services import log
from apps.core.errors import DomainError
from apps.core.emailing import send_email
from apps.core.models import get_setting
from apps.devices.models import DeviceRemovalRequest, RegisteredDevice
from apps.org.models import Campus, Geofence
from apps.org.models import Department
from . import absence, face, rules, services, totp
from .models import (ActivityAttachment, ActivityCategory, AttendanceRecord, DailyActivity, AttendanceCorrection, Holiday, LeaveRecord, OfficialDuty, RecurringLeaveSchedule, FaceProfile, FaceVerification)
from .serializers import (ActivitySerializer, AttendanceRecordSerializer, CampusSerializer,
                          CategorySerializer, GeofenceSerializer, LocationInputSerializer,
                          CorrectionSerializer, HolidaySerializer, LeaveSerializer, OfficialDutySerializer, RecurringLeaveSerializer)


# ---------- Auth ----------
class CanRecallDepartmentRequest(BasePermission):
    """Administrators may recall broadly; directors may recall within their department."""
    def has_permission(self, request, view):
        return (request.user.has_perm("accounts.attendance_approve") or
                (request.user.department_id and request.user.has_perm("accounts.department_request_review")))


def notification_recipients(permission, department=None):
    """Return email addresses for role/direct permission holders, without duplicates."""
    users = get_user_model().objects.filter(is_active=True).filter(
        Q(user_permissions__codename=permission) | Q(groups__permissions__codename=permission)
    )
    if department:
        users = users.filter(department=department)
    return list(users.distinct().exclude(email="").values_list("email", flat=True))


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        ippis_number = str(request.data.get("ippis_number", "")).strip()
        user = authenticate(request, username=ippis_number,
                            password=request.data.get("password", ""))
        if not user:                              # axes counts failures and locks after 5
            if AxesProxyHandler.is_locked(request, credentials={"username": ippis_number}):
                log(request, None, "auth.login_locked", ippis_number[:32])
                raise DomainError("ACCOUNT_LOCKED", "This account is locked after too many unsuccessful sign-in attempts. Please try again in 30 minutes.", 403)
            log(request, None, "auth.login_failed", ippis_number[:32])
            raise DomainError("INVALID_CREDENTIALS", "Invalid IPPIS number or password.", 401)
        # Require the authenticator code only after staff have completed enrollment.
        # A newly enabled profile may still sign in once to configure the app.
        if user.mfa_enabled and user.mfa_confirmed:
            request.session["mfa_user_id"] = user.pk
            request.session.set_expiry(300)
            return Response({"mfa_required": True})
        login(request, user)
        request.session.set_expiry(60 * 60 * 9)
        log(request, user, "auth.login")
        return Response(me_payload(user, request.data.get("device_token")))


class MFAVerifyLogin(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        user_id = request.session.get("mfa_user_id")
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if not user or not user.mfa_enabled or not user.mfa_confirmed:
            request.session.pop("mfa_user_id", None)
            raise DomainError("MFA_EXPIRED", "Your sign-in verification has expired. Please sign in again.", 401)
        if not totp.verify(user.mfa_secret, request.data.get("code", "")):
            raise DomainError("INVALID_MFA_CODE", "The authenticator code is invalid or has expired. Try the current code.", 401)
        request.session.pop("mfa_user_id", None)
        # This user is reloaded from the temporary MFA session rather than returned
        # by authenticate(), so it has no `backend` attribute. Specify the password
        # backend explicitly because Axes and ModelBackend are both configured.
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.set_expiry(60 * 60 * 9)
        log(request, user, "auth.login", "Signed in with authenticator MFA")
        return Response(me_payload(user, request.data.get("device_token")))


class MFASetup(APIView):
    def post(self, request):
        if not request.user.mfa_enabled:
            raise DomainError("MFA_DISABLED", "An administrator must enable MFA on your staff profile first.", 403)
        if request.user.mfa_confirmed:
            raise DomainError("MFA_CONFIGURED", "Authenticator MFA is already configured.", 409)
        if not request.user.mfa_secret:
            request.user.mfa_secret = totp.new_secret()
            request.user.save(update_fields=["mfa_secret"])
        return Response({"secret": request.user.mfa_secret,
                         "provisioning_uri": totp.provisioning_uri(request.user.mfa_secret, request.user.ippis_number)})


class MFAConfirmSetup(APIView):
    def post(self, request):
        if not request.user.mfa_enabled or not request.user.mfa_secret:
            raise DomainError("MFA_SETUP_REQUIRED", "Start MFA setup before confirming an authenticator code.", 409)
        if not totp.verify(request.user.mfa_secret, request.data.get("code", "")):
            raise DomainError("INVALID_MFA_CODE", "The authenticator code is invalid or has expired. Try the current code.", 400)
        request.user.mfa_confirmed = True
        request.user.save(update_fields=["mfa_confirmed"])
        log(request, request.user, "mfa.configured", "Authenticator-app MFA configured")
        return Response({"configured": True})


class LogoutView(APIView):
    # Logging out is safe to allow without a CSRF token: it only invalidates the caller's
    # session. Using the underlying Django request avoids SessionAuthentication rejecting
    # this endpoint when a browser has a valid session but its CSRF cookie was cleared.
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        django_request = request._request
        # APIView's empty authentication classes deliberately treat this request as
        # anonymous, but Django's session is still present on the underlying request.
        # logout() flushes that session whether or not a user object was resolved.
        logout(django_request)
        return Response(status=204)


def me_payload(user, device_token=None):
    device_hash = hashlib.sha256(str(device_token).encode()).hexdigest() if device_token else ""
    return {
        "id": user.pk, "name": user.get_full_name(), "first_name": user.first_name, "last_name": user.last_name,
        "ippis_number": user.ippis_number,
        "department": user.department.name if user.department_id else None,
        "can_admin": user.has_perm("accounts.attendance_view_all")
                     or user.has_perm("accounts.attendance_view_scope"),
        "can_manage_staff": user.has_perm("accounts.staff_manage"),
        "can_view_staff": user.has_perm("accounts.attendance_view_all") or user.has_perm("accounts.attendance_view_scope"),
        "can_access_staff": user.has_perm("accounts.staff_manage") or user.has_perm("accounts.attendance_view_all") or user.has_perm("accounts.attendance_view_scope"),
        "can_approve": user.has_perm("accounts.attendance_approve") or user.has_perm("accounts.attendance_correct"),
        "can_manage_devices": user.has_perm("accounts.device_manage"),
        "can_access_approvals": user.has_perm("accounts.attendance_approve") or user.has_perm("accounts.attendance_correct") or user.has_perm("accounts.device_manage") or user.has_perm("accounts.department_request_review"),
        "can_export_reports": user.has_perm("accounts.reports_export"),
        "can_view_audit": user.has_perm("accounts.audit_view"),
        "can_manage_geofence": user.has_perm("accounts.geofence_manage"),
        "can_manage_roles": user.has_perm("accounts.settings_manage"),
        "can_review_department_requests": user.has_perm("accounts.department_request_review"),
        "face_enrolled": FaceProfile.objects.filter(user=user, status="active").exists(),
        "require_face_verification": get_setting("require_face_verification"),
        "has_approved_device": user.devices.filter(status="active", binding_hash__isnull=False).exists(),
        "has_current_approved_device": bool(device_hash) and user.devices.filter(
            status="active", binding_hash=device_hash
        ).exists(),
        "require_approved_device": get_setting("require_approved_device"),
        "mfa_enabled": user.mfa_enabled,
        "mfa_configured": user.mfa_confirmed,
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    permission_classes = [AllowAny]              # also primes the csrftoken cookie

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        return Response({"authenticated": True, **me_payload(request.user, request.headers.get("X-Attendance-Device-Token"))})


# ---------- Attendance ----------
class FaceStatus(APIView):
    def get(self, request):
        profile = FaceProfile.objects.filter(user=request.user).first()
        return Response({
            "status": profile.status if profile else "not_enrolled",
            "enrolled_at": profile.enrolled_at if profile else None,
            "last_verified_at": profile.last_verified_at if profile else None,
        })


class DeviceBindingList(APIView):
    def get(self, request):
        devices = request.user.devices.filter(binding_hash__isnull=False).prefetch_related("removal_request").order_by("-registered_at")
        return Response([{"id": device.pk, "label": device.label, "status": device.status,
                          "registered_at": device.registered_at, "last_seen_at": device.last_seen_at,
                          "removal_pending": hasattr(device, "removal_request") and device.removal_request.status == "pending"}
                         for device in devices])


class DeviceRemovalRequestView(APIView):
    def post(self, request, pk):
        device = request.user.devices.filter(pk=pk, binding_hash__isnull=False, status="active").first()
        if not device:
            raise DomainError("NOT_FOUND", "Approved device not found.", 404)
        removal, created = DeviceRemovalRequest.objects.get_or_create(device=device, defaults={"status": "pending"})
        if not created and removal.status == "pending":
            raise DomainError("REMOVAL_ALREADY_REQUESTED", "This device removal is already awaiting administrator approval.", 409)
        if not created:
            removal.status, removal.decided_by, removal.decided_at = "pending", None, None
            removal.save(update_fields=["status", "decided_by", "decided_at"])
        log(request, request.user, "device.removal_requested", device.label)
        return Response({"status": "pending"}, status=202)


class DeviceRemovalQueue(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.device_manage"]

    def get(self, request):
        removals = DeviceRemovalRequest.objects.filter(status="pending", device__binding_hash__isnull=False).select_related("device", "device__user").order_by("requested_at")
        return Response([{"id": item.pk, "staff": item.device.user.get_full_name(), "ippis": item.device.user.ippis_number,
                          "device_label": item.device.label, "requested_at": item.requested_at} for item in removals])


class DeviceRemovalDecide(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.device_manage"]

    def post(self, request, pk):
        item = DeviceRemovalRequest.objects.filter(pk=pk, status="pending", device__binding_hash__isnull=False).select_related("device", "device__user").first()
        if not item:
            raise DomainError("NOT_FOUND", "Device-removal request not found or already decided.", 404)
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        item.status, item.decided_by, item.decided_at = decision, request.user, timezone.now()
        item.save(update_fields=["status", "decided_by", "decided_at"])
        if decision == "approved":
            item.device.status = "revoked"
            item.device.save(update_fields=["status"])
            # The biometric template belongs to the approved device binding too.
            # Removing the device therefore removes the encrypted face profile;
            # the staff member must perform a fresh face-and-device setup later.
            FaceProfile.objects.filter(user=item.device.user).delete()
        description = f"{item.device.user.ippis_number}: {item.device.label}"
        if decision == "approved":
            description += "; device revoked and face verification removed"
        log(request, request.user, f"device.removal_{decision}", description)
        return Response({"status": decision})


class FaceEnroll(APIView):
    def post(self, request):
        profile, _ = FaceProfile.objects.get_or_create(user=request.user)
        token = str(request.data.get("device_token", "")).strip()
        label = str(request.data.get("label", "This browser")).strip()[:80]
        if len(token) < 32:
            raise DomainError("INVALID_DEVICE_TOKEN", "This browser could not create a secure device token. Please update your browser and try again.")
        fingerprint = hashlib.sha256(token.encode()).hexdigest()
        # A new user creates a template. An existing user proves their face again
        # before a replacement browser is bound to the account.
        encrypted_template = (profile.template_encrypted if profile.status == "active"
                              else face.enroll(request.data.get("images", [])))
        if profile.status == "active":
            face.verify(request.data.get("images", []), profile.template_encrypted)
        bound_device = RegisteredDevice.objects.filter(user=request.user, binding_hash=fingerprint).first()
        # A device that was previously removed has the same browser token. A fresh
        # successful face verification is the explicit re-registration step, so
        # reactivate that binding rather than leaving the account face-only.
        if bound_device and bound_device.status == RegisteredDevice.Status.REVOKED:
            bound_device.status = RegisteredDevice.Status.ACTIVE
            bound_device.label = label or "This browser"
            bound_device.user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
            bound_device.save(update_fields=["status", "label", "user_agent"])
        if not bound_device:
            other_owner = RegisteredDevice.objects.filter(binding_hash=fingerprint).exists()
            if other_owner:
                raise DomainError("DEVICE_TOKEN_CONFLICT", "This browser device token is already bound to another account. Clear the app data and try again.", 409)
            count = request.user.devices.filter(binding_hash__isnull=False).exclude(status="revoked").count()
            if count >= get_setting("max_devices"):
                raise DomainError("DEVICE_LIMIT", "You have reached the approved-device limit. Ask an administrator to remove an old device first.", 409)
            bound_device = RegisteredDevice.objects.create(
                user=request.user, label=label or "This browser", binding_hash=fingerprint, status="active",
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            )
        profile.template_encrypted = encrypted_template
        profile.status = "active"
        if not profile.enrolled_at:
            profile.enrolled_at = timezone.now()
        profile.enrollment_user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
        profile.save(update_fields=["template_encrypted", "status", "enrolled_at", "enrollment_user_agent", "updated_at"])
        log(request, request.user, "face.enrolled", "Face verification enrolled and device bound",
            new={"device": bound_device.pk, "device_status": bound_device.status})
        return Response({"status": profile.status, "enrolled_at": profile.enrolled_at,
                         "device_status": bound_device.status, "device_label": bound_device.label}, status=201)


class FaceChallenge(APIView):
    """Creates a short-lived, action-bound browser camera liveness challenge."""
    def post(self, request):
        action_name = request.data.get("action")
        if action_name not in ("check-in", "check-out"):
            raise DomainError("INVALID_FACE_ACTION", "Face verification is only available for check-in or check-out.")
        actions = ["Look straight at the camera"]
        challenge = {"nonce": secrets.token_urlsafe(32), "action": action_name, "actions": actions, "expires": (timezone.now() + timedelta(minutes=2)).timestamp()}
        request.session["face_challenge"] = challenge
        return Response({"challenge_id": challenge["nonce"], "steps": actions, "expires_in_seconds": 120})


class FaceVerify(APIView):
    def post(self, request):
        challenge = request.session.get("face_challenge")
        challenge_id = request.data.get("challenge_id", "")
        if not challenge or challenge.get("nonce") != challenge_id or challenge.get("expires", 0) < timezone.now().timestamp():
            raise DomainError("FACE_CHALLENGE_EXPIRED", "Face-verification session expired. Start again.", 409)
        profile = FaceProfile.objects.filter(user=request.user, status="active").first()
        if not profile:
            raise DomainError("FACE_ENROLLMENT_REQUIRED", "Set up face verification before recording attendance.", 409)
        request.session.pop("face_challenge", None)
        action_name = challenge["action"]
        try:
            distance = face.verify(request.data.get("images", []), profile.template_encrypted)
        except DomainError as error:
            error_code = str(error.detail.get("code", "FACE_VERIFICATION_FAILED"))
            FaceVerification.objects.create(user=request.user, action=action_name, status="failed", liveness_passed=False,
                                            failure_reason=error_code[:160], challenge_nonce=challenge_id,
                                            expires_at=timezone.now() + timedelta(minutes=2))
            log(request, request.user, "face.verification_failed", error_code)
            raise
        result = FaceVerification.objects.create(user=request.user, action=action_name, status="success", liveness_passed=True,
                                                 match_distance=distance, challenge_nonce=challenge_id,
                                                 expires_at=timezone.now() + timedelta(minutes=2))
        log(request, request.user, "face.verified", action_name, new={"verification": str(result.pk), "distance": round(distance, 4)})
        return Response({"verification_id": str(result.pk), "expires_in_seconds": 120})


class CheckIn(APIView):
    def post(self, request):
        s = LocationInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = services.check_in(request, request.user, s.validated_data)
        return Response(AttendanceRecordSerializer(rec).data, status=201)


class CheckOut(APIView):
    def post(self, request):
        s = LocationInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = services.check_out(request, request.user, s.validated_data)
        return Response(AttendanceRecordSerializer(rec).data)


class Today(APIView):
    def get(self, request):
        now = timezone.now()
        services.finalize_expired_open_records(now)
        today = timezone.localdate(now)
        rec = AttendanceRecord.objects.filter(user=request.user, date=today).first()
        state = "not_checked_in" if not rec else ("checked_out" if rec.check_out_at else "checked_in")
        return Response({"state": state, "server_time": now,
                         "checkout_allowed_after": rules.checkout_time_for(request.user),
                         "checkin_late_after": get_setting("checkin_late_after"),
                         "checkin_closes_after": get_setting("checkin_closes_after"),
                         "checkin_open": rules.checkin_is_open(timezone.localtime(now)),
                         "is_working_day": absence.is_working_day(today),
                         "non_working_reason": absence.non_working_reason(today),
                         "record": AttendanceRecordSerializer(rec).data if rec else None})


class History(APIView):
    def get(self, request):
        month = request.query_params.get("month")
        try:
            year, month_number = (map(int, month.split("-")) if month else
                                  (timezone.localdate().year, timezone.localdate().month))
            first_day = date(year, month_number, 1)
        except (TypeError, ValueError):
            raise DomainError("INVALID_MONTH", "Month must be in YYYY-MM format.")

        qs = (AttendanceRecord.objects.filter(user=request.user, date__year=year, date__month=month_number)
              .select_related("campus"))
        qs = qs.order_by("-date")[:100]
        records = list(qs)
        present_dates = {record.date for record in records}
        # Future dates must never be counted as absent. Approved requests are
        # evaluated against every elapsed working day, so a late approval also
        # corrects the staff member's past-month absence total automatically.
        last_day = min(date(year, month_number, monthrange(year, month_number)[1]), timezone.localdate())
        working_dates = []
        current = first_day
        while current <= last_day:
            if absence.is_working_day(current):
                working_dates.append(current)
            current += timedelta(days=1)
        excused_days = sum(
            request.user.pk in (absence.on_approved_leave(day) | absence.on_official_duty(day) | absence.on_recurring_leave(day))
            and day not in present_dates
            for day in working_dates
        )
        eligible_days = max(len(working_dates) - excused_days, 0)
        present = len(present_dates & set(working_dates))
        return Response({
            "records": AttendanceRecordSerializer(records, many=True).data,
            "summary": {"days_present": present, "days_absent": max(eligible_days - present, 0)},
        })


# ---------- Activities ----------
def _open_record(user):
    rec = AttendanceRecord.objects.filter(user=user, date=timezone.localdate()).first()
    if not rec:
        raise DomainError("NOT_CHECKED_IN", "Check in before adding activities.", 409)
    if rec.check_out_at:
        raise DomainError("ALREADY_CHECKED_OUT", "You have already checked out today.", 409)
    return rec


class TodayActivities(APIView):
    def get(self, request):
        rec = AttendanceRecord.objects.filter(user=request.user, date=timezone.localdate()).first()
        acts = rec.activities.all() if rec else []
        return Response(ActivitySerializer(acts, many=True).data)

    def post(self, request):
        rec = _open_record(request.user)
        s = ActivitySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        act = s.save(record=rec)
        log(request, request.user, "activity.created", act.title)
        return Response(ActivitySerializer(act).data, status=201)


class ActivityDetail(APIView):
    def delete(self, request, pk):
        rec = _open_record(request.user)
        deleted, _ = DailyActivity.objects.filter(pk=pk, record=rec).delete()   # own record only
        return Response(status=204 if deleted else 404)


ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".jpg", ".jpeg", ".png"}
MAX_BYTES = 5 * 1024 * 1024


class AttachmentUpload(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        rec = _open_record(request.user)
        act = DailyActivity.objects.filter(pk=pk, record=rec).first()
        f = request.FILES.get("file")
        if not act or not f:
            raise DomainError("NOT_FOUND", "Activity or file missing.", 404)
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXT:
            raise DomainError("FILE_TYPE", "Allowed types: PDF, DOCX, XLSX, JPG, PNG.")
        if f.size > MAX_BYTES:
            raise DomainError("FILE_SIZE", "File must be 5 MB or smaller.")
        # Production: sniff magic bytes (python-magic) and scan with ClamAV before saving.
        att = ActivityAttachment.objects.create(activity=act, file=f, original_name=f.name[:200])
        log(request, request.user, "activity.attachment_added", att.original_name)
        return Response({"id": att.pk}, status=201)


class Categories(APIView):
    def get(self, request):
        # Ensure a fresh production database always has usable categories, even if
        # the optional seed command was not run during deployment.
        defaults = ["Official Assignment", "Meeting", "Field Work", "Project Development", "Research",
                    "Training", "Administrative Work", "Inspection", "Documentation",
                    "Stakeholder Engagement", "Travel", "Other"]
        for name in defaults:
            ActivityCategory.objects.get_or_create(name=name)
        return Response(CategorySerializer(ActivityCategory.objects.filter(is_active=True), many=True).data)


# ---------- Admin ----------
class AdminDashboard(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_view_all", "accounts.attendance_view_scope"]

    def get(self, request):
        today = timezone.localdate()
        services.finalize_expired_open_records()
        staff = scoped_staff(request.user)
        recs = AttendanceRecord.objects.filter(user__in=staff, date=today)
        total, present = staff.count(), recs.count()
        checked_out = recs.filter(check_out_at__isnull=False).count()
        on_duty_ids = absence.on_official_duty(today) & set(staff.values_list("id", flat=True))
        on_leave_ids = (absence.on_approved_leave(today) | absence.on_recurring_leave(today)) & set(staff.values_list("id", flat=True))
        # Approved leave/duty removes a person from absence only when they have not
        # already checked in; avoid subtracting an already-present person twice.
        present_ids = set(recs.values_list("user_id", flat=True))
        excused_absences = (on_duty_ids | on_leave_ids) - present_ids
        working_day = absence.is_working_day(today)
        return Response({
            "is_holiday": absence.is_holiday(today), "is_working_day": working_day,
            "non_working_reason": absence.non_working_reason(today),
            "total_staff": total, "present": present,
            "late": recs.filter(check_in_status="late").count(),
            "checked_out": checked_out, "on_site": present - checked_out,
            "absent": max(total - present - len(excused_absences), 0) if working_day and not rules.checkin_is_open(timezone.localtime()) else 0, "official_duty": len(on_duty_ids),
            "on_leave": len(on_leave_ids),
            "early_departures": recs.filter(check_out_status="early_departure").count(),
            "exceptions": recs.filter(review_status="review_required").count(),
        })


class AdminLive(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_view_all", "accounts.attendance_view_scope"]

    def get(self, request):
        services.finalize_expired_open_records()
        qs = (AttendanceRecord.objects.filter(user__in=scoped_staff(request.user),
                                              date=timezone.localdate())
              .select_related("user", "user__department", "campus").order_by("-check_in_at"))
        if dept := request.query_params.get("department"):
            qs = qs.filter(user__department_id=dept)
        if st := request.query_params.get("status"):
            qs = qs.filter(check_in_status=st)
        return Response([{
            "id": r.pk, "name": r.user.get_full_name(), "ippis": r.user.ippis_number,
            "department": r.user.department.name if r.user.department_id else "",
            "check_in_at": r.check_in_at, "check_out_at": r.check_out_at,
            "status": r.check_in_status, "campus": r.campus.name,
            "review": r.review_status,
        } for r in qs[:200]])                   # paginate properly in production


class CampusViewSet(viewsets.ModelViewSet):
    queryset = Campus.objects.prefetch_related("geofences")
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.geofence_manage"]
    pagination_class = None

    def perform_update(self, s):
        old = CampusSerializer(self.get_object()).data
        obj = s.save()
        log(self.request, self.request.user, "campus.updated", obj.name, previous=old, new=s.data)


class GeofenceViewSet(viewsets.ModelViewSet):
    queryset = Geofence.objects.all()
    serializer_class = GeofenceSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.geofence_manage"]
    pagination_class = None

    def perform_create(self, s):
        obj = s.save()
        log(self.request, self.request.user, "geofence.created", f"{obj.name} at {obj.campus.name}", new=s.data)

    def perform_update(self, s):
        old = GeofenceSerializer(self.get_object()).data
        obj = s.save()
        log(self.request, self.request.user, "geofence.updated", f"{obj.name} at {obj.campus.name}", previous=old, new=s.data)

    def perform_destroy(self, instance):
        description = f"{instance.name} at {instance.campus.name}"
        instance.delete()
        log(self.request, self.request.user, "geofence.deleted", description)

# ---- Staff self-service: request a correction ----
class CorrectionRequest(APIView):
    def post(self, request):
        s = CorrectionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = s.validated_data["record"]
        if rec.user_id != request.user.id:
            raise DomainError("FORBIDDEN", "You can only request corrections on your own attendance.", 403)
        corr = s.save(requested_by=request.user)
        log(request, request.user, "attendance.correction_requested", f"record {rec.pk}", new=s.data)
        return Response(CorrectionSerializer(corr).data, status=201)


class MyCorrections(APIView):
    def get(self, request):
        qs = AttendanceCorrection.objects.filter(requested_by=request.user).order_by("-created_at")
        return Response(CorrectionSerializer(qs, many=True).data)


# ---- Admin: review queue ----
class CorrectionQueue(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_approve"]

    def get(self, request):
        qs = (AttendanceCorrection.objects.filter(status="pending", director_status="approved", requested_by__in=scoped_staff(request.user))
              .select_related("record", "requested_by").order_by("created_at"))
        return Response(CorrectionSerializer(qs, many=True).data)


class CorrectionDecide(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_approve"]

    def post(self, request, pk):
        corr = (AttendanceCorrection.objects.select_related("record")
                .filter(pk=pk, status="pending", director_status="approved", requested_by__in=scoped_staff(request.user)).first())
        if not corr:
            raise DomainError("NOT_FOUND", "Correction request not found or already decided.", 404)
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        old_value = getattr(corr.record, corr.field)
        if decision == "approved":
            setattr(corr.record, corr.field, corr.requested_value)
            if corr.field == "check_out_at":
                corr.record.check_out_status = "normal"
            corr.record.save()
        corr.status, corr.reviewed_by = decision, request.user
        corr.reviewed_at, corr.review_note = timezone.now(), request.data.get("note", "")[:500]
        corr.save()
        log(request, request.user, "attendance.correction_decided", decision,
            previous={"value": str(old_value)}, new={"correction": corr.pk, "decision": decision})
        return Response(CorrectionSerializer(corr).data)


# ---- Leave, official duty, holidays ----
class MyLeave(APIView):
    def get(self, request):
        return Response(LeaveSerializer(request.user.leave_records.select_related("director_reviewed_by", "approved_by").order_by("-created_at"), many=True).data)

    def post(self, request):
        active_kind, active = absence.active_approved_absence(request.user)
        if active:
            raise DomainError(
                "ACTIVE_REQUEST_EXISTS",
                f"You have approved {active_kind} until {active.end_date:%d %b %Y}. You cannot submit another leave or official-duty request until it ends or you are recalled.",
                409,
            )
        s = LeaveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = s.save(user=request.user)
        log(request, request.user, "leave.requested", rec.kind)
        send_email(
            "Leave request awaiting your approval",
            f"{request.user.get_full_name()} has submitted a {rec.get_kind_display()} request "
            f"from {rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y}.\n\n"
            "Please review it in NASRDA Staff Attendance.",
            notification_recipients("department_request_review", request.user.department),
        )
        return Response(LeaveSerializer(rec).data, status=201)


class MyOfficialDuty(APIView):
    """Staff self-service official-duty requests; approval happens in the admin queue."""
    def get(self, request):
        return Response(OfficialDutySerializer(request.user.official_duties.select_related("director_reviewed_by", "approved_by").order_by("-created_at"), many=True).data)

    def post(self, request):
        active_kind, active = absence.active_approved_absence(request.user)
        if active:
            raise DomainError(
                "ACTIVE_REQUEST_EXISTS",
                f"You have approved {active_kind} until {active.end_date:%d %b %Y}. You cannot submit another leave or official-duty request until it ends or you are recalled.",
                409,
            )
        s = OfficialDutySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rec = s.save(user=request.user)
        log(request, request.user, "official_duty.requested", rec.location)
        send_email(
            "Official-duty request awaiting your approval",
            f"{request.user.get_full_name()} has submitted an official-duty request at {rec.location} "
            f"from {rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y}.\n\n"
            "Please review it in NASRDA Staff Attendance.",
            notification_recipients("department_request_review", request.user.department),
        )
        return Response(OfficialDutySerializer(rec).data, status=201)


class MyRecurringLeave(APIView):
    """Staff-requested long-running part-time/recurring leave arrangement."""
    def get(self, request):
        schedules = request.user.recurring_leave_schedules.select_related("director_reviewed_by", "approved_by").order_by("-created_at")
        return Response(RecurringLeaveSerializer(schedules, many=True).data)

    def post(self, request):
        active_kind, active = absence.active_approved_absence(request.user)
        if active:
            raise DomainError(
                "ACTIVE_REQUEST_EXISTS",
                f"You have approved {active_kind} until {active.end_date:%d %b %Y}. You cannot submit another leave or official-duty request until it ends or you are recalled.",
                409,
            )
        serializer = RecurringLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rec = serializer.save(user=request.user)
        log(request, request.user, "recurring_leave.requested", "Part-time recurring leave schedule", new={"off_weekdays": rec.off_weekdays})
        send_email(
            "Recurring leave request awaiting your approval",
            f"{request.user.get_full_name()} has requested a recurring leave arrangement from "
            f"{rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y}. Please review it in NASRDA Staff Attendance.",
            notification_recipients("department_request_review", request.user.department),
        )
        return Response(RecurringLeaveSerializer(rec).data, status=201)


class DepartmentReviewQueue(APIView):
    """First-stage review: Directors see only pending requests from their department."""
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.department_request_review"]

    def get(self, request):
        if not request.user.department_id:
            return Response([])
        corrections = AttendanceCorrection.objects.filter(status="pending", director_status="pending", requested_by__department_id=request.user.department_id).select_related("requested_by")
        leave = LeaveRecord.objects.filter(status="pending", director_status="pending", user__department_id=request.user.department_id).select_related("user")
        duty = OfficialDuty.objects.filter(status="pending", director_status="pending", user__department_id=request.user.department_id).select_related("user")
        recurring_leave = RecurringLeaveSchedule.objects.filter(status="pending", director_status="pending", user__department_id=request.user.department_id).select_related("user")
        today = timezone.localdate()
        active_leave = LeaveRecord.objects.filter(status="approved", director_status="approved", user__department_id=request.user.department_id,
                                                  start_date__lte=today, end_date__gte=today, recall_return_date__isnull=True).select_related("user")
        active_duty = OfficialDuty.objects.filter(status="approved", director_status="approved", user__department_id=request.user.department_id,
                                                  start_date__lte=today, end_date__gte=today, recall_return_date__isnull=True).select_related("user")
        active_recurring_leave = RecurringLeaveSchedule.objects.filter(status="approved", director_status="approved", user__department_id=request.user.department_id,
                                                                        start_date__lte=today, end_date__gte=today, recall_return_date__isnull=True).select_related("user")
        return Response(
            [{"id": x.id, "type": "correction", "staff": x.requested_by.get_full_name(), "detail": f"{x.field} → {x.requested_value}: {x.reason}", "created_at": x.created_at} for x in corrections] +
            [{"id": x.id, "type": "leave", "staff": x.user.get_full_name(), "detail": f"{x.kind}: {x.start_date} → {x.end_date} · {x.reason}", "created_at": x.created_at} for x in leave] +
            [{"id": x.id, "type": "official-duty", "staff": x.user.get_full_name(), "detail": f"{x.location}: {x.start_date} → {x.end_date} · {x.reason}", "created_at": x.created_at} for x in duty] +
            [{"id": x.id, "type": "recurring-leave", "staff": x.user.get_full_name(), "detail": f"Recurring leave ({', '.join(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][day] for day in x.off_weekdays)} off): {x.start_date} → {x.end_date} · {x.reason}", "created_at": x.created_at} for x in recurring_leave] +
            [{"id": x.id, "type": "leave", "staff": x.user.get_full_name(), "detail": f"Approved leave: {x.kind} · {x.start_date} → {x.end_date}", "recallable": True, "end_date": str(x.end_date), "created_at": x.created_at} for x in active_leave] +
            [{"id": x.id, "type": "official-duty", "staff": x.user.get_full_name(), "detail": f"Approved official duty: {x.location} · {x.start_date} → {x.end_date}", "recallable": True, "end_date": str(x.end_date), "created_at": x.created_at} for x in active_duty]
            + [{"id": x.id, "type": "recurring-leave", "staff": x.user.get_full_name(), "detail": f"Approved recurring leave ({', '.join(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][day] for day in x.off_weekdays)} off): {x.start_date} → {x.end_date}", "recallable": True, "end_date": str(x.end_date), "created_at": x.created_at} for x in active_recurring_leave]
        )


class DepartmentReviewDecide(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.department_request_review"]

    def post(self, request, kind, pk):
        models = {"correction": (AttendanceCorrection, "requested_by"), "leave": (LeaveRecord, "user"), "official-duty": (OfficialDuty, "user"), "recurring-leave": (RecurringLeaveSchedule, "user")}
        if kind not in models:
            raise DomainError("INVALID", "Unknown request type.")
        model, owner = models[kind]
        item = model.objects.select_related(owner).filter(pk=pk, status="pending", director_status="pending", **{f"{owner}__department_id": request.user.department_id}).first()
        if not item:
            raise DomainError("NOT_FOUND", "Request not found or already reviewed.", 404)
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        item.director_status, item.director_reviewed_by, item.director_reviewed_at = decision, request.user, timezone.now()
        item.save(update_fields=["director_status", "director_reviewed_by", "director_reviewed_at"])
        log(request, request.user, f"{kind}.director_{decision}", new={"request": item.pk})
        staff = getattr(item, owner)
        if decision == "approved":
            send_email(
                f"{kind.replace('-', ' ').title()} request awaiting administrator approval",
                f"{staff.get_full_name()}'s request has been approved by the department director and is awaiting final approval.",
                notification_recipients("attendance_approve"),
            )
        else:
            send_email(
                f"Your {kind.replace('-', ' ')} request was rejected",
                "Your department director has rejected your request. Please sign in to NASRDA Staff Attendance for details.",
                [staff.email],
            )
        return Response({"status": decision})


class LeaveApprovalViewSet(viewsets.ModelViewSet):
    """Admin queue: list pending, then POST .../{id}/decide/."""
    queryset = LeaveRecord.objects.select_related("user").order_by("-created_at")
    serializer_class = LeaveSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_approve"]
    http_method_names = ["get", "post"]
    pagination_class = None

    def get_permissions(self):
        # Directors are allowed only to view the active-recall list and perform a
        # recall; all normal final approval endpoints remain administrator-only.
        if self.action == "recall" or (self.action == "list" and self.request.query_params.get("include_active") == "true"):
            return [IsAuthenticated(), CanRecallDepartmentRequest()]
        return super().get_permissions()

    def get_queryset(self):
        recall_flow = self.action == "recall" or self.request.query_params.get("include_active") == "true"
        if recall_flow and not self.request.user.has_perm("accounts.attendance_approve"):
            qs = super().get_queryset().filter(user__department_id=self.request.user.department_id, director_status="approved")
        else:
            qs = super().get_queryset().filter(user__in=scoped_staff(self.request.user), director_status="approved")
        if self.request.query_params.get("include_active") == "true":
            today = timezone.localdate()
            qs = qs.filter(Q(status="pending") | Q(status="approved", start_date__lte=today, end_date__gte=today,
                                                   recall_return_date__isnull=True))
        elif status_value := self.request.query_params.get("status"):
            qs = qs.filter(status=status_value)
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        rec = self.get_object()
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        rec.status, rec.approved_by, rec.approved_at = decision, request.user, timezone.now()
        rec.save()
        log(request, request.user, "leave.decided", decision, new={"leave": rec.pk})
        send_email(
            f"Your leave request was {decision}",
            f"Your leave request from {rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y} was {decision} by {request.user.get_full_name()}.",
            [rec.user.email],
        )
        return Response(LeaveSerializer(rec).data)

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        rec = self.get_object()
        try:
            return_date = date.fromisoformat(str(request.data.get("return_date", "")))
        except ValueError:
            raise DomainError("INVALID_RECALL_DATE", "Choose a valid return-to-duty date.")
        reason = str(request.data.get("reason", "")).strip()
        today = timezone.localdate()
        if not reason:
            raise DomainError("RECALL_REASON_REQUIRED", "Provide a reason for the recall.")
        if rec.status != "approved" or rec.start_date > today or rec.end_date < today or rec.recall_return_date:
            raise DomainError("RECALL_UNAVAILABLE", "Only a currently active, approved leave request can be recalled.", 409)
        if return_date < today or return_date > rec.end_date:
            raise DomainError("INVALID_RECALL_DATE", "The return-to-duty date must be today through the request end date.")
        rec.status, rec.recalled_by, rec.recalled_at, rec.recall_return_date, rec.recall_reason = "recalled", request.user, timezone.now(), return_date, reason
        rec.save(update_fields=["status", "recalled_by", "recalled_at", "recall_return_date", "recall_reason"])
        log(request, request.user, "leave.recalled", f"{rec.user.get_full_name()} recalled from leave", new={"leave": rec.pk, "return_date": str(return_date), "reason": reason})
        return Response(LeaveSerializer(rec).data)


class OfficialDutyViewSet(viewsets.ModelViewSet):
    queryset = OfficialDuty.objects.select_related("user").order_by("-created_at")
    serializer_class = OfficialDutySerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_approve"]
    pagination_class = None

    def get_permissions(self):
        # Directors are allowed only to view the active-recall list and perform a
        # recall; all normal final approval endpoints remain administrator-only.
        if self.action == "recall" or (self.action == "list" and self.request.query_params.get("include_active") == "true"):
            return [IsAuthenticated(), CanRecallDepartmentRequest()]
        return super().get_permissions()

    def get_queryset(self):
        recall_flow = self.action == "recall" or self.request.query_params.get("include_active") == "true"
        if recall_flow and not self.request.user.has_perm("accounts.attendance_approve"):
            qs = super().get_queryset().filter(user__department_id=self.request.user.department_id, director_status="approved")
        else:
            qs = super().get_queryset().filter(user__in=scoped_staff(self.request.user), director_status="approved")
        if self.request.query_params.get("include_active") == "true":
            today = timezone.localdate()
            qs = qs.filter(Q(status="pending") | Q(status="approved", start_date__lte=today, end_date__gte=today,
                                                   recall_return_date__isnull=True))
        elif status_value := self.request.query_params.get("status"):
            qs = qs.filter(status=status_value)
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        rec = self.get_object()
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        rec.status, rec.approved_by, rec.approved_at = decision, request.user, timezone.now()
        rec.save()
        log(request, request.user, "official_duty.decided", decision, new={"duty": rec.pk})
        send_email(
            f"Your official-duty request was {decision}",
            f"Your official-duty request from {rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y} was {decision} by {request.user.get_full_name()}.",
            [rec.user.email],
        )
        return Response(OfficialDutySerializer(rec).data)

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        rec = self.get_object()
        try:
            return_date = date.fromisoformat(str(request.data.get("return_date", "")))
        except ValueError:
            raise DomainError("INVALID_RECALL_DATE", "Choose a valid return-to-duty date.")
        reason = str(request.data.get("reason", "")).strip()
        today = timezone.localdate()
        if not reason:
            raise DomainError("RECALL_REASON_REQUIRED", "Provide a reason for the recall.")
        if rec.status != "approved" or rec.start_date > today or rec.end_date < today or rec.recall_return_date:
            raise DomainError("RECALL_UNAVAILABLE", "Only a currently active, approved official-duty request can be recalled.", 409)
        if return_date < today or return_date > rec.end_date:
            raise DomainError("INVALID_RECALL_DATE", "The return-to-duty date must be today through the request end date.")
        rec.status, rec.recalled_by, rec.recalled_at, rec.recall_return_date, rec.recall_reason = "recalled", request.user, timezone.now(), return_date, reason
        rec.save(update_fields=["status", "recalled_by", "recalled_at", "recall_return_date", "recall_reason"])
        log(request, request.user, "official_duty.recalled", f"{rec.user.get_full_name()} recalled from official duty", new={"official_duty": rec.pk, "return_date": str(return_date), "reason": reason})
        return Response(OfficialDutySerializer(rec).data)


class RecurringLeaveViewSet(viewsets.ModelViewSet):
    """Administrator approval and Director-scoped recall of part-time leave schedules."""
    queryset = RecurringLeaveSchedule.objects.select_related("user").order_by("-created_at")
    serializer_class = RecurringLeaveSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_approve"]
    http_method_names = ["get", "post"]
    pagination_class = None

    def get_permissions(self):
        if self.action == "recall" or (self.action == "list" and self.request.query_params.get("include_active") == "true"):
            return [IsAuthenticated(), CanRecallDepartmentRequest()]
        return super().get_permissions()

    def get_queryset(self):
        recall_flow = self.action == "recall" or self.request.query_params.get("include_active") == "true"
        if recall_flow and not self.request.user.has_perm("accounts.attendance_approve"):
            qs = super().get_queryset().filter(user__department_id=self.request.user.department_id, director_status="approved")
        else:
            qs = super().get_queryset().filter(user__in=scoped_staff(self.request.user), director_status="approved")
        if self.request.query_params.get("include_active") == "true":
            # Include approved future arrangements as well: a Director/Admin may end
            # one before it begins, and the schedule becomes recalled immediately.
            qs = qs.filter(Q(status="pending") | Q(status="approved", end_date__gte=timezone.localdate(), recall_return_date__isnull=True))
        elif status_value := self.request.query_params.get("status"):
            qs = qs.filter(status=status_value)
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        rec = self.get_object()
        decision = request.data.get("decision")
        if decision not in ("approved", "rejected"):
            raise DomainError("INVALID", "decision must be 'approved' or 'rejected'.")
        rec.status, rec.approved_by, rec.approved_at = decision, request.user, timezone.now()
        rec.save(update_fields=["status", "approved_by", "approved_at"])
        log(request, request.user, "recurring_leave.decided", decision, new={"recurring_leave": rec.pk})
        send_email(
            f"Your recurring leave request was {decision}",
            f"Your recurring leave arrangement from {rec.start_date:%d %b %Y} to {rec.end_date:%d %b %Y} was {decision} by {request.user.get_full_name()}.",
            [rec.user.email],
        )
        return Response(RecurringLeaveSerializer(rec).data)

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        rec = self.get_object()
        try:
            return_date = date.fromisoformat(str(request.data.get("return_date", "")))
        except ValueError:
            raise DomainError("INVALID_RECALL_DATE", "Choose a valid return-to-duty date.")
        reason = str(request.data.get("reason", "")).strip()
        today = timezone.localdate()
        if not reason:
            raise DomainError("RECALL_REASON_REQUIRED", "Provide a reason for the recall.")
        if rec.status != "approved" or rec.end_date < today or rec.recall_return_date:
            raise DomainError("RECALL_UNAVAILABLE", "Only an unexpired, approved recurring leave schedule can be recalled.", 409)
        if return_date < today or return_date > rec.end_date:
            raise DomainError("INVALID_RECALL_DATE", "The return-to-duty date must be today through the schedule end date.")
        rec.status, rec.recalled_by, rec.recalled_at = "recalled", request.user, timezone.now()
        rec.recall_return_date, rec.recall_reason = return_date, reason
        rec.save(update_fields=["status", "recalled_by", "recalled_at", "recall_return_date", "recall_reason"])
        log(request, request.user, "recurring_leave.recalled", f"{rec.user.get_full_name()} recalled from recurring leave", new={"recurring_leave": rec.pk, "return_date": str(return_date), "reason": reason})
        send_email(
            "Your recurring leave arrangement was recalled",
            f"Your recurring leave arrangement has been recalled. Return to duty from {return_date:%d %b %Y}. Reason: {reason}",
            [rec.user.email],
        )
        return Response(RecurringLeaveSerializer(rec).data)


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.order_by("date")
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.settings_manage"]
    pagination_class = None


# ---- Anomaly review queue (spec §11, §41) ----
class ReviewQueue(APIView):
    """Records currently flagged review_required, for the admin to clear or confirm."""
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_correct", "accounts.attendance_view_all"]

    def get(self, request):
        qs = (AttendanceRecord.objects.filter(review_status="review_required", user__in=scoped_staff(request.user))
              .select_related("user", "campus").order_by("-date")[:100])
        return Response([{
            "id": r.pk, "staff": r.user.get_full_name(), "date": r.date, "campus": r.campus.name,
            "flags": r.flags,
        } for r in qs])


class ReviewDecide(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.attendance_correct", "accounts.attendance_view_all"]

    def post(self, request, pk):
        rec = AttendanceRecord.objects.filter(pk=pk).first()
        if not rec:
            raise DomainError("NOT_FOUND", "Record not found.", 404)
        decision = request.data.get("decision")           # "normal" or "confirmed_issue"
        if decision not in ("normal", "confirmed_issue"):
            raise DomainError("INVALID", "decision must be 'normal' or 'confirmed_issue'.")
        rec.review_status = "normal" if decision == "normal" else "review_required"
        rec.remarks = request.data.get("note", "")[:500]
        rec.save(update_fields=["review_status", "remarks"])
        # Never auto-punish (spec §41): a "confirmed_issue" only leaves a note for HR to act on manually.
        log(request, request.user, "attendance.review_decision", decision, new={"record": pk, "decision": decision})
        return Response({"ok": True})


MIME = {"csv": "text/csv",
       "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
       "pdf": "application/pdf"}


class ReportScope(APIView):
    """Return only the organisation scope the current report user may select."""
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.reports_export"]

    def get(self, request):
        if request.user.has_perm("accounts.attendance_view_all"):
            departments = Department.objects.prefetch_related("campuses").order_by("name")
            return Response({
                "all_access": True,
                "campuses": list(Campus.objects.filter(is_active=True).values("id", "name")),
                "departments": [{"id": item.id, "name": item.name, "campus_ids": list(item.campuses.values_list("id", flat=True))} for item in departments],
            })
        if not request.user.has_perm("accounts.attendance_view_scope") or not request.user.department_id or not request.user.primary_campus_id:
            raise DomainError("REPORT_SCOPE", "A director must have an assigned primary campus and department to generate reports.", 403)
        return Response({
            "all_access": False,
            "campuses": [{"id": request.user.primary_campus_id, "name": request.user.primary_campus.name}],
            "departments": [{"id": request.user.department_id, "name": request.user.department.name, "campus_ids": [request.user.primary_campus_id]}],
        })


class ReportExport(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.reports_export"]

    def get(self, request):
        # `format` is reserved by Django REST Framework for renderer negotiation.
        # Use `output_format` for the downloadable file type instead.
        report, fmt = request.query_params.get("report", "daily"), request.query_params.get("output_format", "csv")
        if fmt not in MIME:
            raise DomainError("UNKNOWN_FORMAT", "format must be csv, xlsx or pdf.")
        department, campus = request.query_params.get("department"), request.query_params.get("campus")
        # A Director may export reports only for their assigned campus and department.
        # Do not trust either query parameter supplied by the browser.
        if not request.user.has_perm("accounts.attendance_view_all"):
            if not request.user.has_perm("accounts.attendance_view_scope") or not request.user.department_id or not request.user.primary_campus_id:
                raise DomainError("REPORT_SCOPE", "A director must have an assigned primary campus and department to generate reports.", 403)
            department = str(request.user.department_id)
            campus = str(request.user.primary_campus_id)

        if report == "monthly":
            month = request.query_params.get("month", timezone.localdate().strftime("%Y-%m"))
            y, m = month.split("-")
            rows, title = rpt.monthly_summary_rows(int(y), int(m), department, campus)
            filename_period = datetime.strptime(month, "%Y-%m").strftime("%b-%Y")
        else:
            date = request.query_params.get("date", str(timezone.localdate()))
            builder = rpt.REPORT_BUILDERS.get(report)
            if not builder:
                raise DomainError("UNKNOWN_REPORT", "Unknown report type.")
            rows, title = builder(date, department, campus)
            filename_period = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y")

        body = {"csv": rpt.to_csv, "xlsx": lambda r: rpt.to_xlsx(r, title),
               "pdf": lambda r: rpt.to_pdf(r, title, request.user.get_full_name())}[fmt](rows)
        log(request, request.user, "reports.exported", f"{report}.{fmt}")
        resp = HttpResponse(body, content_type=MIME[fmt])
        def filename_part(value):
            import re
            return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
        report_name = {"monthly": "monthly-attendance-summary", "daily": "daily-attendance"}.get(report, report)
        campus_name = Campus.objects.filter(pk=campus).values_list("name", flat=True).first() if campus else "All-Campuses"
        department_name = Department.objects.filter(pk=department).values_list("name", flat=True).first() if department else "All-Departments"
        filename = f"{report_name}-{filename_part(campus_name or 'All-Campuses')}-{filename_part(department_name or 'All-Departments')}-{filename_period}.{fmt}"
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
