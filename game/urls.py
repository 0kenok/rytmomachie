from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("", views.home, name="home"),
    path("rules/", views.rules, name="rules"),
    path("new/", views.create_game, name="create"),
    path("game/<uuid:game_id>/", views.play, name="play"),
    path("game/<uuid:game_id>/state/", views.state, name="state"),
    path("game/<uuid:game_id>/move/", views.move, name="move"),
    path("game/<uuid:game_id>/resign/", views.resign, name="resign"),
    path("game/<uuid:game_id>/bot/", views.bot_move, name="bot"),
]
