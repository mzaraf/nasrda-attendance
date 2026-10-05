from django.core.management.base import BaseCommand
from apps.attendance.models import ActivityCategory


CATEGORIES = [
    "Official Assignment",
    "Meeting",
    "Field Work",
    "Project Development",
    "Research",
    "Training",
    "Administrative Work",
    "Inspection",
    "Documentation",
    "Stakeholder Engagement",
    "Travel",
    "Other",
]


class Command(BaseCommand):
    help = "Create default attendance activity categories"

    def handle(self, *args, **kwargs):
        for name in CATEGORIES:
            ActivityCategory.objects.get_or_create(name=name)

        self.stdout.write(
            self.style.SUCCESS("Attendance categories created successfully.")
        )