"""Rythmomachy rules engine.

Pure Python, no Django: the whole game state is a JSON-serialisable dict so it
can be stored as-is in a JSONField and sent to the browser.

Board: 16 rows x 8 columns. White (even numbers) starts on rows 0-3,
Black (odd numbers) on rows 12-15. White moves first.

Movement (to an empty square only, no jumping):
  circle   - 1 square diagonally
  triangle - exactly 2 squares orthogonally
  square   - exactly 3 squares orthogonally
  pyramid  - any of the above

Captures are resolved after every move, for the side that just moved.
An enemy piece is removed when one of these holds:
  equality - one of our pieces of the same value could move onto its square
  assault  - one of our pieces lies in a straight line (orthogonal or diagonal)
             with n >= 1 empty squares in between, and value * n == target
  ambush   - two of our pieces could both move onto its square and their
             values add up to the target
  siege    - every orthogonal neighbour of the target on the board is ours
"""

from copy import deepcopy

ROWS = 16
COLS = 8
WHITE = "white"
BLACK = "black"

CIRCLE = "circle"
TRIANGLE = "triangle"
SQUARE = "square"
PYRAMID = "pyramid"

ORTHOGONAL = [(1, 0), (-1, 0), (0, 1), (0, -1)]
DIAGONAL = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
STEP = {CIRCLE: 1, TRIANGLE: 2, SQUARE: 3}

VICTORY_BODY = "body"          # capture N pieces
VICTORY_GOODS = "goods"        # capture pieces worth N in total
VICTORY_PROGRESSION = "progression"  # three pieces in progression in enemy half

VICTORY_DEFAULT_TARGET = {
    VICTORY_BODY: 12,
    VICTORY_GOODS: 500,
    VICTORY_PROGRESSION: 0,
}
VICTORY_TYPES = list(VICTORY_DEFAULT_TARGET)  # also the order they are checked in

# (row, [(col, shape, value), ...]) — pyramid values are the sum of its layers.
WHITE_SETUP = [
    (0, [(0, SQUARE, 289), (1, SQUARE, 169), (2, SQUARE, 153), (3, PYRAMID, 91),
         (4, SQUARE, 45), (5, SQUARE, 15), (6, SQUARE, 81), (7, SQUARE, 25)]),
    (1, [(0, TRIANGLE, 81), (1, TRIANGLE, 49), (2, TRIANGLE, 72), (3, TRIANGLE, 42),
         (4, TRIANGLE, 20), (5, TRIANGLE, 6), (6, TRIANGLE, 25), (7, TRIANGLE, 9)]),
    (2, [(2, CIRCLE, 64), (3, CIRCLE, 36), (4, CIRCLE, 16), (5, CIRCLE, 4)]),
    (3, [(2, CIRCLE, 8), (3, CIRCLE, 6), (4, CIRCLE, 4), (5, CIRCLE, 2)]),
]
BLACK_SETUP = [
    (15, [(0, SQUARE, 361), (1, SQUARE, 225), (2, SQUARE, 120), (3, PYRAMID, 190),
          (4, SQUARE, 66), (5, SQUARE, 28), (6, SQUARE, 121), (7, SQUARE, 49)]),
    (14, [(0, TRIANGLE, 100), (1, TRIANGLE, 64), (2, TRIANGLE, 90), (3, TRIANGLE, 56),
          (4, TRIANGLE, 30), (5, TRIANGLE, 12), (6, TRIANGLE, 36), (7, TRIANGLE, 16)]),
    (13, [(2, CIRCLE, 81), (3, CIRCLE, 49), (4, CIRCLE, 25), (5, CIRCLE, 9)]),
    (12, [(2, CIRCLE, 9), (3, CIRCLE, 7), (4, CIRCLE, 5), (5, CIRCLE, 3)]),
]
PYRAMID_LAYERS = {WHITE: [36, 25, 16, 9, 4, 1], BLACK: [64, 49, 36, 25, 16]}


class IllegalMove(ValueError):
    """Raised for a move or action the rules do not allow.

    `code` is one of: game_over, empty_square, not_your_turn, illegal_destination.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def other(side):
    return BLACK if side == WHITE else WHITE


def on_board(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS


def new_game(victory=VICTORY_BODY, target=None, victories=None):
    """A fresh game.

    `victories` maps each enabled victory type to its target (None for the
    default), e.g. {"body": 10, "progression": None}; the first one reached
    wins. Without it, the single `victory` / `target` pair is used.
    """
    if victories is None:
        victories = {victory: target}
    if not victories:
        raise ValueError("at least one victory type is required")
    for kind in victories:
        if kind not in VICTORY_DEFAULT_TARGET:
            raise ValueError(f"unknown victory type: {kind}")
    victories = {
        kind: VICTORY_DEFAULT_TARGET[kind] if victories[kind] is None else victories[kind]
        for kind in VICTORY_TYPES
        if kind in victories
    }
    pieces = []
    for side, setup in ((WHITE, WHITE_SETUP), (BLACK, BLACK_SETUP)):
        for row, entries in setup:
            for col, shape, value in entries:
                piece = {
                    "id": f"{side[0]}{row}{col}",
                    "side": side,
                    "shape": shape,
                    "value": value,
                    "r": row,
                    "c": col,
                }
                if shape == PYRAMID:
                    piece["layers"] = PYRAMID_LAYERS[side]
                pieces.append(piece)
    return {
        "pieces": pieces,
        "turn": WHITE,
        "captured": {WHITE: [], BLACK: []},  # pieces captured BY that side
        "winner": None,
        "win_reason": None,
        "log": [],
        "victories": victories,
    }


def victories(state):
    """{victory type: target} for a state. Games saved before victory types
    could be combined store a single "victory" and "target" instead."""
    if "victories" in state:
        return state["victories"]
    return {state["victory"]: state["target"]}


def _grid(state):
    return {(p["r"], p["c"]): p for p in state["pieces"]}


def _patterns(shape):
    """(dr, dc, distance) move patterns for a shape."""
    if shape == PYRAMID:
        shapes = (CIRCLE, TRIANGLE, SQUARE)
    else:
        shapes = (shape,)
    out = []
    for s in shapes:
        dirs = DIAGONAL if s == CIRCLE else ORTHOGONAL
        out.extend((dr, dc, STEP[s]) for dr, dc in dirs)
    return out


def _path_clear(grid, r, c, dr, dc, dist):
    """True if every square strictly between (r,c) and the destination is empty."""
    return all((r + dr * i, c + dc * i) not in grid for i in range(1, dist))


def reach(piece, grid):
    """Squares the piece could land on if they were empty (path must be clear)."""
    out = []
    r, c = piece["r"], piece["c"]
    for dr, dc, dist in _patterns(piece["shape"]):
        tr, tc = r + dr * dist, c + dc * dist
        if on_board(tr, tc) and _path_clear(grid, r, c, dr, dc, dist):
            out.append((tr, tc))
    return out


def legal_moves(state, side=None):
    """{piece_id: [(r, c), ...]} for the side to move (or `side`)."""
    if state["winner"]:
        return {}
    side = side or state["turn"]
    grid = _grid(state)
    moves = {}
    for p in state["pieces"]:
        if p["side"] != side:
            continue
        targets = [sq for sq in reach(p, grid) if sq not in grid]
        if targets:
            moves[p["id"]] = targets
    return moves


def find_captures(state, side):
    """Enemy pieces `side` captures in the current position: [(piece, rule, detail)]."""
    grid = _grid(state)
    ours = [p for p in state["pieces"] if p["side"] == side]
    reaches = {p["id"]: set(reach(p, grid)) for p in ours}
    found = []
    for enemy in state["pieces"]:
        if enemy["side"] == side:
            continue
        hit = _capture_rule(enemy, ours, reaches, grid, side)
        if hit:
            found.append((enemy, *hit))
    return found


def _capture_rule(enemy, ours, reaches, grid, side):
    sq = (enemy["r"], enemy["c"])
    value = enemy["value"]
    attackers = [p for p in ours if sq in reaches[p["id"]]]

    for p in attackers:
        if p["value"] == value:
            return "equality", f"{p['value']} = {value}"

    for dr, dc in ORTHOGONAL + DIAGONAL:
        r, c = sq[0] + dr, sq[1] + dc
        gap = 0
        while on_board(r, c) and (r, c) not in grid:
            gap += 1
            r, c = r + dr, c + dc
        if gap and on_board(r, c):
            p = grid[(r, c)]
            if p["side"] == side and p["value"] * gap == value:
                return "assault", f"{p['value']} × {gap} = {value}"

    for i, a in enumerate(attackers):
        for b in attackers[i + 1:]:
            if a["value"] + b["value"] == value:
                return "ambush", f"{a['value']} + {b['value']} = {value}"

    neighbours = [(sq[0] + dr, sq[1] + dc) for dr, dc in ORTHOGONAL]
    neighbours = [n for n in neighbours if on_board(*n)]
    if all(n in grid and grid[n]["side"] == side for n in neighbours):
        return "siege", ""

    return None


def progression(values):
    """Name of the progression formed by three values in order, or None."""
    a, b, c = values
    if len({a, b, c}) < 3:
        return None
    if b - a == c - b:
        return "arithmetic"
    if b * b == a * c:
        return "geometric"
    if b * (a + c) == 2 * a * c:
        return "harmonic"
    return None


def find_progression(state, side):
    """Three adjacent pieces of `side` in a line inside the enemy half forming a
    progression. Returns (kind, [values]) or None."""
    grid = _grid(state)
    enemy_half = range(ROWS // 2, ROWS) if side == WHITE else range(0, ROWS // 2)
    for p in state["pieces"]:
        if p["side"] != side or p["r"] not in enemy_half:
            continue
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            line = [p]
            for i in (1, 2):
                q = grid.get((p["r"] + dr * i, p["c"] + dc * i))
                if not q or q["side"] != side or q["r"] not in enemy_half:
                    break
                line.append(q)
            if len(line) == 3:
                values = [q["value"] for q in line]
                kind = progression(values)
                if kind:
                    return kind, values
    return None


def _check_winner(state, side):
    """Why `side` has won, as {"code": ..., **params}, or None."""
    captured = state["captured"][side]
    enabled = victories(state)
    if VICTORY_BODY in enabled and len(captured) >= enabled[VICTORY_BODY]:
        return {"code": VICTORY_BODY, "count": len(captured)}
    if VICTORY_GOODS in enabled:
        total = sum(p["value"] for p in captured)
        if total >= enabled[VICTORY_GOODS]:
            return {"code": VICTORY_GOODS, "total": total}
    if VICTORY_PROGRESSION in enabled:
        found = find_progression(state, side)
        if found:
            kind, values = found
            return {"code": VICTORY_PROGRESSION, "kind": kind, "values": values}
    if not any(p["side"] == other(side) for p in state["pieces"]):
        return {"code": "annihilation"}
    if not legal_moves(state, other(side)):
        return {"code": "no_moves"}
    return None


def _play(state, piece, to):
    """Move `piece` (a dict inside `state`) to `to`, resolve captures and
    victory, and pass the turn. Mutates `state`; returns the captures."""
    side = piece["side"]
    piece["r"], piece["c"] = to
    captures = find_captures(state, side)
    captured_ids = {enemy["id"] for enemy, _, _ in captures}
    state["pieces"] = [p for p in state["pieces"] if p["id"] not in captured_ids]
    for enemy, _, _ in captures:
        state["captured"][side].append(enemy)
    reason = _check_winner(state, side)
    if reason:
        state["winner"], state["win_reason"] = side, reason
    else:
        state["turn"] = other(side)
    return captures


def simulate(state, piece_id, to):
    """Fast, unvalidated move for search: returns (new_state, captures).

    Pieces and captured lists are copied, the move log is shared and left
    untouched. Only use with moves taken from legal_moves().
    """
    pieces = [dict(p) for p in state["pieces"]]
    new = {
        **state,
        "pieces": pieces,
        "captured": {side: list(lst) for side, lst in state["captured"].items()},
    }
    piece = next(p for p in pieces if p["id"] == piece_id)
    return new, _play(new, piece, tuple(to))


def apply_move(state, frm, to):
    """Return a new state after the side to move plays frm -> to.

    frm and to are (row, col) pairs. Raises IllegalMove.
    """
    if state["winner"]:
        raise IllegalMove("game_over", "the game is over")
    frm, to = tuple(frm), tuple(to)
    state = deepcopy(state)
    side = state["turn"]
    piece = _grid(state).get(frm)
    if piece is None:
        raise IllegalMove("empty_square", "no piece on that square")
    if piece["side"] != side:
        raise IllegalMove("not_your_turn", f"it is {side}'s turn")
    if to not in legal_moves(state).get(piece["id"], []):
        raise IllegalMove("illegal_destination", "that piece cannot move there")

    captures = _play(state, piece, to)
    state["log"].append({
        "n": len(state["log"]) + 1,
        "side": side,
        "shape": piece["shape"],
        "value": piece["value"],
        "from": list(frm),
        "to": list(to),
        "captures": [
            {"shape": e["shape"], "value": e["value"], "rule": rule, "detail": detail}
            for e, rule, detail in captures
        ],
    })
    return state


def resign(state, side):
    if state["winner"]:
        raise IllegalMove("game_over", "the game is over")
    state = deepcopy(state)
    state["winner"] = other(side)
    state["win_reason"] = {"code": "resigned", "side": side}
    return state
