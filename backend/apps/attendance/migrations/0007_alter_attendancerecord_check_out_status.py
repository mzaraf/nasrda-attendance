from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0006_alter_leaverecord_kind")]

    operations = [
        migrations.AlterField(
            model_name="attendancerecord",
            name="check_out_status",
            field=models.CharField(blank=True, choices=[
                ("normal", "Normal"), ("early_departure", "Early"),
                ("early_closure", "Early Closure"), ("missed_checkout", "Missed"),
            ], max_length=20),
        ),
    ]
