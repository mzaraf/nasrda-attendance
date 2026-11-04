from rest_framework import serializers
from django.db import transaction

from .models import Campus, Department


class DepartmentSerializer(serializers.ModelSerializer):
    campus_ids = serializers.PrimaryKeyRelatedField(source="campuses", many=True, queryset=Campus.objects.all(), required=True)

    def validate_campus_ids(self, campuses):
        if not campuses:
            raise serializers.ValidationError("Assign at least one campus to this department.")
        return campuses

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        campuses = attrs.get("campuses")
        if campuses is None and self.instance:
            campuses = self.instance.campuses.all()

        # Validate this at object level as well as field level.  The source
        # alias (campus_ids -> campuses) is resolved by DRF before this point,
        # so this catches both a missing field and an explicit empty list.
        if not campuses:
            raise serializers.ValidationError({"campus_ids": "Assign at least one campus to this department."})

        # Names are unique only within a campus. This permits, for example,
        # ICT at NASRDA HQ and a separate ICT at NCSR Jos, while preventing
        # duplicate ICT departments in either campus.
        if name and campuses:
            existing = Department.objects.filter(name__iexact=name, campuses__in=campuses)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"name": f"A department named '{name}' already exists in one of the selected campuses."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Set the relationship explicitly in the same transaction. This makes
        # a successful create inseparable from its campus assignment.
        campuses = validated_data.pop("campuses", [])
        if not campuses:
            raise serializers.ValidationError({"campus_ids": "Assign at least one campus to this department."})
        department = Department.objects.create(**validated_data)
        department.campuses.set(campuses)
        return department

    class Meta:
        model = Department
        fields = ["id", "name", "campus_ids"]
