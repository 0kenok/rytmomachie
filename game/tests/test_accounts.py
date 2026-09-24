import json

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game import engine
from game.models import Game, TutorialProgress


class AccountTests(TestCase):
    password = "a-Long-enough-passw0rd"

    def setUp(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def make_user(self, name="alice"):
        return User.objects.create_user(name, password=self.password)

    def new_game(self, **data):
        form = {"mode": Game.AI, "victories": [engine.VICTORY_BODY], "ai_level": "1", "side": "white"}
        form.update(data)
        self.client.post(reverse("game:create"), form)
        return Game.objects.order_by("-created_at").first()

    def test_signup_logs_in_and_redirects_to_account(self):
        res = self.client.post(reverse("game:signup"), {
            "username": "bob", "password1": self.password, "password2": self.password,
        })
        self.assertRedirects(res, reverse("game:account"), fetch_redirect_response=False)
        res = self.client.get(reverse("game:account"))
        self.assertContains(res, "bob")
        self.assertContains(res, "Welcome, bob!")

    def test_signup_errors(self):
        self.make_user("bob")
        res = self.client.post(reverse("game:signup"), {
            "username": "bob", "password1": "x", "password2": "y",
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.wsgi_request.user.is_authenticated)

    def test_login_logout(self):
        self.make_user()
        res = self.client.post(reverse("game:login"), {"username": "alice", "password": self.password})
        self.assertRedirects(res, reverse("game:account"))
        self.assertContains(self.client.get(reverse("game:home")), 'class="account-link">alice<')
        res = self.client.post(reverse("game:logout"))
        self.assertRedirects(res, reverse("game:home"))
        self.assertRedirects(self.client.get(reverse("game:account")), f"{reverse('game:login')}?next=/account/")

    def test_wrong_password(self):
        self.make_user()
        res = self.client.post(reverse("game:login"), {"username": "alice", "password": "nope"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.wsgi_request.user.is_authenticated)

    def test_password_change(self):
        user = self.make_user()
        self.client.force_login(user)
        res = self.client.post(reverse("game:password_change"), {
            "old_password": self.password, "new_password1": "An0ther-long-one", "new_password2": "An0ther-long-one",
        })
        self.assertRedirects(res, reverse("game:account"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("An0ther-long-one"))

    def test_games_are_linked_and_listed(self):
        user = self.make_user()
        self.client.force_login(user)
        as_white = self.new_game()
        as_black = self.new_game(side="black")
        self.assertEqual(as_white.white_player, user)
        self.assertEqual((as_black.white_player, as_black.black_player), (None, user))

        # Won against the computer; the other game is still going.
        state = engine.resign(as_white.state, engine.BLACK)
        Game.objects.filter(pk=as_white.pk).update(state=state)

        res = self.client.get(reverse("game:account"))
        self.assertEqual(res.context["stats"], {"won": 1, "lost": 0, "playing": 1})
        self.assertContains(res, "Computer (Beginner)")
        self.assertContains(res, f"?key={as_white.white_key}")

    def test_player_recognised_without_key(self):
        user = self.make_user()
        self.client.force_login(user)
        game = self.new_game()
        res = self.client.get(reverse("game:play", args=[game.id]))
        self.assertEqual(res.context["sides"], [engine.WHITE])

    def test_anonymous_games_still_work(self):
        game = self.new_game()
        self.assertIsNone(game.white_player)
        res = self.client.post(
            reverse("game:move", args=[game.id]),
            json.dumps({"key": game.white_key, "from": [3, 2], "to": [4, 1]}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

    def test_joining_an_online_game(self):
        alice, bob = self.make_user("alice"), self.make_user("bob")
        self.client.force_login(alice)
        game = self.new_game(mode=Game.ONLINE)
        self.client.force_login(bob)
        self.client.get(reverse("game:play", args=[game.id]), {"key": game.black_key})
        game.refresh_from_db()
        self.assertEqual((game.white_player, game.black_player), (alice, bob))
        self.assertEqual(game.opponent_label(bob), "alice")
        self.assertEqual(game.key_for(bob), game.black_key)

    def test_tutorial_progress_saved_to_account(self):
        user = self.make_user()
        # Finish a lesson while logged out, then log in: it counts.
        self.client.post(
            reverse("game:lesson_move", args=["circle"]),
            json.dumps({"from": [5, 3], "to": [6, 4]}), content_type="application/json",
        )
        self.client.post(reverse("game:login"), {"username": "alice", "password": self.password})
        self.assertTrue(TutorialProgress.objects.filter(user=user, slug="circle").exists())
        # Finish another while logged in, log out: the account keeps both.
        self.client.post(
            reverse("game:lesson_move", args=["equality"]),
            json.dumps({"from": [5, 2], "to": [6, 3]}), content_type="application/json",
        )
        self.client.post(reverse("game:logout"))
        self.client.post(reverse("game:login"), {"username": "alice", "password": self.password})
        self.assertContains(self.client.get(reverse("game:tutorial")), "2 of 11 lessons completed")
        self.assertEqual(self.client.get(reverse("game:account")).context["lessons_done"], 2)

    def test_login_link_on_login_page_has_no_loop(self):
        res = self.client.get(reverse("game:login"))
        self.assertNotContains(res, "?next=/account/login/")

    def test_password_fields_have_reveal_button(self):
        for name, count in [("game:signup", 2), ("game:login", 1)]:
            res = self.client.get(reverse(name))
            self.assertContains(res, 'class="reveal-password"', count=count)
            self.assertContains(res, "Show password")
        self.client.force_login(self.make_user())
        self.assertContains(self.client.get(reverse("game:password_change")), 'class="reveal-password"', count=3)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        self.assertContains(self.client.get(reverse("game:password_change")), "Afficher le mot de passe")
