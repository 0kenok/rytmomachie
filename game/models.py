import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from . import ai, engine


INITIAL_RATING = 1200


def new_key():
    return secrets.token_urlsafe(16)


class Game(models.Model):
    AI = "ai"
    LOCAL = "local"
    ONLINE = "online"
    MODE_CHOICES = [
        (AI, _("Against the computer")),
        (LOCAL, _("Same screen (hot seat)")),
        (ONLINE, _("Two browsers (share a link)")),
    ]
    AI_LEVEL_CHOICES = [
        (ai.BEGINNER, _("Beginner")),
        (ai.EASY, _("Easy")),
        (ai.MEDIUM, _("Medium")),
        (ai.HARD, _("Hard")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=LOCAL)
    white_key = models.CharField(max_length=32, default=new_key)
    black_key = models.CharField(max_length=32, default=new_key)
    # In AI mode: the side the computer plays, and how strong it is.
    ai_side = models.CharField(max_length=5, blank=True, default="")
    ai_level = models.PositiveSmallIntegerField(choices=AI_LEVEL_CHOICES, null=True, blank=True)
    # Accounts of the people playing, when they were logged in. In hot-seat
    # mode the creator is stored as white_player and plays both sides.
    white_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="games_as_white",
    )
    black_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="games_as_black",
    )
    # Rating points each player won (positive) or lost (negative) when this
    # game ended. None while the game runs, or if it is not rated.
    white_rating_change = models.IntegerField(null=True, blank=True)
    black_rating_change = models.IntegerField(null=True, blank=True)
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
        if self.mode == self.AI:
            # The human's key is always white_key, whichever side they play.
            return [engine.other(self.ai_side)] if secrets.compare_digest(key, self.white_key) else []
        sides = []
        if secrets.compare_digest(key, self.white_key):
            sides.append(engine.WHITE)
        if secrets.compare_digest(key, self.black_key):
            sides.append(engine.BLACK)
        return sides

    # ---- Accounts --------------------------------------------------------

    def user_sides(self, user):
        """Sides `user`'s account plays in this game."""
        if not user.is_authenticated:
            return []
        if self.mode == self.LOCAL:
            return [engine.WHITE, engine.BLACK] if self.white_player_id == user.pk else []
        sides = []
        if self.white_player_id == user.pk:
            sides.append(engine.WHITE)
        if self.black_player_id == user.pk:
            sides.append(engine.BLACK)
        return sides

    def key_for(self, user):
        """The key that lets `user` play, or "" if they are not a player."""
        sides = self.user_sides(user)
        if not sides:
            return ""
        if self.mode == self.ONLINE and sides == [engine.BLACK]:
            return self.black_key
        return self.white_key

    def result_for(self, user):
        """"won", "lost" or "playing" for a player; None for hot-seat games."""
        sides = self.user_sides(user)
        if not sides or self.mode == self.LOCAL:
            return None
        winner = self.state.get("winner")
        if not winner:
            return "playing"
        return "won" if winner in sides else "lost"

    def rating_change_for(self, user):
        """Rating points `user` won or lost in this game, or None."""
        if self.white_player_id == user.pk:
            return self.white_rating_change
        if self.black_player_id == user.pk:
            return self.black_rating_change
        return None

    def opponent_label(self, user):
        if self.mode == self.AI:
            return gettext("Computer (%(level)s)") % {"level": self.get_ai_level_display()}
        if self.mode == self.LOCAL:
            return gettext("Same screen")
        other = self.black_player if self.white_player_id == user.pk else self.white_player
        return other.username if other else gettext("Waiting for an opponent")


class TutorialProgress(models.Model):
    """A tutorial lesson completed by a logged-in user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lessons_done")
    slug = models.SlugField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "slug"], name="unique_lesson_per_user")]

    def __str__(self):
        return f"{self.user} completed {self.slug}"


class PlayerRating(models.Model):
    """A player's Elo rating from online games against other accounts."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rating")
    rating = models.IntegerField(default=INITIAL_RATING)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-rating"]

    def __str__(self):
        return f"{self.user} ({self.rating})"

    @property
    def games(self):
        return self.wins + self.losses
