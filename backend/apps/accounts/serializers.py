from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

User = get_user_model()


class StaffSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    campus_name = serializers.CharField(source="primary_campus.name", read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(source="groups", many=True, queryset=Group.objects.all(), required=False)
    roles = serializers.StringRelatedField(source="groups", many=True, read_only=True)

    def validate(self, attrs):
        campus = attrs.get("primary_campus", getattr(self.instance, "primary_campus", None))
        department = attrs.get("department", getattr(self.instance, "department", None))
        if campus and department and not campus.departments.filter(pk=department.pk).exists():
            raise serializers.ValidationError({"department": f"{department.name} is not assigned to {campus.name}."})
        return attrs

    class Meta:
        model = User
        fields = ["id", "ippis_number", "file_number", "first_name", "middle_name", "last_name",
                  "email", "phone", "department", "department_name",
                  "designation", "grade_level", "employment_status", "primary_campus", "campus_name",
                  "campus_policy", "is_nursing_mother", "mfa_enabled", "is_active", "role_ids", "roles"]

    def update(self, instance, validated_data):
        # Turning MFA off invalidates the current authenticator enrollment.
        if validated_data.get("mfa_enabled") is False and instance.mfa_enabled:
            instance.mfa_secret = ""
            instance.mfa_confirmed = False
        return super().update(instance, validated_data)


class PermissionSerializer(serializers.ModelSerializer):
    code = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ["id", "name", "code"]

    def get_code(self, obj):
        return f"{obj.content_type.app_label}.{obj.codename}"


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(source="permissions", many=True,
                                                         queryset=Permission.objects.all(), required=False)
    permissions = PermissionSerializer(many=True, read_only=True)
    member_count = serializers.IntegerField(source="user_set.count", read_only=True)

    class Meta:
        model = Group
        fields = ["id", "name", "permission_ids", "permissions", "member_count"]
