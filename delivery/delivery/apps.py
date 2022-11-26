from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    name = "delivery.delivery"
    verbose_name = "Delivery"

    def ready(self):
        try:
            import delivery.delivery.signals  # noqa F401
        except ImportError:
            pass
