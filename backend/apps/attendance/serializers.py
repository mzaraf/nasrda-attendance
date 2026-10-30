from datetime import time

from django.utils import timezone
from rest_framework import serializers

from apps.org.models import Campus, CampusArea, Department, Geofence
from apps.org.geometry import polygon_within_polygon
from .models import ActivityCategory, AttendanceRecord, DailyActivity, AttendanceCorrection, Holiday, LeaveRecord, OfficialDuty, RecurringLeaveSchedule


class LocationInputSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(min_value=0)
    face_verification_id = serializers.UUIDField(required=False)
    device_token = serializers.CharField(required=False, max_length=160)


class AttendanceRecordSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    activity_count = serializers.IntegerField(source="activities.count", read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "date", "campus_name", "check_in_at", "check_out_at", "duration_minutes",
                  "check_in_status", "check_out_status", "overtime_minutes",
                  "activity_report_status", "review_status", "activity_count"]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyActivity
        fields = ["id", "category", "title", "description", "start_time", "end_time", "status", "output"]
        extra_kwargs = {"start_time": {"required": False}, "end_time": {"required": False}, "output": {"required": False}}

    def validate(self, a):
        if "start_time" in a and "end_time" in a and a["end_time"] <= a["start_time"]:
            raise serializers.ValidationError("End time must be after start time.")
        return a

    def create(self, validated_data):
        # These are kept internally for existing reports, but are no longer fields
        # staff need to complete in the simplified activity form.
        validated_data.setdefault("start_time", time(0, 0))
        validated_data.setdefault("end_time", time(0, 1))
        validated_data.setdefault("output", "")
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCategory
        fields = ["id", "name"]


class CampusAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampusArea
        fields = ["id", "campus", "name", "boundary", "is_active"]

    def validate_boundary(self, boundary):
        if not isinstance(boundary, list) or len(boundary) < 3:
            raise serializers.ValidationError("Draw at least 3 points to form the campus area boundary.")
        for point in boundary:
            if not (isinstance(point, (list, tuple)) and len(point) == 2 and
                    isinstance(point[0], (int, float)) and isinstance(point[1], (int, float)) and
                    -90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                raise serializers.ValidationError("Each point must be a valid [latitude, longitude] pair.")
        return boundary

    def validate(self, attrs):
        boundary = attrs.get("boundary", getattr(self.instance, "boundary", None))
        if self.instance and "boundary" in attrs:
            invalid = [building.name for building in self.instance.geofences.filter(kind=Geofence.Kind.POLYGON)
                       if building.polygon and not polygon_within_polygon(building.polygon, boundary)]
            if invalid:
                raise serializers.ValidationError({"boundary": f"The boundary would exclude existing building(s): {', '.join(invalid)}."})
        return attrs


class GeofenceSerializer(serializers.ModelSerializer):
    department_ids = serializers.PrimaryKeyRelatedField(source="departments", many=True,
                                                        queryset=Department.objects.all(), required=False)
    departments = serializers.StringRelatedField(many=True, read_only=True)
    campus_area = serializers.PrimaryKeyRelatedField(queryset=CampusArea.objects.all(), required=False, allow_null=True)
    campus_area_name = serializers.CharField(source="campus_area.name", read_only=True)

    class Meta:
        model = Geofence
        fields = ["id", "campus", "campus_area", "campus_area_name", "name", "department_ids", "departments", "kind", "radius_m", "polygon", "is_active"]

    def validate(self, d):
        # Partial updates (the "edit an existing boundary" PATCH from GeofenceEditor) don't
        # resend `kind` — fall back to the existing record's kind so validation still runs.
        kind = d.get("kind") or getattr(self.instance, "kind", None)

        if kind == "circle" and not (d.get("radius_m") or getattr(self.instance, "radius_m", None)):
            raise serializers.ValidationError({"radius_m": "Circle geofence needs a radius."})

        polygon = d.get("polygon", getattr(self.instance, "polygon", None))
        if kind == "polygon" and polygon is not None:
            poly = polygon or []
            if len(poly) < 3:
                raise serializers.ValidationError({"polygon": "Draw at least 3 points to form a boundary."})
            for i, pt in enumerate(poly, start=1):
                if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                    raise serializers.ValidationError({"polygon": f"Point {i} is not a valid [latitude, longitude] pair."})
                lat, lng = pt
                if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                    raise serializers.ValidationError({"polygon": f"Point {i} has a non-numeric coordinate."})
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    raise serializers.ValidationError({"polygon": f"Point {i} is outside valid Earth coordinates."})

        campus = d.get("campus") or getattr(self.instance, "campus", None)
        campus_area = d.get("campus_area", getattr(self.instance, "campus_area", None))
        departments = d.get("departments")
        if departments is None and self.instance:
            departments = self.instance.departments.all()
        if kind == "polygon" and not self.instance and not departments:
            raise serializers.ValidationError({"department_ids": "Assign at least one department to this building."})
        if departments and campus:
            invalid = [department.name for department in departments if not department.campuses.filter(pk=campus.pk).exists()]
            if invalid:
                raise serializers.ValidationError({"department_ids": f"These departments are not assigned to {campus.name}: {', '.join(invalid)}."})
        if campus_area and campus and campus_area.campus_id != campus.id:
            raise serializers.ValidationError({"campus_area": "The selected campus area does not belong to this campus."})
        if kind == "polygon" and not campus_area:
            raise serializers.ValidationError({"campus_area": "Select a campus area before adding a building."})
        if kind == "polygon" and polygon and campus_area and not polygon_within_polygon(polygon, campus_area.boundary):
            raise serializers.ValidationError({"polygon": f"The whole building boundary must be inside the {campus_area.name} campus area."})

        return d


class CampusSerializer(serializers.ModelSerializer):
    geofences = GeofenceSerializer(many=True, read_only=True)
    areas = CampusAreaSerializer(many=True, read_only=True)
    department_ids = serializers.PrimaryKeyRelatedField(source="departments", many=True,
                                                        queryset=Department.objects.all(), required=False)
    departments = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Campus
        fields = ["id", "name", "latitude", "longitude", "boundary", "is_active", "department_ids", "departments", "areas", "geofences"]

    def validate_boundary(self, boundary):
        if boundary is None:
            return boundary
        if not isinstance(boundary, list) or len(boundary) < 3:
            raise serializers.ValidationError("Draw at least 3 points to form the campus boundary.")
        for point in boundary:
            if not (isinstance(point, (list, tuple)) and len(point) == 2 and
                    isinstance(point[0], (int, float)) and isinstance(point[1], (int, float)) and
                    -90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                raise serializers.ValidationError("Each point must be a valid [latitude, longitude] pair.")
        return boundary

    def validate(self, attrs):
        boundary = attrs.get("boundary", getattr(self.instance, "boundary", None))
        if self.instance and "boundary" in attrs:
            buildings = self.instance.geofences.filter(kind=Geofence.Kind.POLYGON)
            if not boundary and buildings.exists():
                raise serializers.ValidationError({"boundary": "A campus with buildings must keep a campus boundary."})
            if boundary:
                invalid = [building.name for building in buildings
                           if building.polygon and not polygon_within_polygon(building.polygon, boundary)]
                if invalid:
                    raise serializers.ValidationError({"boundary": f"The boundary would exclude existing building(s): {', '.join(invalid)}."})
        return attrs



class CorrectionSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="requested_by.get_full_name", read_only=True)

    class Meta:
        model = AttendanceCorrection
        fields = ["id", "record", "field", "requested_value", "reason", "supporting_document",
                  "status", "director_status", "review_note", "staff_name", "created_at"]
        read_only_fields = ["status", "director_status", "review_note"]


class LeaveSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="user.get_full_name", read_only=True)
    approval_state = serializers.SerializerMethodField()
    approval_message = serializers.SerializerMethodField()

    @staticmethod
    def _name(user):
        return user.get_full_name().strip() if user and user.get_full_name().strip() else None

    def get_approval_state(self, obj):
        if obj.director_status == "rejected" or obj.status == "rejected":
            return "rejected"
        if obj.recall_return_date:
            return "recalled"
        if obj.status == "approved":
            return "approved"
        return "pending"

    def get_approval_message(self, obj):
        if obj.director_status == "rejected":
            return f"Rejected by {self._name(obj.director_reviewed_by) or 'the department director'}"
        if obj.status == "rejected":
            return f"Rejected by {self._name(obj.approved_by) or 'the administrator'}"
        if obj.recall_return_date:
            return f"Recalled by {self._name(obj.recalled_by) or 'the administrator'}; return to duty from {obj.recall_return_date:%d %b %Y}. Reason: {obj.recall_reason}"
        if obj.status == "approved":
            return f"Approved by {self._name(obj.approved_by) or 'the administrator'}"
        if obj.director_status == "approved":
            return "Awaiting Administrator's Approval"
        return "Awaiting Director's Approval"

    class Meta:
        model = LeaveRecord
        fields = ["id", "staff_name", "kind", "start_date", "end_date", "reason", "status", "director_status", "recall_return_date", "recall_reason", "approval_state", "approval_message", "created_at"]
        read_only_fields = ["status", "director_status"]

    def validate(self, d):
        if d["end_date"] < d["start_date"]:
            raise serializers.ValidationError("End date must be on or after the start date.")
        return d


class OfficialDutySerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="user.get_full_name", read_only=True)
    approval_state = serializers.SerializerMethodField()
    approval_message = serializers.SerializerMethodField()

    @staticmethod
    def _name(user):
        return user.get_full_name().strip() if user and user.get_full_name().strip() else None

    def get_approval_state(self, obj):
        if obj.director_status == "rejected" or obj.status == "rejected":
            return "rejected"
        if obj.recall_return_date:
            return "recalled"
        if obj.status == "approved":
            return "approved"
        return "pending"

    def get_approval_message(self, obj):
        if obj.director_status == "rejected":
            return f"Rejected by {self._name(obj.director_reviewed_by) or 'the department director'}"
        if obj.status == "rejected":
            return f"Rejected by {self._name(obj.approved_by) or 'the administrator'}"
        if obj.recall_return_date:
            return f"Recalled by {self._name(obj.recalled_by) or 'the administrator'}; return to duty from {obj.recall_return_date:%d %b %Y}. Reason: {obj.recall_reason}"
        if obj.status == "approved":
            return f"Approved by {self._name(obj.approved_by) or 'the administrator'}"
        if obj.director_status == "approved":
            return "Awaiting Administrator's Approval"
        return "Awaiting Director's Approval"

    class Meta:
        model = OfficialDuty
        fields = ["id", "user", "staff_name", "location", "start_date", "end_date", "reason",
                  "supporting_document", "status", "director_status", "recall_return_date", "recall_reason", "approval_state", "approval_message", "created_at"]
        read_only_fields = ["user", "staff_name", "status", "director_status"]

    def validate(self, d):
        if d["end_date"] < d["start_date"]:
            raise serializers.ValidationError("End date must be on or after the start date.")
        return d


class RecurringLeaveSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="user.get_full_name", read_only=True)
    approval_state = serializers.SerializerMethodField()
    approval_message = serializers.SerializerMethodField()

    @staticmethod
    def _name(user):
        return user.get_full_name().strip() if user and user.get_full_name().strip() else None

    class Meta:
        model = RecurringLeaveSchedule
        fields = ["id", "staff_name", "start_date", "end_date", "off_weekdays", "reason", "status", "director_status", "recall_return_date", "recall_reason", "approval_state", "approval_message", "created_at"]
        read_only_fields = ["status", "director_status"]

    def validate(self, d):
        if d["end_date"] < d["start_date"]:
            raise serializers.ValidationError("End date must be on or after the start date.")
        days = d.get("off_weekdays", [])
        if not days or any(not isinstance(day, int) or day < 0 or day > 6 for day in days):
            raise serializers.ValidationError({"off_weekdays": "Select one or more recurring off days."})
        return d

    def get_approval_state(self, obj):
        if obj.director_status == "rejected" or obj.status == "rejected": return "rejected"
        if obj.status == "recalled": return "recalled"
        if obj.status == "approved": return "approved"
        return "pending"

    def get_approval_message(self, obj):
        if obj.director_status == "rejected": return f"Rejected by {self._name(obj.director_reviewed_by) or 'the Director'}"
        if obj.status == "rejected": return f"Rejected by {self._name(obj.approved_by) or 'the Administrator'}"
        if obj.status == "recalled": return f"Recalled by {self._name(obj.recalled_by) or 'the Administrator'}; return to duty from {obj.recall_return_date:%d %b %Y}. Reason: {obj.recall_reason}"
        if obj.status == "approved": return f"Approved by {self._name(obj.approved_by) or 'the Administrator'}"
        return "Awaiting Administrator's Approval" if obj.director_status == "approved" else "Awaiting Director's Approval"


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "kind"]
