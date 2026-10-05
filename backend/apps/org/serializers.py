from rest_framework import serializers

from .models import Campus, Department


class DepartmentSerializer(serializers.ModelSerializer):
    campus_ids = serializers.PrimaryKeyRelatedField(source="campuses", many=True, queryset=Campus.objects.all(), required=False)

    class Meta:
        model = Department
        fields = ["id", "name", "campus_ids"]
