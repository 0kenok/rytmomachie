import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from game import engine
from game.models import Game


class ViewTests(TestCase):
    def setUp(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def create(self, **data):
        form = {"mode": Game.LOCAL, "victory": engine.VICTORY_BODY, "target": ""}
        form.update(data)
        return self.client.post(reverse("game:create"), form)

    def post_json(self, name, game, body):
        return self.client.post(
            reverse(name, args=[game.id]), json.dumps(body), content_type="application/json"
        )

    def test_home_and_rules_render(self):
        self.assertContains(self.client.get(reverse("game:home")), "Start game")
        self.assertContains(self.client.get(reverse("game:rules")), "Assault")

    def test_create_redirects_with_key(self):
        res = self.create(target="5")
        game = Game.objects.get()
        self.assertRedirects(res, f"{reverse('game:play', args=[game.id])}?key={game.white_key}")
        self.assertEqual(game.state["target"], 5)

    def test_create_uses_default_target(self):
        self.create(victory=engine.VICTORY_GOODS)
        self.assertEqual(Game.objects.get().state["target"], 500)

    def test_invalid_form(self):
        self.assertEqual(self.create(victory="bogus").status_code, 400)

    def test_local_game_controls_both_sides(self):
        self.create()
        game = Game.objects.get()
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [3, 2], "to": [4, 1]})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["turn"], engine.BLACK)
        self.assertTrue(data["legal_moves"])
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [12, 2], "to": [11, 1]})
        self.assertEqual(res.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.version, 2)

    def test_online_game_enforces_sides(self):
        self.create(mode=Game.ONLINE)
        game = Game.objects.get()
        page = self.client.get(reverse("game:play", args=[game.id]), {"key": game.white_key})
        self.assertContains(page, game.black_key)  # invite link

        res = self.post_json("game:move", game, {"key": game.black_key, "from": [12, 2], "to": [11, 1]})
        self.assertEqual(res.status_code, 403)
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [3, 2], "to": [4, 1]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["legal_moves"], {})  # white waits for black
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [12, 2], "to": [11, 1]})
        self.assertEqual(res.status_code, 403)
        res = self.post_json("game:move", game, {"key": game.black_key, "from": [12, 2], "to": [11, 1]})
        self.assertEqual(res.status_code, 200)

    def test_spectator_sees_state_without_moves(self):
        self.create()
        game = Game.objects.get()
        data = self.client.get(reverse("game:state", args=[game.id])).json()
        self.assertEqual(data["your_sides"], [])
        self.assertEqual(data["legal_moves"], {})
        self.assertEqual(len(data["pieces"]), 48)
        page = self.client.get(reverse("game:play", args=[game.id]))
        self.assertNotContains(page, game.white_key)

    def test_bad_move_requests(self):
        self.create()
        game = Game.objects.get()
        url = reverse("game:move", args=[game.id])
        self.assertEqual(self.client.post(url, "nope", content_type="application/json").status_code, 400)
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [3, 2]})
        self.assertEqual(res.status_code, 400)
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [3, 2], "to": [5, 2]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot move", res.json()["error"])
        res = self.post_json("game:move", game, {"key": "wrong", "from": [3, 2], "to": [4, 1]})
        self.assertEqual(res.status_code, 403)

    def test_ai_game_as_white(self):
        self.create(mode=Game.AI, ai_level="2", side="white")
        game = Game.objects.get()
        self.assertEqual((game.ai_side, game.ai_level), (engine.BLACK, 2))
        page = self.client.get(reverse("game:play", args=[game.id]), {"key": game.white_key})
        self.assertContains(page, "against the computer")

        # Asking the bot to play out of turn changes nothing.
        res = self.post_json("game:bot", game, {"key": game.white_key})
        self.assertEqual(res.json()["version"], 0)

        res = self.post_json("game:move", game, {"key": game.white_key, "from": [3, 2], "to": [4, 1]})
        self.assertEqual(res.json()["ai"]["side"], engine.BLACK)
        # The human cannot move for the computer.
        res = self.post_json("game:move", game, {"key": game.white_key, "from": [12, 2], "to": [11, 1]})
        self.assertEqual(res.status_code, 403)

        res = self.post_json("game:bot", game, {"key": game.white_key})
        data = res.json()
        self.assertEqual((data["version"], data["turn"]), (2, engine.WHITE))
        self.assertEqual(data["log"][-1]["side"], engine.BLACK)
        self.assertTrue(data["legal_moves"])

    def test_ai_game_as_black_bot_opens(self):
        self.create(mode=Game.AI, ai_level="1", side="black")
        game = Game.objects.get()
        self.assertEqual(game.ai_side, engine.WHITE)
        self.assertEqual(game.sides_for(game.white_key), [engine.BLACK])
        data = self.post_json("game:bot", game, {"key": game.white_key}).json()
        self.assertEqual(data["turn"], engine.BLACK)
        self.assertEqual(data["your_sides"], [engine.BLACK])

    def test_ai_defaults_and_random_side(self):
        self.create(mode=Game.AI, ai_level="", side="random")
        game = Game.objects.get()
        self.assertEqual(game.ai_level, 3)
        self.assertIn(game.ai_side, [engine.WHITE, engine.BLACK])

    def test_bot_endpoint_rejects_other_modes_and_keys(self):
        self.create()
        game = Game.objects.get()
        self.assertEqual(self.post_json("game:bot", game, {"key": game.white_key}).status_code, 403)
        self.create(mode=Game.AI)
        game = Game.objects.get(mode=Game.AI)
        self.assertEqual(self.post_json("game:bot", game, {"key": "nope"}).status_code, 403)

    def test_resign(self):
        self.create(mode=Game.ONLINE)
        game = Game.objects.get()
        res = self.post_json("game:resign", game, {"key": game.black_key})
        self.assertEqual(res.json()["winner"], engine.WHITE)
        res = self.post_json("game:resign", game, {"key": game.white_key})
        self.assertEqual(res.status_code, 400)


class LanguageTests(TestCase):
    def test_first_visit_asks_for_language(self):
        res = self.client.get(reverse("game:home"))
        self.assertTemplateUsed(res, "game/choose_language.html")
        self.assertContains(res, "Français")
        self.assertContains(res, "English")

    def test_choosing_french_sets_cookie_and_translates(self):
        res = self.client.post(reverse("set_language"), {"language": "fr", "next": reverse("game:home")})
        self.assertRedirects(res, reverse("game:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fr")
        res = self.client.get(reverse("game:home"))
        self.assertTemplateUsed(res, "game/home.html")
        self.assertContains(res, "Commencer la partie")
        self.assertContains(res, '<html lang="fr">')
        self.assertContains(self.client.get(reverse("game:rules")), "Embuscade")

    def test_choosing_english(self):
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        res = self.client.get(reverse("game:home"))
        self.assertContains(res, "Start game")
        self.assertContains(self.client.get(reverse("game:rules")), "Ambush")

    def test_game_page_and_api_errors_in_french(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        game = Game.objects.create(state=engine.new_game())
        page = self.client.get(reverse("game:play", args=[game.id]), {"key": game.white_key})
        self.assertContains(page, "Abandonner")
        self.assertContains(page, "Aux %(side)s de jouer")  # string handed to board.js
        res = self.client.post(
            reverse("game:move", args=[game.id]),
            json.dumps({"key": game.white_key, "from": [3, 2], "to": [5, 2]}),
            content_type="application/json",
        )
        self.assertEqual(res.json()["error"], "Cette pièce ne peut pas aller là.")
