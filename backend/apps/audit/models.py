import hashlib
import json

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80, db_index=True)       # e.g. attendance.check_in
    description = models.TextField(blank=True)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit logs are immutable.")
        with transaction.atomic():
            last = AuditLog.objects.select_for_update().order_by("-id").first()
            self.prev_hash = last.hash if last else ""
            payload = json.dumps([self.user_id, self.action, self.description, self.previous_value,
                                  self.new_value, self.ip_address, self.created_at.isoformat(),
                                  self.prev_hash], sort_keys=True, default=str)
            self.hash = hashlib.sha256(payload.encode()).hexdigest()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit logs cannot be deleted.")