from django.db import models

DEFAULTS = {
    "work_start": "08:00",
    "checkin_late_after": "09:30",
    "checkin_closes_after": "12:00",
    "work_end": "16:00",
    "checkout_allowed_after": "16:30",
    "nursing_mother_checkout_after": "14:00",
    "grace_minutes": 10,
    "overtime_after_minutes": 30,    # minutes beyond work_end before overtime counts
    "min_accuracy_m": 100,           # reject GPS fixes worse than this
    "require_passkey": True,
    "max_devices": 1,
    "device_approval_required": False,
    "max_speed_mps": 70,             # ~250 km/h; faster implied movement is flagged
}


class SystemSetting(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


def get_setting(key):
    row = SystemSetting.objects.filter(key=key).values_list("value", flat=True).first()
    return DEFAULTS[key] if row is None else row
