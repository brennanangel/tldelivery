from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    name = 'delivery.delivery'
    verbose_name = "Delivery"

    def ready(self):
        """Override this to put in:
            Users system checks
            Users signal registration
        """
        pass
