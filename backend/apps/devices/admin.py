from django.contrib import admin

from .models import DeviceRemovalRequest, PasskeyCredential, RegisteredDevice


@admin.register(RegisteredDevice)
class RegisteredDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "status", "registered_at", "last_seen_at"]
    list_filter = ["status"]
    search_fields = ["user__ippis_number", "user__first_name", "user__last_name", "label"]
    actions = ["revoke_devices"]

    @admin.action(description="Revoke selected devices")
    def revoke_devices(self, request, queryset):
        queryset.update(status="revoked")


@admin.register(PasskeyCredential)
class PasskeyCredentialAdmin(admin.ModelAdmin):
    list_display = ["device", "sign_count", "created_at"]


@admin.register(DeviceRemovalRequest)
class DeviceRemovalRequestAdmin(admin.ModelAdmin):
    list_display = ["device", "status", "requested_at", "decided_by", "decided_at"]
    list_filter = ["status"]
    search_fields = ["device__user__ippis_number", "device__label"]
