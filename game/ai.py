"""Computer opponent for Rythmomachy.

Levels:
  1 beginner - random moves, takes a capture about half the time
  2 easy     - looks two moves ahead like medium, but with a lot of randomness
  3 medium   - looks two moves ahead (its move and your reply)
  4 hard     - iterative deepening alpha-beta, up to three moves ahead

Search is negamax with alpha-beta pruning over engine.simulate(). Because
captures are resolved for the side that just moved, whatever the side to move
can capture right now is effectively already won; the evaluation counts it,
which makes even shallow searches aware of hanging pieces.
"""

import math
import random
import time

from . import engine

BEGINNER, EASY, MEDIUM, HARD = 1, 2, 3, 4
LEVELS = (BEGINNER, EASY, MEDIUM, HARD)

# depth, random noise added to root scores, time budget in seconds
SETTINGS = {
    EASY: (2, 130.0, 2.0),
    MEDIUM: (2, 12.0, 3.0),
    HARD: (3, 0.0, 5.0),
}

WIN = 1_000_000


class _Timeout(Exception):
    pass


def worth(piece, victory):
    """How much a piece matters, depending on how the game is won."""
    if victory == engine.VICTORY_GOODS:
        base = 20 + piece["value"]
    else:
        base = 100 + 4 * math.sqrt(piece["value"])
    if piece["shape"] == engine.PYRAMID:
        base *= 1.5
    return base


def _advance(piece):
    """Rows travelled towards the enemy (0 on the home edge)."""
    return piece["r"] if piece["side"] == engine.WHITE else engine.ROWS - 1 - piece["r"]


def evaluate(state, side):
    """Static score of `state` from the point of view of `side`, who is to move."""
    victory = state["victory"]
    progression = victory == engine.VICTORY_PROGRESSION
    advance_weight = 5 if progression else 1
    score = 0.0
    for p in state["pieces"]:
        value = worth(p, victory) + advance_weight * _advance(p)
        if progression and _advance(p) >= engine.ROWS // 2:
            value += 15
        score += value if p["side"] == side else -value
    # Enemy pieces we attack right now fall on our next move whatever we play.
    for enemy, _, _ in engine.find_captures(state, side):
        score += 0.9 * worth(enemy, victory)
    return score


def _children(state):
    """(gain, piece_id, square, child_state) for every legal move, captures first."""
    victory = state["victory"]
    out = []
    for pid, squares in engine.legal_moves(state).items():
        for sq in squares:
            child, captures = engine.simulate(state, pid, sq)
            gain = sum(worth(e, victory) for e, _, _ in captures)
            if child["winner"]:
                gain += WIN
            out.append((gain, pid, sq, child))
    out.sort(key=lambda t: -t[0])
    return out


def _negamax(state, depth, alpha, beta, deadline):
    if time.monotonic() > deadline:
        raise _Timeout
    if state["winner"]:
        # The previous player just won; prefer losing later rather than sooner.
        return -WIN - depth
    if depth == 0:
        return evaluate(state, state["turn"])
    children = _children(state)
    if not children:
        return evaluate(state, state["turn"])
    best = -math.inf
    for _, _, _, child in children:
        score = -_negamax(child, depth - 1, -beta, -alpha, deadline)
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def _search(state, max_depth, noise, time_limit, rng):
    deadline = time.monotonic() + time_limit
    children = _children(state)
    if len(children) == 1:
        return children[0][1:3]
    best_move = children[0][1:3]
    for depth in range(1, max_depth + 1):
        try:
            scored = []
            alpha = -math.inf
            for _, pid, sq, child in children:
                # A move scoring 2 * noise below the best so far can't win even
                # with maximum noise, so its exact score isn't needed.
                score = -_negamax(child, depth - 1, -math.inf, -alpha + 2 * noise, deadline)
                score += rng.uniform(-noise, noise) if noise else 0
                scored.append((score, pid, sq, child))
                alpha = max(alpha, score)
        except _Timeout:
            break  # keep the best move of the last completed depth
        scored.sort(key=lambda t: -t[0])
        best_move = scored[0][1:3]
        # Search the most promising moves first at the next depth.
        children = scored
        if scored[0][0] >= WIN:
            break
    return best_move


def choose_move(state, level, rng=None, time_limit=None):
    """Pick a move for the side to move. Returns ((r, c), (r, c)) or None."""
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    if state["winner"]:
        return None
    rng = rng or random.Random()
    moves = engine.legal_moves(state)
    if not moves:
        return None

    if level == BEGINNER:
        if rng.random() < 0.5:
            best = _children(state)[0]
            if best[0] > 0:
                pid, sq = best[1:3]
                return _as_squares(state, pid, sq)
        pid = rng.choice(sorted(moves))
        return _as_squares(state, pid, rng.choice(moves[pid]))

    depth, noise, budget = SETTINGS[level]
    pid, sq = _search(state, depth, noise, time_limit or budget, rng)
    return _as_squares(state, pid, sq)


def _as_squares(state, pid, sq):
    piece = next(p for p in state["pieces"] if p["id"] == pid)
    return (piece["r"], piece["c"]), tuple(sq)
