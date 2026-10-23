from django.apps import AppConfig


class PumpConfig(AppConfig):
    name = 'pump'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import close_guards
