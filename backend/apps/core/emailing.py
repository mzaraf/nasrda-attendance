"""Best-effort email notifications. Mail must never interrupt a business action."""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_email(subject, message, recipients):
    recipients = list({email.strip() for email in recipients if email and email.strip()})
    # Do not even attempt an SMTP connection until the deployment has configured it.
    if not recipients or not getattr(settings, "EMAIL_HOST", "") or not getattr(settings, "DEFAULT_FROM_EMAIL", ""):
        return False
    try:
        return bool(send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True))
    except Exception:  # A mail outage must never break attendance or approvals.
        logger.exception("Email notification could not be sent")
        return False


def send_credentials(user, password, reason="Your account has been created"):
    return send_email(
        "NASRDA Staff Attendance account details",
        f"Hello {user.get_full_name() or user.ippis_number},\n\n{reason}.\n\n"
        f"Username (IPPIS Number): {user.ippis_number}\nPassword: {password}\n\n"
        "Please sign in and change this password immediately.\n\nNASRDA Staff Attendance System",
        [user.email],
    )
