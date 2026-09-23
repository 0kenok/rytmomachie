import random

from django.test import SimpleTestCase

from game import ai, engine
from game.engine import BLACK, CIRCLE, SQUARE, WHITE

from .test_engine import piece, position


class ChooseMoveTests(SimpleTestCase):
    def test_every_level_returns_a_legal_move(self):
        state = engine.new_game()
        for level in ai.LEVELS:
            frm, to = ai.choose_move(state, level, random.Random(level), time_limit=2)
            engine.apply_move(state, frm, to)  # raises if illegal

    def test_plays_black_too(self):
        state = engine.apply_move(engine.new_game(), (3, 2), (4, 1))
        frm, to = ai.choose_move(state, ai.MEDIUM, random.Random(0))
        self.assertEqual(engine._grid(state)[frm]["side"], BLACK)

    def test_unknown_level(self):
        with self.assertRaises(ValueError):
            ai.choose_move(engine.new_game(), 9)

    def test_no_move_when_game_over(self):
        state = engine.resign(engine.new_game(), WHITE)
        self.assertIsNone(ai.choose_move(state, ai.HARD))

    def test_takes_a_free_piece(self):
        # Moving the 9 next to the black 9 captures it by equality.
        state = position(
            piece(WHITE, CIRCLE, 9, 5, 2),
            piece(WHITE, SQUARE, 15, 0, 7),
            piece(BLACK, CIRCLE, 9, 7, 4),
            piece(BLACK, CIRCLE, 3, 15, 0),
        )
        for level in (ai.EASY, ai.MEDIUM, ai.HARD):
            frm, to = ai.choose_move(state, level, random.Random(0))
            after = engine.apply_move(state, frm, to)
            self.assertEqual(len(after["captured"][WHITE]), 1, f"level {level}")

    def test_takes_the_win(self):
        state = position(
            piece(WHITE, CIRCLE, 2, 9, 1),
            piece(WHITE, CIRCLE, 4, 9, 2),
            piece(WHITE, CIRCLE, 6, 8, 2),
            piece(BLACK, CIRCLE, 3, 15, 7),
            victory=engine.VICTORY_PROGRESSION,
        )
        for level in (ai.MEDIUM, ai.HARD):
            after = engine.apply_move(state, *ai.choose_move(state, level, random.Random(0)))
            self.assertEqual(after["winner"], WHITE, f"level {level}")

    def test_does_not_walk_into_an_ambush(self):
        # On (6, 4) the white 4 could be reached by both the black 1 and 3,
        # which take it by ambush (1 + 3 = 4). Every other square is safe.
        state = position(
            piece(WHITE, CIRCLE, 4, 5, 3),
            piece(WHITE, SQUARE, 289, 0, 0),
            piece(BLACK, CIRCLE, 1, 7, 5),
            piece(BLACK, CIRCLE, 3, 7, 3),
            piece(BLACK, SQUARE, 361, 15, 7),
        )
        trap = engine.apply_move(state, (5, 3), (6, 4))
        self.assertEqual(
            [(e["value"], rule) for e, rule, _ in engine.find_captures(trap, BLACK)],
            [(4, "ambush")],
        )
        for level in (ai.MEDIUM, ai.HARD):
            for seed in range(3):
                frm, to = ai.choose_move(state, level, random.Random(seed))
                self.assertNotEqual(to, (6, 4), f"level {level}")

    def test_simulate_matches_apply_move(self):
        state = engine.new_game()
        rng = random.Random(4)
        for _ in range(12):
            frm, to = ai.choose_move(state, ai.BEGINNER, rng)
            pid = engine._grid(state)[frm]["id"]
            fast, _ = engine.simulate(state, pid, to)
            state = engine.apply_move(state, frm, to)
            self.assertEqual(fast["pieces"], state["pieces"])
            self.assertEqual(fast["captured"], state["captured"])
            self.assertEqual(fast["turn"], state["turn"])
