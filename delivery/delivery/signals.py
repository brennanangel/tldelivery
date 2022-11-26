from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Delivery, Shift


@receiver(post_save, sender=Delivery)
def handle_delivery_save(*args, **kwargs):
    Shift.bust_available_shift_cache()


@receiver(post_delete, sender=Delivery)
def handle_delivery_delete(*args, **kwargs):
    Shift.bust_available_shift_cache()
