from django.utils import timezone
from rest_framework import serializers

from apps.org.models import Campus, Department, Geofence
from .geo import haversine_m
from .models import ActivityCategory, AttendanceRecord, DailyActivity, AttendanceCorrection, Holiday, LeaveRecord, OfficialDuty


class LocationInputSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(min_value=0)
    assertion = serializers.DictField(required=False)


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

    def validate(self, a):
        if a["end_time"] <= a["start_time"]:
            raise serializers.ValidationError("End time must be after start time.")
        return a


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCategory
        fields = ["id", "name"]


class GeofenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Geofence
        fields = ["id", "campus", "kind", "radius_m", "polygon", "is_active"]

    # How far a drawn point may sit from the campus's stored centre before it's rejected as
    # almost certainly a mistake (map zoomed out too far, wrong campus selected, a stray click).
    MAX_POINT_DISTANCE_M = 5000

    def validate(self, d):
        # Partial updates (the "edit an existing boundary" PATCH from GeofenceEditor) don't
        # resend `kind` — fall back to the existing record's kind so validation still runs.
        kind = d.get("kind") or getattr(self.instance, "kind", None)

        if kind == "circle" and not (d.get("radius_m") or getattr(self.instance, "radius_m", None)):
            raise serializers.ValidationError({"radius_m": "Circle geofence needs a radius."})

        if kind == "polygon" and "polygon" in d:
            poly = d.get("polygon") or []
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
            if campus:
                far_points = [str(i) for i, (lat, lng) in enumerate(poly, start=1)
                             if haversine_m(lat, lng, campus.latitude, campus.longitude) > self.MAX_POINT_DISTANCE_M]
                if far_points:
                    raise serializers.ValidationError({"polygon":
                        f"Point(s) {', '.join(far_points)} are more than "
                        f"{self.MAX_POINT_DISTANCE_M // 1000}km from {campus.name}'s stored location. "
                        "Check you're drawing on the right campus, or if the boundary is correct, "
                        "update the campus's stored latitude/longitude first."})
        return d


class CampusSerializer(serializers.ModelSerializer):
    geofences = GeofenceSerializer(many=True, read_only=True)
    department_ids = serializers.PrimaryKeyRelatedField(source="departments", many=True,
                                                        queryset=Department.objects.all(), required=False)
    departments = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Campus
        fields = ["id", "name", "latitude", "longitude", "is_active", "department_ids", "departments", "geofences"]



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


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "kind"]
