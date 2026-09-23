from django.contrib import admin

from .models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "mode", "version", "created_at", "updated_at"]
    list_filter = ["mode"]
    readonly_fields = ["id", "created_at", "updated_at"]
