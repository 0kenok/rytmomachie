import secrets
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import engine


def new_key():
    return secrets.token_urlsafe(16)


class Game(models.Model):
    LOCAL = "local"
    ONLINE = "online"
    MODE_CHOICES = [
        (LOCAL, _("Same screen (hot seat)")),
        (ONLINE, _("Two browsers (share a link)")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=LOCAL)
    white_key = models.CharField(max_length=32, default=new_key)
    black_key = models.CharField(max_length=32, default=new_key)
    state = models.JSONField()
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Game {self.id} ({self.mode})"

    def sides_for(self, key):
        """Sides the holder of `key` may play."""
        if not key:
            return []
        if self.mode == self.LOCAL:
            return [engine.WHITE, engine.BLACK] if secrets.compare_digest(key, self.white_key) else []
        sides = []
        if secrets.compare_digest(key, self.white_key):
            sides.append(engine.WHITE)
        if secrets.compare_digest(key, self.black_key):
            sides.append(engine.BLACK)
        return sides
