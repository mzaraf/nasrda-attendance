from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission


def scoped_staff(user):
    qs = get_user_model().objects.filter(is_active=True)
    if user.has_perm("accounts.attendance_view_all"):        # superusers pass this too
        return qs
    if user.has_perm("accounts.attendance_view_scope") and user.department_id:
        return qs.filter(department_id=user.department_id)
    return qs.none()


class HasAnyPerm(BasePermission):
    """View sets `required_perms = ["accounts.x", ...]`; user needs at least one."""
    def has_permission(self, request, view):
        return any(request.user.has_perm(p) for p in getattr(view, "required_perms", []))