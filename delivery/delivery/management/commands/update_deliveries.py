import datetime
from django.core.management.base import BaseCommand
from delivery.delivery.models import Delivery


class Command(BaseCommand):
    help = "Run code against all existing delivery orders"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        deliveries = Delivery.objects.all()
        for delivery in deliveries:
            if id != 148:
                continue
            delivery.sync()
            delivery.save()
