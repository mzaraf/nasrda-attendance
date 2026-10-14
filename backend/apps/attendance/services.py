from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import client_ip, log
from apps.core.errors import DomainError
from apps.core.models import get_setting
from . import absence, geo, rules
from .models import AttendanceLocation, AttendanceRecord, FaceProfile, FaceVerification


def finalize_expired_open_records(now=None):
    """Close records left open beyond 11:59 PM as early closures.

    This runs whenever attendance data is read or written, so it does not depend on a
    browser remaining open overnight. A scheduled job can call it too if configured.
    """
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    expired = AttendanceRecord.objects.filter(date__lt=local_now.date(), check_out_at__isnull=True)
    for record in expired.iterator():
        closing_local = datetime.combine(record.date, time(23, 59, 59), tzinfo=local_now.tzinfo)
        record.check_out_at = closing_local
        record.check_out_status = AttendanceRecord.OutStatus.EARLY_CLOSURE
        record.overtime_minutes = 0
        record.remarks = (record.remarks + "\n" if record.remarks else "") + "Automatically closed at 11:59 PM because no check-out was recorded."
        record.save(update_fields=["check_out_at", "check_out_status", "overtime_minutes", "remarks"])


def _verify_location(request, user, data, action):
    lat, lng, acc = data["latitude"], data["longitude"], data["accuracy"]
    if acc > get_setting("min_accuracy_m"):
        log(request, user, "location.accuracy_insufficient", f"{action}: accuracy {acc:.0f}m")
        raise DomainError("ACCURACY_INSUFFICIENT",
                          "Your location accuracy is currently insufficient. "
                          "Please move to an open area and try again.")
    campus, dist = geo.resolve_campus(user, lat, lng)
    if not campus:
        log(request, user, "geofence.violation", f"{action} outside geofence",
            new={"lat": lat, "lng": lng, "accuracy": acc})
        raise DomainError("OUTSIDE_GEOFENCE", "You are outside the NASRDA authorized attendance area.", 403)

    flags = []
    if acc < 1:
        flags.append("suspiciously_perfect_accuracy")
    prev = (AttendanceLocation.objects.filter(record__user=user).order_by("-recorded_at").first())
    if prev:
        secs = max((timezone.now() - prev.recorded_at).total_seconds(), 1)
        if geo.haversine_m(prev.latitude, prev.longitude, lat, lng) / secs > get_setting("max_speed_mps"):
            flags.append("impossible_location_jump")
    return campus, dist, flags


def _evidence(request, record, event, data, campus, dist, device, method, flags, now):
    return AttendanceLocation.objects.create(
        record=record, event=event, latitude=data["latitude"], longitude=data["longitude"],
        accuracy_m=data["accuracy"], inside_geofence=True, distance_m=dist, campus=campus,
        device=device, auth_method=method, ip_address=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300], flags=flags, recorded_at=now)


def _require_face_verification(request, user, verification_id, action):
    if not get_setting("require_face_verification"):
        return None, "password_only"
    profile = FaceProfile.objects.filter(user=user, status="active").first()
    if not profile:
        raise DomainError("FACE_ENROLLMENT_REQUIRED", "Set up face verification before recording attendance.", 409)
    if not verification_id:
        raise DomainError("FACE_VERIFICATION_REQUIRED", "Complete face verification before recording attendance.", 403)
    with transaction.atomic():
        result = FaceVerification.objects.select_for_update().filter(
            pk=verification_id, user=user, action=action, status="success", used_at__isnull=True,
            expires_at__gte=timezone.now(),
        ).first()
        if not result:
            raise DomainError("FACE_VERIFICATION_EXPIRED", "Face verification expired. Please verify again.", 403)
        result.used_at = timezone.now()
        result.save(update_fields=["used_at"])
    profile.last_verified_at = result.used_at
    profile.save(update_fields=["last_verified_at"])
    return None, "face_verification"


def check_in(request, user, data):
    now = timezone.now()
    local = timezone.localtime(now)
    finalize_expired_open_records(now)
    if reason := absence.non_working_reason(local.date()):
        raise DomainError("NON_WORKING_DAY", f"Attendance is not required today: {reason}", 403)
    if not rules.checkin_is_open(local):
        raise DomainError("CHECKIN_CLOSED", f"Check-in closed at {get_setting('checkin_closes_after')}. You are recorded as absent for today.", 403)
    device, method = _require_face_verification(request, user, data.get("face_verification_id"), "check-in")
    campus, dist, flags = _verify_location(request, user, data, "check-in")

    # SERVER time: the only time we trust
    try:
        with transaction.atomic():
            record = AttendanceRecord.objects.create(
                user=user, date=local.date(), campus=campus, check_in_at=now,
                check_in_status=rules.classify_check_in(local), flags=flags,
                review_status="review_required" if flags else "normal")
    except IntegrityError:                      # DB-level duplicate protection
        raise DomainError("ALREADY_CHECKED_IN", "You have already checked in today.", 409)

    _evidence(request, record, "in", data, campus, dist, device, method, flags, now)
    log(request, user, "attendance.check_in", f"{campus.name} {record.check_in_status}",
        new={"record": record.pk, "flags": flags})
    return record


def check_out(request, user, data):
    now = timezone.now()
    finalize_expired_open_records(now)
    local = timezone.localtime(now)
    checkout_after = rules.checkout_time_for(user)
    if not rules.checkout_is_open(local, user):
        raise DomainError("CHECKOUT_NOT_OPEN",
                          f"Check-out opens at {checkout_after}.", 403)
    device, method = _require_face_verification(request, user, data.get("face_verification_id"), "check-out")
    campus, dist, flags = _verify_location(request, user, data, "check-out")

    now = timezone.now()
    local = timezone.localtime(now)
    with transaction.atomic():
        record = (AttendanceRecord.objects.select_for_update()
                  .filter(user=user, date=local.date()).first())
        if not record:
            raise DomainError("NOT_CHECKED_IN", "You have not checked in today.", 409)
        if record.check_out_at:
            raise DomainError("ALREADY_CHECKED_OUT", "You have already checked out today.", 409)
        if not record.activities.exists():          # spec §18: no checkout without activities
            raise DomainError("ACTIVITY_REQUIRED",
                              "Please record at least one activity before checking out.")
        status, overtime = rules.classify_check_out(local, user)
        record.check_out_at, record.check_out_status = now, status
        record.overtime_minutes, record.activity_report_status = overtime, "submitted"
        if flags:
            record.flags = list(set(record.flags) | set(flags))
            record.review_status = "review_required"
        record.save()
        _evidence(request, record, "out", data, campus, dist, device, method, flags, now)
    log(request, user, "attendance.check_out", f"{status}", new={"record": record.pk})
    return record
