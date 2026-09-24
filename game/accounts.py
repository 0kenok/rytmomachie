"""Sign up, log in, account page. Built on django.contrib.auth."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.signals import user_logged_in
from django.db.models import Q
from django.dispatch import receiver
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from . import tutorial
from .models import Game, TutorialProgress
from .tutorial_views import DONE_KEY


@receiver(user_logged_in)
def keep_tutorial_progress(sender, request, user, **kwargs):
    """Lessons finished before logging in count for the account too."""
    for slug in request.session.get(DONE_KEY, []):
        if slug in tutorial.BY_SLUG:
            TutorialProgress.objects.get_or_create(user=user, slug=slug)


def _next_url(request, default):
    url = request.POST.get("next") or request.GET.get("next")
    if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, request.is_secure()):
        return url
    return default


def signup(request):
    if request.user.is_authenticated:
        return redirect("game:account")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, _("Welcome, %(name)s! Your account is ready.") % {"name": user.username})
        return redirect(_next_url(request, reverse("game:account")))
    return render(request, "game/account/signup.html", {"form": form, "next": _next_url(request, "")})


class LoginView(auth_views.LoginView):
    template_name = "game/account/login.html"
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("game:home")


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "game/account/password_change.html"
    success_url = reverse_lazy("game:account")

    def form_valid(self, form):
        messages.success(self.request, _("Your password has been changed."))
        return super().form_valid(form)


@login_required
def account(request):
    user = request.user
    games = (
        Game.objects.filter(Q(white_player=user) | Q(black_player=user))
        .select_related("white_player", "black_player")
        .order_by("-updated_at")
    )
    rows = []
    stats = {"won": 0, "lost": 0, "playing": 0}
    for game in games:
        result = game.result_for(user)
        if result:
            stats[result] += 1
        sides = game.user_sides(user)
        rows.append({
            "game": game,
            "result": result,
            "finished": bool(game.state.get("winner")),
            "side": sides[0] if len(sides) == 1 else "",
            "opponent": game.opponent_label(user),
            "moves": len(game.state.get("log", [])),
            "url": f"{reverse('game:play', args=[game.id])}?key={game.key_for(user)}",
        })
    done = set(TutorialProgress.objects.filter(user=user).values_list("slug", flat=True))
    done &= set(tutorial.BY_SLUG)
    return render(request, "game/account/account.html", {
        "rows": rows,
        "stats": stats,
        "lessons_done": len(done),
        "lessons_total": len(tutorial.LESSONS),
    })
