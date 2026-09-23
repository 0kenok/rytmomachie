import json

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET, require_POST

from . import engine
from .forms import NewGameForm
from .models import Game


ILLEGAL_MOVE_MESSAGES = {
    "game_over": gettext_lazy("The game is over."),
    "empty_square": gettext_lazy("There is no piece on that square."),
    "not_your_turn": gettext_lazy("It is not your turn."),
    "illegal_destination": gettext_lazy("That piece cannot move there."),
}


def _error(message, status):
    return JsonResponse({"error": str(message)}, status=status)


def _illegal(exc):
    return _error(ILLEGAL_MOVE_MESSAGES.get(exc.code, str(exc)), 400)


def home(request):
    # First visit: ask for a language before anything else.
    if settings.LANGUAGE_COOKIE_NAME not in request.COOKIES:
        return render(request, "game/choose_language.html")
    return render(request, "game/home.html", {"form": NewGameForm()})


def js_strings():
    """UI strings used by board.js, in the active language."""
    return {
        "white": _("White"),
        "black": _("Black"),
        "circle": _("circle"),
        "triangle": _("triangle"),
        "square": _("square"),
        "pyramid": _("pyramid"),
        "piece": _("%(side)s %(shape)s %(value)s"),
        "moveHere": _("move here"),
        "toMove": _("%(side)s to move"),
        # Joins a status and its detail; French puts a space before the colon.
        "withDetail": _("%(text)s: %(detail)s"),
        "logMove": _("%(piece)s: %(from)s → %(to)s"),
        "yourTurn": _("your turn"),
        "waiting": _("waiting for your opponent…"),
        "spectating": _("spectating"),
        "wins": _("%(side)s wins: %(reason)s."),
        "reason_body": _("captured %(count)s pieces"),
        "reason_goods": _("captured pieces worth %(total)s"),
        "reason_progression_arithmetic": _("arithmetic progression %(values)s"),
        "reason_progression_geometric": _("geometric progression %(values)s"),
        "reason_progression_harmonic": _("harmonic progression %(values)s"),
        "reason_annihilation": _("captured every enemy piece"),
        "reason_no_moves": _("the opponent has no legal moves"),
        "reason_resigned": _("%(side)s resigned"),
        "goal_body": _("First to capture %(target)s pieces. White %(white)s, Black %(black)s."),
        "goal_goods": _("First to capture %(target)s in value. White %(white)s, Black %(black)s."),
        "goal_progression": _("Line up three pieces in progression inside the enemy half."),
        "took": _("took %(piece)s by %(rule)s"),
        "rule_equality": _("equality"),
        "rule_assault": _("assault"),
        "rule_ambush": _("ambush"),
        "rule_siege": _("siege"),
        "resignConfirm": _("Resign this game?"),
        "copied": _("Copied"),
    }


def rules(request):
    return render(request, "game/rules.html")


@require_POST
def create_game(request):
    form = NewGameForm(request.POST)
    if not form.is_valid():
        return render(request, "game/home.html", {"form": form}, status=400)
    data = form.cleaned_data
    game = Game.objects.create(
        mode=data["mode"],
        state=engine.new_game(data["victory"], data["target"]),
    )
    return redirect(f"{reverse('game:play', args=[game.id])}?key={game.white_key}")


def play(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    key = request.GET.get("key", "")
    sides = game.sides_for(key)
    invite_url = None
    if game.mode == Game.ONLINE and engine.WHITE in sides:
        invite_url = request.build_absolute_uri(
            f"{reverse('game:play', args=[game.id])}?key={game.black_key}"
        )
    return render(request, "game/game.html", {
        "game": game,
        "key": key if sides else "",
        "sides": sides,
        "invite_url": invite_url,
        "rows": engine.ROWS,
        "cols": engine.COLS,
        "js_strings": js_strings(),
    })


def _payload(game, sides):
    s = game.state
    payload = {
        "version": game.version,
        "mode": game.mode,
        "pieces": s["pieces"],
        "turn": s["turn"],
        "captured": s["captured"],
        "winner": s["winner"],
        "win_reason": s["win_reason"],
        "log": s["log"],
        "victory": s["victory"],
        "target": s["target"],
        "your_sides": sides,
        "legal_moves": {},
    }
    if s["turn"] in sides and not s["winner"]:
        payload["legal_moves"] = {
            pid: [list(sq) for sq in squares]
            for pid, squares in engine.legal_moves(s).items()
        }
    return payload


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


@require_GET
def state(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    return JsonResponse(_payload(game, game.sides_for(request.GET.get("key", ""))))


@require_POST
def move(request, game_id):
    body = _json_body(request)
    if not isinstance(body, dict):
        return _error(_("Invalid JSON."), 400)
    try:
        frm = [int(v) for v in body["from"]]
        to = [int(v) for v in body["to"]]
        if len(frm) != 2 or len(to) != 2:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return _error(_("Expected 'from' and 'to' as [row, col]."), 400)

    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), pk=game_id)
        sides = game.sides_for(str(body.get("key", "")))
        if game.state["turn"] not in sides:
            return _error(ILLEGAL_MOVE_MESSAGES["not_your_turn"], 403)
        try:
            game.state = engine.apply_move(game.state, frm, to)
        except engine.IllegalMove as exc:
            return _illegal(exc)
        game.version += 1
        game.save()
    return JsonResponse(_payload(game, sides))


@require_POST
def resign(request, game_id):
    body = _json_body(request)
    if not isinstance(body, dict):
        return _error(_("Invalid JSON."), 400)
    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), pk=game_id)
        sides = game.sides_for(str(body.get("key", "")))
        if not sides:
            return _error(_("You are not playing in this game."), 403)
        # In hot-seat mode the player to move resigns.
        side = game.state["turn"] if len(sides) == 2 else sides[0]
        try:
            game.state = engine.resign(game.state, side)
        except engine.IllegalMove as exc:
            return _illegal(exc)
        game.version += 1
        game.save()
    return JsonResponse(_payload(game, sides))
