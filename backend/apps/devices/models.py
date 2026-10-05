from django.conf import settings
from django.db import models


class RegisteredDevice(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"     # awaiting admin approval
        ACTIVE = "active"
        REVOKED = "revoked"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    label = models.CharField(max_length=80)                 # "My Samsung"
    user_agent = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)


class PasskeyCredential(models.Model):
    """Public half of a device-bound key. The private key and biometric never leave the phone."""
    device = models.OneToOneField(RegisteredDevice, on_delete=models.CASCADE, related_name="credential")
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class DeviceRemovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    device = models.OneToOneField(RegisteredDevice, on_delete=models.CASCADE, related_name="removal_request")
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="device_removal_decisions")
    decided_at = models.DateTimeField(null=True, blank=True)
