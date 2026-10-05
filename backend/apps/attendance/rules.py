from datetime import datetime, time, timedelta

from apps.core.models import get_setting


def _t(s):
    h, m = map(int, s.split(":"))
    return time(h, m)


def _at(local_dt, hhmm):
    return datetime.combine(local_dt.date(), _t(hhmm), tzinfo=local_dt.tzinfo)


def classify_check_in(local_dt):
    return "late" if local_dt.time() >= _t(get_setting("checkin_late_after")) else "on_time"


def checkin_is_open(local_dt):
    return local_dt.time() < _t(get_setting("checkin_closes_after"))


def checkout_time_for(user):
    return get_setting("nursing_mother_checkout_after") if user.is_nursing_mother else get_setting("checkout_allowed_after")


def classify_check_out(local_dt, user):
    """Returns (status, overtime_minutes)."""
    end_time = get_setting("nursing_mother_checkout_after") if user.is_nursing_mother else get_setting("work_end")
    end = _at(local_dt, end_time)
    if local_dt < end:
        return "early_departure", 0
    over = int((local_dt - end).total_seconds() // 60)
    return "normal", (over if over > get_setting("overtime_after_minutes") else 0)


def checkout_is_open(local_dt, user):
    return local_dt.time() >= _t(checkout_time_for(user))
