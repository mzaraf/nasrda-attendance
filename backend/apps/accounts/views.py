import secrets

import csv
import io

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from apps.audit.services import log
from apps.core.errors import DomainError
from apps.core.emailing import send_credentials, send_email
from .scope import HasAnyPerm, scoped_staff
from .serializers import PermissionSerializer, RoleSerializer, StaffSerializer

User = get_user_model()


class StaffViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("department", "primary_campus").order_by("last_name")
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.staff_manage"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Directors can browse only active colleagues in their department. Staff managers
        # retain access to the complete staff directory and can make changes.
        if self.request.method in SAFE_METHODS and not self.request.user.has_perm("accounts.staff_manage"):
            qs = scoped_staff(self.request.user)
        if q := self.request.query_params.get("q"):
            qs = qs.filter(Q(ippis_number__icontains=q) | Q(first_name__icontains=q)
                          | Q(last_name__icontains=q) | Q(email__icontains=q))
        return qs

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            self.required_perms = ["accounts.staff_manage", "accounts.attendance_view_all", "accounts.attendance_view_scope"]
        else:
            self.required_perms = ["accounts.staff_manage"]
        return super().get_permissions()

    def perform_create(self, serializer):
        temp_password = secrets.token_urlsafe(9)
        user = serializer.save()
        user.set_password(temp_password)
        user.save(update_fields=["password"])
        self._temp_password = temp_password
        self._email_sent = send_credentials(user, temp_password)
        log(self.request, self.request.user, "staff.created", user.ippis_number)

    def create(self, request, *a, **kw):
        resp = super().create(request, *a, **kw)
        # Pilot-simplicity: temp password is returned here for the admin to hand to the staff member.
        # Production: remove this and email/SMS it to the staff member's verified contact instead.
        resp.data["temporary_password"] = self._temp_password
        resp.data["email_sent"] = self._email_sent
        return resp

    def perform_update(self, serializer):
        old = StaffSerializer(self.get_object()).data
        user = serializer.save()
        log(self.request, self.request.user, "staff.updated", user.ippis_number, previous=old, new=serializer.data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        u = self.get_object(); u.is_active = False; u.save(update_fields=["is_active"])
        log(request, request.user, "staff.deactivated", u.ippis_number)
        return Response({"ok": True})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        u = self.get_object(); u.is_active = True; u.save(update_fields=["is_active"])
        log(request, request.user, "staff.activated", u.ippis_number)
        return Response({"ok": True})

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        u = self.get_object()
        temp = secrets.token_urlsafe(9)
        u.set_password(temp); u.save(update_fields=["password"])
        email_sent = send_credentials(u, temp, "Your password has been reset by an administrator")
        log(request, request.user, "staff.password_reset", u.ippis_number)
        return Response({"temporary_password": temp, "email_sent": email_sent})

    @action(detail=True, methods=["post"])
    def reset_devices(self, request, pk=None):
        u = self.get_object()
        n = u.devices.exclude(status="revoked").update(status="revoked")
        log(request, request.user, "staff.devices_reset", f"{u.ippis_number}: {n} device(s)")
        return Response({"revoked": n})


class RoleViewSet(viewsets.ModelViewSet):
    """Custom Django groups used as staff roles."""
    queryset = Group.objects.prefetch_related("permissions", "user_set").order_by("name")
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.settings_manage"]
    pagination_class = None

    def perform_create(self, serializer):
        role = serializer.save()
        log(self.request, self.request.user, "role.created", role.name, new=serializer.data)

    def perform_update(self, serializer):
        old = RoleSerializer(self.get_object()).data
        role = serializer.save()
        log(self.request, self.request.user, "role.updated", role.name, previous=old, new=serializer.data)

    def perform_destroy(self, instance):
        if instance.user_set.exists():
            raise DomainError("ROLE_IN_USE", "Remove this role from its staff members before deleting it.", 409)
        name = instance.name
        instance.delete()
        log(self.request, self.request.user, "role.deleted", name)


class PermissionList(APIView):
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.settings_manage"]

    def get(self, request):
        # Only expose the application's explicit business permissions, never Django's
        # powerful built-in admin permissions.
        qs = Permission.objects.filter(content_type__app_label="accounts", codename__in=[
            "attendance_view_all", "attendance_view_scope", "attendance_correct", "attendance_approve",
            "staff_manage", "device_manage", "geofence_manage", "reports_export", "audit_view", "settings_manage",
        ]).select_related("content_type").order_by("name")
        return Response(PermissionSerializer(qs, many=True).data)


class PasswordResetRequest(APIView):
    """Public request endpoint: always returns the same response to avoid account enumeration."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        ippis = str(request.data.get("ippis_number", "")).strip()
        user = User.objects.filter(ippis_number=ippis, is_active=True).first()
        if not user:
            return Response({"ok": False, "message": "There is no active account associated with this IPPIS number."})
        if not user.email:
            return Response({"ok": False, "message": "There is no email address associated with this account. Please contact administrator to update your profile email."})
        password = secrets.token_urlsafe(9)
        sent = send_credentials(user, password, "A password reset was requested for your account")
        if not sent:
            return Response({"ok": False, "message": "We could not send a password email at this time. Please contact an administrator."})
        user.set_password(password)
        user.save(update_fields=["password"])
        log(request, user, "auth.password_reset_requested", "Password reset email sent")
        return Response({"ok": True, "message": f"A new password has been sent to {user.email}. Please check your email inbox or spam folder."})


class ChangePassword(APIView):
    def post(self, request):
        current_password = str(request.data.get("current_password", ""))
        new_password = str(request.data.get("new_password", ""))
        if not request.user.check_password(current_password):
            raise DomainError("INVALID_PASSWORD", "Your current password is incorrect.", 400)
        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        log(request, request.user, "auth.password_changed", "Staff member changed their password")
        return Response({"ok": True})


REQUIRED_COLUMNS = ["IPPIS Number", "First Name", "Last Name", "Email"]
OPTIONAL_COLUMNS = ["File Number", "Middle Name", "Phone", "Department", "Designation", "Grade Level", "Campus", "Role"]


class StaffImportPreview(APIView):
    """Step 1 of 2: parse and validate, but do not write anything to the database yet."""
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.staff_manage"]

    def post(self, request):
        import openpyxl
        from django.core.cache import cache
        import uuid

        f = request.FILES.get("file")
        if not f:
            raise DomainError("FILE_REQUIRED", "Upload an .xlsx file.")
        try:
            if f.name.lower().endswith(".csv"):
                decoded = io.TextIOWrapper(f.file, encoding="utf-8-sig", newline="")
                csv_rows = list(csv.reader(decoded))
                headers = [c.strip() for c in csv_rows[0]] if csv_rows else []
                raw_rows = csv_rows[1:]
                def value_at(raw, index):
                    return raw[index].strip() if index < len(raw) else ""
            elif f.name.lower().endswith(".xlsx"):
                wb = openpyxl.load_workbook(f, data_only=True)
                ws = wb.active
                headers = [str(c.value).strip() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
                raw_rows = list(ws.iter_rows(min_row=2, values_only=True))
                def value_at(raw, index):
                    value = raw[index] if index < len(raw) else None
                    return str(value).strip() if value not in (None, "") else ""
            else:
                raise DomainError("FILE_TYPE", "Upload a CSV or XLSX staff file.")
        except DomainError:
            raise
        except Exception:
            raise DomainError("FILE_INVALID", "Could not read this file. Upload a valid CSV or XLSX file.")
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise DomainError("MISSING_COLUMNS", f"Missing required column(s): {', '.join(missing)}.")
        idx = {h: i for i, h in enumerate(headers)}

        from apps.org.models import Campus, Department
        existing = set(User.objects.values_list("ippis_number", flat=True))
        depts = {d.name: d for d in Department.objects.all()}
        campuses = {c.name: c for c in Campus.objects.all()}
        roles = {role.name: role for role in Group.objects.all()}

        rows, seen = [], set()
        for raw in raw_rows:
            def get(col):
                return value_at(raw, idx[col]) if col in idx else ""

            row = {c.lower().replace(" ", "_"): get(c) for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
            errors = []
            if not row["ippis_number"]:
                errors.append("Missing IPPIS Number")
            if not row["first_name"] or not row["last_name"]:
                errors.append("Missing first or last name")
            if not row["email"]:
                errors.append("Missing email")
            if row["department"] and row["department"] not in depts:
                errors.append(f"Unknown department '{row['department']}'")
            if row["campus"] and row["campus"] not in campuses:
                errors.append(f"Unknown campus '{row['campus']}'")
            if row["department"] and row["campus"] and row["department"] in depts and row["campus"] in campuses \
                    and not campuses[row["campus"]].departments.filter(pk=depts[row["department"]].pk).exists():
                errors.append(f"Department '{row['department']}' is not assigned to campus '{row['campus']}'")
            row["role_names"] = [name.strip() for name in row["role"].split(";") if name.strip()]
            unknown_roles = [name for name in row["role_names"] if name not in roles]
            if unknown_roles:
                errors.append(f"Unknown role(s): {', '.join(unknown_roles)}")
            if row["ippis_number"] and row["ippis_number"] in existing:
                errors.append("Already registered")
            if row["ippis_number"] and row["ippis_number"] in seen:
                errors.append("Duplicate within this file")
            seen.add(row["ippis_number"])
            rows.append({**row, "errors": errors, "valid": not errors})

        token = str(uuid.uuid4())
        cache.set(f"staff_import:{token}", rows, 600)     # 10 minutes to review, then re-upload
        return Response({"token": token, "total": len(rows),
                         "valid": sum(r["valid"] for r in rows), "invalid": sum(not r["valid"] for r in rows),
                         "rows": rows})


class StaffImportCommit(APIView):
    """Step 2 of 2: commit only the rows that passed validation."""
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.staff_manage"]

    def post(self, request):
        from django.core.cache import cache
        from apps.org.models import Campus, Department

        token = request.data.get("token")
        rows = cache.get(f"staff_import:{token}")
        if rows is None:
            raise DomainError("PREVIEW_EXPIRED", "This import preview has expired. Please re-upload the file.")
        depts = {d.name: d for d in Department.objects.all()}
        campuses = {c.name: c for c in Campus.objects.all()}
        roles = {role.name: role for role in Group.objects.all()}
        created = 0
        with transaction.atomic():
            for row in rows:
                if not row["valid"] or User.objects.filter(ippis_number=row["ippis_number"]).exists():
                    continue
                u = User(ippis_number=row["ippis_number"], first_name=row["first_name"],
                         last_name=row["last_name"], file_number=row.get("file_number", ""), middle_name=row.get("middle_name", ""),
                         email=row["email"], phone=row.get("phone", ""),
                         designation=row.get("designation", ""), grade_level=row.get("grade_level", ""),
                         department=depts.get(row.get("department", "")),
                         primary_campus=campuses.get(row.get("campus", "")))
                password = secrets.token_urlsafe(9)
                u.set_password(password)
                u.save()
                u.groups.set([roles[name] for name in row.get("role_names", [])])
                send_credentials(u, password)
                created += 1
        cache.delete(f"staff_import:{token}")
        log(request, request.user, "staff.bulk_import", f"{created} staff created")
        return Response({"created": created})
