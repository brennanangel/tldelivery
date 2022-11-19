import datetime
from django.core.management.base import BaseCommand
from delivery.delivery.models import Delivery


class Command(BaseCommand):
    help = "Run code against all existing delivery orders"

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int)

    def handle(self, *args, **options):
        if options["id"]:
            deliveries = [Delivery.objects.get(pk=options["id"])]
        else:
            deliveries = Delivery.objects.all()
        for delivery in deliveries:
            delivery.sync()
            delivery.save()
