from django.urls import path

from . import accounts, tutorial_views, views

app_name = "game"

urlpatterns = [
    path("", views.home, name="home"),
    path("rules/", views.rules, name="rules"),
    path("ranking/", views.leaderboard, name="leaderboard"),
    path("new/", views.create_game, name="create"),
    path("game/<uuid:game_id>/", views.play, name="play"),
    path("game/<uuid:game_id>/state/", views.state, name="state"),
    path("game/<uuid:game_id>/move/", views.move, name="move"),
    path("game/<uuid:game_id>/resign/", views.resign, name="resign"),
    path("game/<uuid:game_id>/bot/", views.bot_move, name="bot"),
    path("account/", accounts.account, name="account"),
    path("account/signup/", accounts.signup, name="signup"),
    path("account/login/", accounts.LoginView.as_view(), name="login"),
    path("account/logout/", accounts.LogoutView.as_view(), name="logout"),
    path("account/password/", accounts.PasswordChangeView.as_view(), name="password_change"),
    path("tutorial/", tutorial_views.index, name="tutorial"),
    path("tutorial/<slug:slug>/", tutorial_views.lesson, name="lesson"),
    path("tutorial/<slug:slug>/state/", tutorial_views.state, name="lesson_state"),
    path("tutorial/<slug:slug>/move/", tutorial_views.move, name="lesson_move"),
    path("tutorial/<slug:slug>/reset/", tutorial_views.reset, name="lesson_reset"),
]
