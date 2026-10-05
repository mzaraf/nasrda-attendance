from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class NasrdaUserAdmin(UserAdmin):
    ordering = ["ippis_number"]
    list_display = ["ippis_number", "first_name", "last_name", "department",
                    "primary_campus", "is_active", "is_staff"]
    list_filter = ["is_active", "department", "primary_campus", "employment_status"]
    search_fields = ["ippis_number", "first_name", "last_name", "email", "file_number"]
    filter_horizontal = ["secondary_campuses", "groups", "user_permissions"]
    fieldsets = [
        (None, {"fields": ["ippis_number", "password"]}),
        ("Personal", {"fields": ["first_name", "middle_name", "last_name", "email", "phone", "photo"]}),
        ("Organisation", {"fields": ["department", "designation", "grade_level", "employment_status"]}),
        ("Campus access", {"fields": ["primary_campus", "secondary_campuses", "campus_policy"]}),
        ("Access", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"],
        "fields": ["ippis_number", "email", "first_name", "last_name", "password1", "password2"]})]