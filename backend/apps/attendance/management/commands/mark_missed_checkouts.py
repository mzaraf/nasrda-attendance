from django.core.management.base import BaseCommand
from apps.attendance.services import finalize_expired_open_records


class Command(BaseCommand):
    help = "Marks open attendance records from previous days as early closures."

    def handle(self, *a, **kw):
        finalize_expired_open_records()
        self.stdout.write("Processed open attendance records from previous days.")
