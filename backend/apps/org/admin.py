from django.contrib import admin

from .models import Campus, CampusArea, Department, Geofence


class GeofenceInline(admin.TabularInline):
    model = Geofence
    extra = 0


class CampusAreaInline(admin.TabularInline):
    model = CampusArea
    extra = 0


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ["name", "latitude", "longitude", "is_active"]
    inlines = [CampusAreaInline, GeofenceInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Geofence)
class GeofenceAdmin(admin.ModelAdmin):
    list_display = ["campus", "campus_area", "kind", "radius_m", "is_active", "modified_at"]
    list_filter = ["kind", "is_active", "campus", "campus_area"]


@admin.register(CampusArea)
class CampusAreaAdmin(admin.ModelAdmin):
    list_display = ["name", "campus", "is_active", "modified_at"]
    list_filter = ["is_active", "campus"]
    search_fields = ["name", "campus__name"]
