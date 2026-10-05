from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0004_request_director_review")]

    operations = [
        migrations.AlterField(
            model_name="leaverecord",
            name="kind",
            field=models.CharField(choices=[
                ("annual", "Annual"), ("sick", "Sick"), ("maternity", "Maternity"),
                ("paternity", "Paternity"), ("training", "Training"), ("study", "Study"),
                ("conference", "Conference"), ("official_travel", "Travel"),
                ("permission", "Permission"), ("other", "Other"),
            ], max_length=20),
        ),
    ]
