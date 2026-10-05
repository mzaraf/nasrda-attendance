from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_alter_user_options_remove_user_division_and_more")]
    operations = [migrations.AlterModelOptions(name="user", options={"permissions": [
        ("attendance_view_all", "View attendance for all staff"), ("attendance_view_scope", "View attendance for own department"),
        ("attendance_correct", "Correct attendance"), ("attendance_approve", "Approve corrections"),
        ("staff_manage", "Create/edit/disable staff"), ("device_manage", "Approve/revoke devices"),
        ("geofence_manage", "Manage campuses and geofences"), ("reports_export", "Generate and export reports"),
        ("audit_view", "View audit logs"), ("settings_manage", "Manage system settings"),
        ("department_request_review", "Review requests for own department"),
    ]})]
