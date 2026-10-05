from django.contrib import admin

from .models import Campus, Department, Geofence


class GeofenceInline(admin.TabularInline):
    model = Geofence
    extra = 0


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ["name", "latitude", "longitude", "is_active"]
    inlines = [GeofenceInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Geofence)
class GeofenceAdmin(admin.ModelAdmin):
    list_display = ["campus", "kind", "radius_m", "is_active", "modified_at"]
    list_filter = ["kind", "is_active", "campus"]