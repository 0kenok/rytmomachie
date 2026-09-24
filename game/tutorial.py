"""Interactive tutorial: short lessons, from moving a piece to winning a game.

Each lesson is a small position on the real board. The learner always plays
White. After each White move, Black either passes (the learner keeps the move)
or a computer opponent replies. A lesson is solved when its goal is met within
its move budget.

Goals:
  reach    - move a piece onto one of the marked squares
  capture  - capture an enemy piece with a given rule
  survive  - play the allowed moves without losing a piece
  win      - win the (small) game
"""

from dataclasses import dataclass, field

from django.utils.translation import gettext_lazy as _

from . import ai, engine
from .engine import BLACK, CIRCLE, PYRAMID, SQUARE, TRIANGLE, WHITE

PLAYING, SUCCESS, FAILED = "playing", "success", "failed"
PASS = "pass"

# A black piece far away, so the lesson never ends because Black has no pieces
# or no moves left.
BYSTANDER = (BLACK, CIRCLE, 3, 14, 6)


@dataclass
class Lesson:
    slug: str
    chapter: str
    title: str
    text: str
    goal_text: str
    hint: str
    pieces: list
    goal: dict
    max_moves: int
    opponent: object = PASS  # PASS or an ai level
    victory: str = engine.VICTORY_BODY
    target: int = 12
    solution: list = field(default_factory=list)  # used by the tests

    def highlights(self):
        return [list(sq) for sq in self.goal.get("squares", [])]


CHAPTER_MOVES = _("Moving")
CHAPTER_CAPTURES = _("Capturing")
CHAPTER_STRATEGY = _("Playing well")
CHAPTER_WINNING = _("Winning")

LESSONS = [
    Lesson(
        slug="circle",
        chapter=CHAPTER_MOVES,
        title=_("The circle"),
        text=_("Circles are the smallest pieces. They move exactly one square "
               "diagonally, to an empty square."),
        goal_text=_("Move your circle onto the marked square."),
        hint=_("Click your circle, then click the marked square just diagonally in front of it."),
        pieces=[(WHITE, CIRCLE, 4, 5, 3), BYSTANDER],
        goal={"type": "reach", "squares": [(6, 4)]},
        max_moves=1,
        solution=[((5, 3), (6, 4))],
    ),
    Lesson(
        slug="triangle",
        chapter=CHAPTER_MOVES,
        title=_("The triangle"),
        text=_("Triangles move exactly two squares in a straight line: forwards, "
               "backwards or sideways, never diagonally. They cannot jump over pieces."),
        goal_text=_("Bring your triangle to the marked square in two moves."),
        hint=_("Go two squares forwards, then two squares sideways (or the other way round)."),
        pieces=[(WHITE, TRIANGLE, 6, 4, 2), BYSTANDER],
        goal={"type": "reach", "squares": [(6, 4)]},
        max_moves=2,
        solution=[((4, 2), (4, 4)), ((4, 4), (6, 4))],
    ),
    Lesson(
        slug="square",
        chapter=CHAPTER_MOVES,
        title=_("The square"),
        text=_("Squares move exactly three squares in a straight line. Like every "
               "piece, they cannot jump: here your own circle blocks the way forward."),
        goal_text=_("Bring your square to the marked square. You have three moves."),
        hint=_("Go around the circle: move the square three squares sideways first."),
        pieces=[(WHITE, SQUARE, 15, 2, 1), (WHITE, CIRCLE, 2, 3, 1), BYSTANDER],
        goal={"type": "reach", "squares": [(5, 4)]},
        max_moves=3,
        solution=[((2, 1), (2, 4)), ((2, 4), (5, 4))],
    ),
    Lesson(
        slug="pyramid",
        chapter=CHAPTER_MOVES,
        title=_("The pyramid"),
        text=_("Each side has one pyramid, built from several square numbers "
               "(White's is 36 + 25 + 16 + 9 + 4 + 1 = 91). It may move like a "
               "circle, a triangle or a square."),
        goal_text=_("Bring your pyramid to the marked square in two moves."),
        hint=_("Move three squares forwards like a square, then one square diagonally like a circle."),
        pieces=[(WHITE, PYRAMID, 91, 3, 3), BYSTANDER],
        goal={"type": "reach", "squares": [(7, 4)]},
        max_moves=2,
        solution=[((3, 3), (6, 3)), ((6, 3), (7, 4))],
    ),
    Lesson(
        slug="equality",
        chapter=CHAPTER_CAPTURES,
        title=_("Capture by equality"),
        text=_("You never capture by moving onto a piece. Instead, after your move, "
               "any enemy piece that one of your pieces could move onto is captured "
               "if both pieces have the same value. Your piece stays where it is."),
        goal_text=_("Capture the black 9 with your 9."),
        hint=_("Put your circle diagonally next to the black 9."),
        pieces=[(WHITE, CIRCLE, 9, 5, 2), (BLACK, CIRCLE, 9, 7, 4), BYSTANDER],
        goal={"type": "capture", "rule": "equality"},
        max_moves=1,
        solution=[((5, 2), (6, 3))],
    ),
    Lesson(
        slug="assault",
        chapter=CHAPTER_CAPTURES,
        title=_("Capture by assault"),
        text=_("Assault uses multiplication. If one of your pieces is in a straight "
               "line with an enemy piece (diagonals count), with only empty squares "
               "between them, and your value × the number of empty squares = the "
               "enemy's value, the enemy piece is captured."),
        goal_text=_("Capture the black 20 with your 4 (4 × 5 = 20)."),
        hint=_("Line your 4 up with the 20 so that exactly five empty squares separate them."),
        pieces=[(WHITE, CIRCLE, 4, 1, 1), (BLACK, TRIANGLE, 20, 8, 2), BYSTANDER],
        goal={"type": "capture", "rule": "assault"},
        max_moves=1,
        solution=[((1, 1), (2, 2))],
    ),
    Lesson(
        slug="ambush",
        chapter=CHAPTER_CAPTURES,
        title=_("Capture by ambush"),
        text=_("Ambush uses addition. If two of your pieces could both move onto an "
               "enemy piece, and their values add up to its value, it is captured."),
        goal_text=_("Capture the black 6 with your 2 and your 4 (2 + 4 = 6)."),
        hint=_("Your 2 already reaches the 6. Move your triangle so that it reaches the 6 too."),
        pieces=[
            (WHITE, CIRCLE, 2, 6, 2), (WHITE, TRIANGLE, 4, 9, 5),
            (BLACK, SQUARE, 6, 7, 3), BYSTANDER,
        ],
        goal={"type": "capture", "rule": "ambush"},
        max_moves=1,
        solution=[((9, 5), (7, 5))],
    ),
    Lesson(
        slug="siege",
        chapter=CHAPTER_CAPTURES,
        title=_("Capture by siege"),
        text=_("A piece of any value is captured when your pieces occupy every square "
               "directly next to it: above, below, left and right. The edge of the "
               "board counts as blocked."),
        goal_text=_("Complete the siege of the black 361."),
        hint=_("Three sides are already closed. Move your 64 onto the fourth."),
        pieces=[
            (WHITE, SQUARE, 15, 8, 3), (WHITE, SQUARE, 45, 7, 4), (WHITE, SQUARE, 153, 8, 5),
            (WHITE, CIRCLE, 64, 10, 3), (BLACK, SQUARE, 361, 8, 4), BYSTANDER,
        ],
        goal={"type": "capture", "rule": "siege"},
        max_moves=1,
        solution=[((10, 3), (9, 4))],
    ),
    Lesson(
        slug="danger",
        chapter=CHAPTER_STRATEGY,
        title=_("Watch out for traps"),
        text=_("Your opponent captures in exactly the same ways. Before moving, check "
               "whether an enemy piece, or two enemy pieces together, could reach the "
               "square you are going to. From now on, the computer answers your moves."),
        goal_text=_("Move your 4 without letting Black capture it."),
        hint=_("The black 1 and 3 can both reach one of your squares, and 1 + 3 = 4. Avoid that square."),
        pieces=[
            (WHITE, CIRCLE, 4, 5, 3), (WHITE, SQUARE, 289, 0, 0),
            (BLACK, CIRCLE, 1, 7, 5), (BLACK, CIRCLE, 3, 7, 3), (BLACK, SQUARE, 361, 15, 7),
        ],
        goal={"type": "survive"},
        max_moves=1,
        opponent=ai.MEDIUM,
        solution=[((5, 3), (4, 2))],
    ),
    Lesson(
        slug="corpore",
        chapter=CHAPTER_WINNING,
        title=_("Victory de corpore"),
        text=_("The simplest way to win is to capture a set number of pieces. In "
               "this small game against the computer, the first side to capture two "
               "pieces wins."),
        goal_text=_("Capture two black pieces before Black captures two of yours."),
        hint=_("Look for equal values first: your 9 and 25 have twins on the black side."),
        pieces=[
            (WHITE, CIRCLE, 4, 5, 2), (WHITE, CIRCLE, 9, 5, 4), (WHITE, CIRCLE, 25, 5, 6),
            (WHITE, TRIANGLE, 6, 4, 3), (WHITE, TRIANGLE, 20, 4, 5),
            (BLACK, CIRCLE, 9, 10, 3), (BLACK, CIRCLE, 25, 10, 5), (BLACK, CIRCLE, 7, 10, 1),
            (BLACK, TRIANGLE, 12, 11, 2), (BLACK, TRIANGLE, 30, 11, 4),
        ],
        goal={"type": "win"},
        max_moves=40,
        opponent=ai.BEGINNER,
        target=2,
    ),
    Lesson(
        slug="magna",
        chapter=CHAPTER_WINNING,
        title=_("Victoria magna"),
        text=_("The most prestigious victory: line up three of your pieces side by "
               "side in the enemy half of the board so that their values form a "
               "progression. Arithmetic: 2, 4, 6. Geometric: 4, 16, 64. "
               "Harmonic: 3, 4, 6."),
        goal_text=_("Line up 2, 4 and 6 in the enemy half (past the middle line)."),
        hint=_("Walk your 6 diagonally until it stands right next to the 4, in the same line as the 2."),
        pieces=[
            (WHITE, CIRCLE, 2, 9, 1), (WHITE, CIRCLE, 4, 9, 2), (WHITE, CIRCLE, 6, 7, 1),
            BYSTANDER,
        ],
        goal={"type": "win"},
        max_moves=2,
        victory=engine.VICTORY_PROGRESSION,
        target=0,
        solution=[((7, 1), (8, 2)), ((8, 2), (9, 3))],
    ),
]

BY_SLUG = {lesson.slug: lesson for lesson in LESSONS}


def get(slug):
    return BY_SLUG.get(slug)


def next_lesson(lesson):
    i = LESSONS.index(lesson)
    return LESSONS[i + 1] if i + 1 < len(LESSONS) else None


def start(lesson):
    """Fresh game state for a lesson."""
    state = engine.new_game(lesson.victory, lesson.target)
    state["pieces"] = [
        {"id": f"{side[0]}{r}-{c}", "side": side, "shape": shape, "value": value, "r": r, "c": c}
        for side, shape, value, r, c in lesson.pieces
    ]
    for p in state["pieces"]:
        if p["shape"] == PYRAMID:
            p["layers"] = engine.PYRAMID_LAYERS[p["side"]]
    return state


def moves_played(state):
    return sum(1 for m in state["log"] if m["side"] == WHITE)


def status(lesson, state):
    """PLAYING, SUCCESS or FAILED for `state` in `lesson`."""
    goal = lesson.goal
    kind = goal["type"]
    played = moves_played(state)
    lost = len(state["captured"][BLACK])

    if kind == "reach":
        squares = {tuple(sq) for sq in goal["squares"]}
        if any(p["side"] == WHITE and (p["r"], p["c"]) in squares for p in state["pieces"]):
            return SUCCESS
    elif kind == "capture":
        rules = [c["rule"] for m in state["log"] if m["side"] == WHITE for c in m["captures"]]
        if goal["rule"] in rules:
            return SUCCESS
    elif kind == "survive":
        if lost:
            return FAILED
        # Solved once Black has answered the last allowed move.
        if played >= lesson.max_moves and state["turn"] == WHITE:
            return SUCCESS
    elif kind == "win":
        if state["winner"] == WHITE:
            return SUCCESS

    if state["winner"] == BLACK or played >= lesson.max_moves:
        return FAILED
    return PLAYING


def play(lesson, state, frm, to, rng=None):
    """Apply the learner's move, then Black's answer. Raises engine.IllegalMove."""
    if status(lesson, state) != PLAYING:
        raise engine.IllegalMove("game_over", "the lesson is over")
    state = engine.apply_move(state, frm, to)
    if state["winner"] or state["turn"] != BLACK:
        return state
    if lesson.opponent == PASS:
        state["turn"] = WHITE
    elif status(lesson, state) == PLAYING or lesson.goal["type"] == "survive":
        move = ai.choose_move(state, lesson.opponent, rng)
        if move:
            state = engine.apply_move(state, *move)
    return state
