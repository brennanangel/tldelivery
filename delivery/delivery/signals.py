from django.db.models.signals import post_save, post_delete

from .models import Delivery, Shift

from django.dispatch import receiver


@receiver(post_save, sender=Delivery)
def handle_delivery_save(sender, instance, created, **kwargs):
    Shift.bust_available_shift_cache()


@receiver(post_delete, sender=Delivery)
def handle_delivery_delete(sender, instance, **kwargs):
    Shift.bust_available_shift_cache()
