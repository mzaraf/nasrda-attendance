from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_user_is_nursing_mother")]

    operations = [
        migrations.AddField(model_name="user", name="mfa_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="user", name="mfa_secret", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="user", name="mfa_confirmed", field=models.BooleanField(default=False)),
    ]
