from rest_framework import viewsets

from apps.accounts.scope import HasAnyPerm
from apps.audit.services import log
from rest_framework.permissions import IsAuthenticated

from .models import Department
from .serializers import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """Department directory and campus assignments for staff administration."""
    queryset = Department.objects.order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.staff_manage"]
    pagination_class = None

    def perform_create(self, serializer):
        department = serializer.save()
        log(self.request, self.request.user, "department.created", department.name, new=serializer.data)

    def perform_update(self, serializer):
        old = DepartmentSerializer(self.get_object()).data
        department = serializer.save()
        log(self.request, self.request.user, "department.updated", department.name, previous=old, new=serializer.data)

    def perform_destroy(self, instance):
        if instance.user_set.exists():
            from apps.core.errors import DomainError
            raise DomainError("DEPARTMENT_IN_USE", "Move staff out of this department before deleting it.", 409)
        name = instance.name
        instance.delete()
        log(self.request, self.request.user, "department.deleted", name)
