from django.core.management.base import BaseCommand

from tracker.models import Category

DEFAULTS = ["Food", "Travel", "Bills", "Shopping", "Health", "Education", "Entertainment", "Other"]


class Command(BaseCommand):
    help = "Create the default expense categories."

    def handle(self, *args, **options):
        created = 0
        for name in DEFAULTS:
            _, was_created = Category.objects.get_or_create(name=name)
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"Done. {created} new categories added."))
