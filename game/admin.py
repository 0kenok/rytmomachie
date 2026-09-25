from django.contrib import admin

from .models import Game, PlayerRating


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "mode", "version", "created_at", "updated_at"]
    list_filter = ["mode"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(PlayerRating)
class PlayerRatingAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "wins", "losses"]
    search_fields = ["user__username"]
