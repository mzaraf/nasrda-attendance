from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


ROLE_PERMISSIONS = {
    "Administrator": [
        "attendance_view_all", "attendance_correct", "attendance_approve", "staff_manage",
        "device_manage", "geofence_manage", "reports_export", "audit_view", "settings_manage",
    ],
    "Director": ["attendance_view_scope", "reports_export", "department_request_review"],
    # Staff receive no administrative permission; their self-service attendance access is built in.
    "Staff": [],
}


class Command(BaseCommand):
    help = "Create the standard Administrator, Director, and Staff roles without changing existing roles."

    def handle(self, *args, **options):
        permissions = {p.codename: p for p in Permission.objects.filter(content_type__app_label="accounts")}
        for name, codenames in ROLE_PERMISSIONS.items():
            role, created = Group.objects.get_or_create(name=name)
            role.permissions.add(*[permissions[codename] for codename in codenames])
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} {name} role."))
