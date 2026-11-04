from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from django.db import transaction

from apps.accounts.scope import HasAnyPerm
from apps.audit.services import log
from rest_framework.permissions import IsAuthenticated

from .models import Campus, Department
from .serializers import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """Department directory and campus assignments for staff administration."""
    queryset = Department.objects.order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, HasAnyPerm]
    required_perms = ["accounts.staff_manage"]
    pagination_class = None

    def perform_create(self, serializer):
        # Do not rely on implicit ModelSerializer many-to-many handling here.
        # The campus relationship is essential organisational data, so create
        # and verify it explicitly in the same transaction as the department.
        campus_ids = self.request.data.get("campus_ids", [])
        if not isinstance(campus_ids, list) or not campus_ids:
            raise ValidationError({"campus_ids": "Assign at least one campus to this department."})
        campuses = list(Campus.objects.filter(pk__in=campus_ids))
        if len(campuses) != len({str(campus_id) for campus_id in campus_ids}):
            raise ValidationError({"campus_ids": "One or more selected campuses do not exist."})
        with transaction.atomic():
            department = serializer.save()
            department.campuses.set(campuses)
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
