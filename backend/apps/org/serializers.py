from rest_framework import serializers

from .models import Campus, Department


class DepartmentSerializer(serializers.ModelSerializer):
    campus_ids = serializers.PrimaryKeyRelatedField(source="campuses", many=True, queryset=Campus.objects.all(), required=True)

    def validate_campus_ids(self, campuses):
        if not campuses:
            raise serializers.ValidationError("Assign at least one campus to this department.")
        return campuses

    class Meta:
        model = Department
        fields = ["id", "name", "campus_ids"]
