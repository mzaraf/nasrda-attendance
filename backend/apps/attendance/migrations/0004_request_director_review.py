import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0003_alter_leaverecord_kind"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="attendancecorrection", name="director_status", field=models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=10)),
        migrations.AddField(model_name="attendancecorrection", name="director_reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="attendancecorrection", name="director_reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="correction_director_reviews", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="leaverecord", name="director_status", field=models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=10)),
        migrations.AddField(model_name="leaverecord", name="director_reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="leaverecord", name="director_reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="leave_director_reviews", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="officialduty", name="director_status", field=models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=10)),
        migrations.AddField(model_name="officialduty", name="director_reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="officialduty", name="director_reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="duty_director_reviews", to=settings.AUTH_USER_MODEL)),
    ]
