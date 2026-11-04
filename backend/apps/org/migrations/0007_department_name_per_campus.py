from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("org", "0006_campus_areas")]

    operations = [
        migrations.AlterField(
            model_name="department",
            name="name",
            field=models.CharField(max_length=120),
        ),
    ]
