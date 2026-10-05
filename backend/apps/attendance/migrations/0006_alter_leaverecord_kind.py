from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0005_alter_leaverecord_kind")]

    operations = [
        migrations.AlterField(
            model_name="leaverecord",
            name="kind",
            field=models.CharField(choices=[
                ("annual", "Annual"), ("sick", "Sick"), ("casual", "Casual"),
                ("maternity", "Maternity"), ("paternity", "Paternity"),
                ("training", "Training"), ("study", "Study"), ("conference", "Conference"),
                ("official_travel", "Travel"), ("permission", "Permission"), ("other", "Other"),
            ], max_length=20),
        ),
    ]
