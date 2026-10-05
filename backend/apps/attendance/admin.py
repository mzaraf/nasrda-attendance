from django.contrib import admin

from .models import (ActivityAttachment, ActivityCategory, AttendanceLocation,
                     AttendanceRecord, DailyActivity)


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