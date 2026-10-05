from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, ippis_number, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        user = self.model(ippis_number=ippis_number, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, ippis_number, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(ippis_number, password, **extra)


class User(AbstractUser):
    """IPPIS number is the login and the canonical staff identifier (PMS-ready)."""
    username = None
    ippis_number = models.CharField(max_length=32, unique=True)
    file_number = models.CharField(max_length=32, blank=True)
    middle_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to="staff_photos/", blank=True)

    department = models.ForeignKey("org.Department", null=True, blank=True, on_delete=models.PROTECT)
    designation = models.CharField(max_length=120, blank=True)
    grade_level = models.CharField(max_length=10, blank=True)
    employment_status = models.CharField(max_length=30, default="permanent")
    is_nursing_mother = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True)
    mfa_confirmed = models.BooleanField(default=False)

    class CampusPolicy(models.TextChoices):
        ONE = "one", "One campus only"
        APPROVED = "approved", "Approved campuses"
        ANY = "any", "Any NASRDA campus"

    primary_campus = models.ForeignKey("org.Campus", null=True, blank=True, on_delete=models.PROTECT,
                                       related_name="primary_staff")
    secondary_campuses = models.ManyToManyField("org.Campus", blank=True, related_name="secondary_staff")
    campus_policy = models.CharField(max_length=10, choices=CampusPolicy.choices, default=CampusPolicy.ONE)

    USERNAME_FIELD = "ippis_number"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]
    objects = UserManager()

    class Meta:
        # spec §59 permission codenames; assign to Groups in the seed command
        permissions = [
            ("attendance_view_all", "View attendance for all staff"),
            ("attendance_view_scope", "View attendance for own department"),
            ("attendance_correct", "Correct attendance"),
            ("attendance_approve", "Approve corrections"),
            ("staff_manage", "Create/edit/disable staff"),
            ("device_manage", "Approve/revoke devices"),
            ("geofence_manage", "Manage campuses and geofences"),
            ("reports_export", "Generate and export reports"),
            ("audit_view", "View audit logs"),
            ("settings_manage", "Manage system settings"),
            ("department_request_review", "Review requests for own department"),
        ]

    def allowed_campus_ids(self):
        from apps.org.models import Campus
        if self.campus_policy == self.CampusPolicy.ANY:
            return list(Campus.objects.filter(is_active=True).values_list("id", flat=True))
        ids = set()
        if self.primary_campus_id:
            ids.add(self.primary_campus_id)
        if self.campus_policy == self.CampusPolicy.APPROVED:
            ids.update(self.secondary_campuses.values_list("id", flat=True))
        return list(ids)
