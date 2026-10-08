from django.conf import settings
from django.db import models
from django.db.models import F, Q


class AttendanceRecord(models.Model):
    class InStatus(models.TextChoices):
        ON_TIME = "on_time"
        LATE = "late"

    class OutStatus(models.TextChoices):
        NORMAL = "normal"
        EARLY = "early_departure"
        EARLY_CLOSURE = "early_closure"
        MISSED = "missed_checkout"

    class Review(models.TextChoices):
        NORMAL = "normal"
        REVIEW = "review_required"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()                                   # local (Africa/Lagos) date, server-derived
    campus = models.ForeignKey("org.Campus", on_delete=models.PROTECT)
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    check_in_status = models.CharField(max_length=10, choices=InStatus.choices)
    check_out_status = models.CharField(max_length=20, choices=OutStatus.choices, blank=True)
    overtime_minutes = models.PositiveIntegerField(default=0)
    activity_report_status = models.CharField(max_length=12, default="pending")
    review_status = models.CharField(max_length=16, choices=Review.choices, default=Review.NORMAL)
    flags = models.JSONField(default=list, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="uniq_attendance_per_user_day"),
            models.CheckConstraint(
                check=Q(check_out_at__isnull=True) | Q(check_out_at__gte=F("check_in_at")),
                name="checkout_after_checkin"),
        ]
        indexes = [models.Index(fields=["date", "campus"]), models.Index(fields=["user", "-date"])]

    @property
    def duration_minutes(self):
        return int((self.check_out_at - self.check_in_at).total_seconds() // 60) if self.check_out_at else None


class AttendanceLocation(models.Model):
    """One row per check-in / check-out event: the evidence behind the record."""
    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="locations")
    event = models.CharField(max_length=3, choices=[("in", "in"), ("out", "out")])
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_m = models.FloatField()
    inside_geofence = models.BooleanField()
    distance_m = models.FloatField(null=True)
    campus = models.ForeignKey("org.Campus", on_delete=models.PROTECT)
    device = models.ForeignKey("devices.RegisteredDevice", null=True, on_delete=models.SET_NULL)
    auth_method = models.CharField(max_length=20)            # passkey | password_only
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=300, blank=True)
    flags = models.JSONField(default=list, blank=True)
    recorded_at = models.DateTimeField()


class ActivityCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class DailyActivity(models.Model):
    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="activities")
    category = models.ForeignKey(ActivityCategory, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, default="completed")
    output = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ActivityAttachment(models.Model):
    activity = models.ForeignKey(DailyActivity, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="activity_docs/%Y/%m/")
    original_name = models.CharField(max_length=200)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class AttendanceCorrection(models.Model):
    class DirectorReview(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"
    class Field(models.TextChoices):
        CHECK_IN = "check_in_at"
        CHECK_OUT = "check_out_at"

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="corrections")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="correction_requests")
    field = models.CharField(max_length=20, choices=Field.choices)
    requested_value = models.DateTimeField()
    reason = models.TextField()
    supporting_document = models.FileField(upload_to="corrections/%Y/%m/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    director_status = models.CharField(max_length=10, choices=DirectorReview.choices, default=DirectorReview.PENDING)
    director_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                              on_delete=models.SET_NULL, related_name="correction_director_reviews")
    director_reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="correction_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LeaveRecord(models.Model):
    class Kind(models.TextChoices):
        ANNUAL = "annual"; SICK = "sick"; CASUAL = "casual"; MATERNITY = "maternity"; PATERNITY = "paternity"; TRAINING = "training"; STUDY = "study"; CONFERENCE = "conference"
        TRAVEL = "official_travel"; PERMISSION = "permission"; OTHER = "other"

    class Status(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"; RECALLED = "recalled"
    class DirectorReview(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_records")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    director_status = models.CharField(max_length=10, choices=DirectorReview.choices, default=DirectorReview.PENDING)
    director_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                              on_delete=models.SET_NULL, related_name="leave_director_reviews")
    director_reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="leave_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    recalled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="leave_recalls")
    recalled_at = models.DateTimeField(null=True, blank=True)
    recall_return_date = models.DateField(null=True, blank=True)
    recall_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OfficialDuty(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"; RECALLED = "recalled"
    class DirectorReview(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="official_duties")
    location = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    supporting_document = models.FileField(upload_to="official_duty/%Y/%m/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    director_status = models.CharField(max_length=10, choices=DirectorReview.choices, default=DirectorReview.PENDING)
    director_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                              on_delete=models.SET_NULL, related_name="duty_director_reviews")
    director_reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="duty_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    recalled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="duty_recalls")
    recalled_at = models.DateTimeField(null=True, blank=True)
    recall_return_date = models.DateField(null=True, blank=True)
    recall_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RecurringLeaveSchedule(models.Model):
    """Long-running part-time arrangement with selected weekly off days."""
    class Status(models.TextChoices):
        PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"; RECALLED = "recalled"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recurring_leave_schedules")
    start_date = models.DateField()
    end_date = models.DateField()
    # ISO weekday numbers: Monday=0 through Sunday=6.
    off_weekdays = models.JSONField(default=list)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    director_status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    director_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recurring_leave_director_reviews")
    director_reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recurring_leave_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    recalled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recurring_leave_recalls")
    recalled_at = models.DateTimeField(null=True, blank=True)
    recall_return_date = models.DateField(null=True, blank=True)
    recall_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Holiday(models.Model):
    class Kind(models.TextChoices):
        PUBLIC = "public"; NASRDA = "nasrda"; SPECIAL_WORKING = "special_working"; NON_WORKING = "non_working"

    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PUBLIC)
