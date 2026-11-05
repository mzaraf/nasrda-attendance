from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0013_attendancelocation_geofence")]

    operations = [
        migrations.AddField(model_name="leaverecord", name="director_comment", field=models.TextField(blank=True)),
        migrations.AddField(model_name="leaverecord", name="admin_comment", field=models.TextField(blank=True)),
        migrations.AddField(model_name="officialduty", name="director_comment", field=models.TextField(blank=True)),
        migrations.AddField(model_name="officialduty", name="admin_comment", field=models.TextField(blank=True)),
        migrations.AddField(model_name="recurringleaveschedule", name="director_comment", field=models.TextField(blank=True)),
        migrations.AddField(model_name="recurringleaveschedule", name="admin_comment", field=models.TextField(blank=True)),
    ]
