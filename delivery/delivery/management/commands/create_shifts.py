from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from delivery.delivery.models import Shift


class Command(BaseCommand):
    help = "Creates shifts as a template"

    def add_arguments(self, parser):
        parser.add_argument("start_date")
        parser.add_argument("end_date")

    def handle(self, *args, **options):
        date = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(options["end_date"], "%Y-%m-%d").date()

        while date < end_date:
            shift = Shift(date=date, time="AM", slots_available=20)
            shift.save()
            shift = Shift(date=date, time="PM", slots_available=20)
            shift.save()

            date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS("Done"))
