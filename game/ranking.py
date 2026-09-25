"""Elo ranking for games between two accounts (online mode).

Everyone starts at models.INITIAL_RATING. When a rated game ends, the winner takes
points from the loser: more when they beat a stronger player, fewer when they
beat a weaker one. The rules have no draws, so every result is a win or a loss.
"""

from django.db.models import Q

from . import engine
from .models import Game, PlayerRating

K_FACTOR = 32


def expected_score(rating, opponent_rating):
    """Chance that a player rated `rating` beats one rated `opponent_rating`."""
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def rating_change(winner_rating, loser_rating):
    """Points the winner gains and the loser loses."""
    return round(K_FACTOR * (1 - expected_score(winner_rating, loser_rating)))


def is_rated(game):
    """Online games between two different accounts count for the ranking."""
    return (
        game.mode == Game.ONLINE
        and game.white_player_id is not None
        and game.black_player_id is not None
        and game.white_player_id != game.black_player_id
    )


def record_result(game):
    """Update both players' ratings if `game` just ended and is rated.

    Call inside the transaction that saves the final move, before game.save().
    Does nothing for an unfinished, unrated or already recorded game.
    """
    winner = game.state.get("winner")
    if not winner or game.white_rating_change is not None or not is_rated(game):
        return
    ratings = {
        r.user_id: r
        for r in PlayerRating.objects.select_for_update().filter(
            user_id__in=[game.white_player_id, game.black_player_id]
        )
    }
    for user_id in (game.white_player_id, game.black_player_id):
        if user_id not in ratings:
            ratings[user_id] = PlayerRating.objects.create(user_id=user_id)
    white = ratings[game.white_player_id]
    black = ratings[game.black_player_id]
    won, lost = (white, black) if winner == engine.WHITE else (black, white)

    points = rating_change(won.rating, lost.rating)
    won.rating += points
    won.wins += 1
    lost.rating -= points
    lost.losses += 1
    for r in (won, lost):
        r.save()
    game.white_rating_change = points if won is white else -points
    game.black_rating_change = -game.white_rating_change


def leaderboard():
    """Ratings of everyone who finished a rated game, best first, with ranks.

    Players on the same rating share a rank (1, 2, 2, 4...).
    """
    rows = list(
        PlayerRating.objects.select_related("user")
        .filter(Q(wins__gt=0) | Q(losses__gt=0))
        .order_by("-rating", "-wins", "user__username")
    )
    rank = 0
    for i, row in enumerate(rows):
        if i == 0 or row.rating != rows[i - 1].rating:
            rank = i + 1
        row.rank = rank
    return rows
