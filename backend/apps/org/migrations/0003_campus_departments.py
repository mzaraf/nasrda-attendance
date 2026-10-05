from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("org", "0002_delete_division")]

    operations = [
        migrations.AddField(
            model_name="campus",
            name="departments",
            field=models.ManyToManyField(blank=True, related_name="campuses", to="org.department"),
        ),
    ]
