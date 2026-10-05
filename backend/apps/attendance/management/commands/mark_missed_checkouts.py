from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.attendance.models import AttendanceRecord


class Command(BaseCommand):
    help = "Marks today's still-open attendance records as missed check-out. Run once late at night."

    def handle(self, *a, **kw):
        today = timezone.localdate()
        n = AttendanceRecord.objects.filter(date=today, check_out_at__isnull=True) \
                                     .update(check_out_status="missed_checkout")
        self.stdout.write(f"Marked {n} missed checkouts for {today}.")