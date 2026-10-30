from django.db import migrations, models
import django.db.models.deletion


def create_areas_from_existing_boundaries(apps, schema_editor):
    Campus = apps.get_model("org", "Campus")
    CampusArea = apps.get_model("org", "CampusArea")
    Geofence = apps.get_model("org", "Geofence")

    for campus in Campus.objects.exclude(boundary__isnull=True):
        if not campus.boundary:
            continue
        area, _ = CampusArea.objects.get_or_create(
            campus_id=campus.id,
            name="Main campus area",
            defaults={"boundary": campus.boundary, "is_active": campus.is_active},
        )
        Geofence.objects.filter(campus_id=campus.id, campus_area__isnull=True).update(campus_area_id=area.id)


class Migration(migrations.Migration):
    dependencies = [("org", "0005_campus_boundary_geofence_departments")]

    operations = [
        migrations.CreateModel(
            name="CampusArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("boundary", models.JSONField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("campus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="areas", to="org.campus")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="campusarea",
            constraint=models.UniqueConstraint(fields=("campus", "name"), name="unique_campus_area_name"),
        ),
        migrations.AddField(
            model_name="geofence",
            name="campus_area",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="geofences", to="org.campusarea"),
        ),
        migrations.RunPython(create_areas_from_existing_boundaries, migrations.RunPython.noop),
    ]
