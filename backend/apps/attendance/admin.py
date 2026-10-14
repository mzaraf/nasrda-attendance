from django.contrib import admin

from .models import (ActivityAttachment, ActivityCategory, AttendanceLocation,
                     AttendanceRecord, DailyActivity, FaceProfile, FaceVerification)


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "enrolled_at", "last_verified_at"]
    search_fields = ["user__ippis_number", "user__first_name", "user__last_name"]
    readonly_fields = ["template_encrypted", "enrolled_at", "last_verified_at", "updated_at"]


@admin.register(FaceVerification)
class FaceVerificationAdmin(admin.ModelAdmin):
    list_display = ["user", "action", "status", "liveness_passed", "match_distance", "created_at"]
    list_filter = ["action", "status", "liveness_passed"]
    search_fields = ["user__ippis_number"]
    readonly_fields = [field.name for field in FaceVerification._meta.fields]


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


class DailyActivityInline(admin.TabularInline):
    model = DailyActivity
    extra = 0


class AttendanceLocationInline(admin.TabularInline):
    model = AttendanceLocation
    extra = 0
    readonly_fields = [f.name for f in AttendanceLocation._meta.fields]
    can_delete = False


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "campus", "check_in_status", "check_out_status", "review_status"]
    list_filter = ["date", "campus", "check_in_status", "review_status"]
    search_fields = ["user__ippis_number", "user__first_name", "user__last_name"]
    inlines = [DailyActivityInline, AttendanceLocationInline]


@admin.register(ActivityAttachment)
class ActivityAttachmentAdmin(admin.ModelAdmin):
    list_display = ["activity", "original_name", "uploaded_at"]
