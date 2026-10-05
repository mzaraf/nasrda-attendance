from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_alter_user_options")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_nursing_mother",
            field=models.BooleanField(default=False),
        ),
    ]
