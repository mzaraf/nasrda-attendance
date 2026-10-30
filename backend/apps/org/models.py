from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Campus(models.Model):
    name = models.CharField(max_length=120, unique=True)
    latitude = models.FloatField()          # centre, for map framing
    longitude = models.FloatField()
    boundary = models.JSONField(null=True, blank=True)  # [[lat, lng], ...] outer campus polygon
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(Department, blank=True, related_name="campuses")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CampusArea(models.Model):
    """A distinct physical location that belongs to one organisational campus."""
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="areas")
    name = models.CharField(max_length=120)
    boundary = models.JSONField()  # [[lat, lng], ...]
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campus", "name"], name="unique_campus_area_name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.campus.name}: {self.name}"


class Geofence(models.Model):
    class Kind(models.TextChoices):
        CIRCLE = "circle"
        POLYGON = "polygon"

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="geofences")
    campus_area = models.ForeignKey(CampusArea, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="geofences")
    name = models.CharField(max_length=120, default="Campus location")
    departments = models.ManyToManyField(Department, blank=True, related_name="buildings")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    radius_m = models.FloatField(null=True, blank=True)          # circle only
    polygon = models.JSONField(null=True, blank=True)            # [[lat,lng], ...] polygon only
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
