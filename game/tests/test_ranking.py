import json

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game import engine, ranking
from game.models import INITIAL_RATING, Game, PlayerRating
from game.tests.test_engine import piece, position


class EloTests(TestCase):
    def test_even_players_swap_half_of_k(self):
        self.assertEqual(ranking.rating_change(1200, 1200), ranking.K_FACTOR // 2)

    def test_upset_is_worth_more(self):
        upset = ranking.rating_change(1000, 1400)
        expected = ranking.rating_change(1400, 1000)
        self.assertGreater(upset, expected)
        self.assertEqual(upset + expected, ranking.K_FACTOR)


class RankingTests(TestCase):
    def setUp(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")

    def game(self, mode=Game.ONLINE, white=None, black=None):
        return Game.objects.create(
            mode=mode, state=engine.new_game(),
            white_player=white or self.alice, black_player=black or self.bob,
        )

    def resign(self, game, key):
        return self.client.post(
            reverse("game:resign", args=[game.id]),
            json.dumps({"key": key}), content_type="application/json",
        )

    def rating(self, user):
        return PlayerRating.objects.get(user=user)

    def test_finished_online_game_updates_ratings(self):
        game = self.game()
        self.resign(game, game.black_key)
        alice, bob = self.rating(self.alice), self.rating(self.bob)
        self.assertEqual(alice.rating, INITIAL_RATING + 16)
        self.assertEqual(bob.rating, INITIAL_RATING - 16)
        self.assertEqual((alice.wins, alice.losses, bob.wins, bob.losses), (1, 0, 0, 1))
        game.refresh_from_db()
        self.assertEqual((game.white_rating_change, game.black_rating_change), (16, -16))
        self.assertEqual(game.rating_change_for(self.bob), -16)

    def test_winning_move_updates_ratings(self):
        game = self.game()
        game.state = position(
            piece(engine.WHITE, engine.CIRCLE, 9, 5, 2),
            piece(engine.BLACK, engine.CIRCLE, 9, 7, 4),
            piece(engine.BLACK, engine.CIRCLE, 3, 14, 0),
            target=1,
        )
        game.save()
        res = self.client.post(
            reverse("game:move", args=[game.id]),
            json.dumps({"key": game.white_key, "from": [5, 2], "to": [6, 3]}),
            content_type="application/json",
        )
        self.assertEqual(res.json()["winner"], engine.WHITE)
        self.assertEqual(self.rating(self.alice).rating, INITIAL_RATING + 16)

    def test_result_is_recorded_once(self):
        game = self.game()
        self.resign(game, game.black_key)
        game.refresh_from_db()
        ranking.record_result(game)
        self.assertEqual(self.rating(self.alice).wins, 1)

    def test_unrated_games(self):
        unrated = [
            self.game(mode=Game.AI),
            self.game(mode=Game.LOCAL),
            self.game(black=self.alice),  # same account on both sides
        ]
        anonymous = self.game()
        anonymous.black_player = None
        anonymous.save()
        for game in [*unrated, anonymous]:
            self.resign(game, game.white_key)
        self.assertFalse(PlayerRating.objects.exists())
        self.assertFalse(Game.objects.filter(white_rating_change__isnull=False).exists())

    def test_leaderboard_ranks_ties_together(self):
        carol = User.objects.create_user("carol")
        PlayerRating.objects.create(user=self.alice, rating=1250, wins=2)
        PlayerRating.objects.create(user=self.bob, rating=1250, wins=1, losses=1)
        PlayerRating.objects.create(user=carol, rating=1100, losses=3)
        PlayerRating.objects.create(user=User.objects.create_user("dave"))  # no games yet
        rows = ranking.leaderboard()
        self.assertEqual([(r.user.username, r.rank) for r in rows], [("alice", 1), ("bob", 1), ("carol", 3)])

    def test_leaderboard_page(self):
        self.assertContains(self.client.get(reverse("game:leaderboard")), "No rated games")
        game = self.game()
        self.resign(game, game.white_key)
        self.client.force_login(self.bob)
        res = self.client.get(reverse("game:leaderboard"))
        self.assertContains(res, 'class="you" aria-current="true"')
        self.assertContains(res, f"<strong>{INITIAL_RATING + 16}</strong>")

    def test_account_shows_rating_and_change(self):
        game = self.game()
        self.resign(game, game.white_key)
        self.client.force_login(self.alice)
        res = self.client.get(reverse("game:account"))
        self.assertContains(res, f"{INITIAL_RATING - 16}")
        self.assertContains(res, "Rating · #2")
        self.assertContains(res, '<span class="rating-change down">-16</span>')
