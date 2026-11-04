from rest_framework import serializers

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

    class Meta:
        model = Department
        fields = ["id", "name", "campus_ids"]
