from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Campus(models.Model):
    name = models.CharField(max_length=120, unique=True)
    latitude = models.FloatField()          # centre, for map framing
    longitude = models.FloatField()
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(Department, blank=True, related_name="campuses")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Geofence(models.Model):
    class Kind(models.TextChoices):
        CIRCLE = "circle"
        POLYGON = "polygon"

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="geofences")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    radius_m = models.FloatField(null=True, blank=True)          # circle only
    polygon = models.JSONField(null=True, blank=True)            # [[lat,lng], ...] polygon only
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
