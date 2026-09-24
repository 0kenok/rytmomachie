from django.apps import AppConfig


class GameConfig(AppConfig):
    name = 'game'

    def ready(self):
        from . import accounts  # noqa: F401  (registers the login signal handler)
