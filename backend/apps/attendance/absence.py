from django.utils import timezone
from django.db.models import Q

from .models import Holiday, LeaveRecord, OfficialDuty, RecurringLeaveSchedule


def is_holiday(date):
    return Holiday.objects.filter(date=date).exclude(kind="special_working").exists()


def non_working_reason(date):
    """Return why the office is closed, or None when attendance is required."""
    holiday = Holiday.objects.filter(date=date).first()
    if holiday:
        if holiday.kind == Holiday.Kind.SPECIAL_WORKING:
            return None
        return f"{holiday.name} is a non-working holiday."
    if date.weekday() >= 5:
        return "It is a weekend."
    return None


def is_working_day(date):
    return non_working_reason(date) is None


def on_approved_leave(date):
    return set(LeaveRecord.objects.filter(status__in=["approved", "recalled"], start_date__lte=date,
                                          end_date__gte=date)
               .filter(Q(recall_return_date__isnull=True) | Q(recall_return_date__gt=date))
               .values_list("user_id", flat=True))


def on_official_duty(date):
    return set(OfficialDuty.objects.filter(status__in=["approved", "recalled"], start_date__lte=date,
                                           end_date__gte=date)
               .filter(Q(recall_return_date__isnull=True) | Q(recall_return_date__gt=date))
               .values_list("user_id", flat=True))


def on_recurring_leave(date):
    """Staff excused by an approved part-time schedule on this weekday only."""
    schedules = (RecurringLeaveSchedule.objects
                 .filter(status__in=["approved", "recalled"], start_date__lte=date, end_date__gte=date)
                 .filter(Q(recall_return_date__isnull=True) | Q(recall_return_date__gt=date))
                 .values_list("user_id", "off_weekdays"))
    return {user_id for user_id, off_days in schedules if date.weekday() in (off_days or [])}


def active_approved_absence(user, date=None):
    """Return the active approved leave/duty record that currently prevents a new request."""
    date = date or timezone.localdate()
    active = Q(recall_return_date__isnull=True) | Q(recall_return_date__gt=date)
    # Recall changes the request state immediately. A recalled record may still
    # excuse attendance until its selected return date, but it must no longer
    # prevent the staff member from submitting their next request.
    # A future approved request also reserves the staff member's next leave/duty
    # period, so it blocks another request before its start date as well.
    leave = LeaveRecord.objects.filter(user=user, status="approved", end_date__gte=date).filter(active).first()
    if leave:
        return "leave", leave
    duty = OfficialDuty.objects.filter(user=user, status="approved", end_date__gte=date).filter(active).first()
    if duty:
        return "official duty", duty
    schedule = RecurringLeaveSchedule.objects.filter(user=user, status="approved", end_date__gte=date).filter(active).first()
    return ("recurring leave schedule", schedule) if schedule else (None, None)
