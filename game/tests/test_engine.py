from django.test import SimpleTestCase

from game import engine
from game.engine import BLACK, CIRCLE, PYRAMID, SQUARE, TRIANGLE, WHITE


def piece(side, shape, value, r, c, pid=None):
    return {"id": pid or f"{side[0]}{r}-{c}", "side": side, "shape": shape,
            "value": value, "r": r, "c": c}


def position(*pieces, turn=WHITE, victory=engine.VICTORY_BODY, target=12):
    state = engine.new_game(victory, target)
    state["pieces"] = list(pieces)
    state["turn"] = turn
    return state


class SetupTests(SimpleTestCase):
    def test_each_side_has_24_pieces(self):
        state = engine.new_game()
        for side in (WHITE, BLACK):
            mine = [p for p in state["pieces"] if p["side"] == side]
            self.assertEqual(len(mine), 24)
            shapes = [p["shape"] for p in mine]
            self.assertEqual(shapes.count(CIRCLE), 8)
            self.assertEqual(shapes.count(TRIANGLE), 8)
            self.assertEqual(shapes.count(SQUARE), 7)
            self.assertEqual(shapes.count(PYRAMID), 1)

    def test_pyramid_value_is_sum_of_layers(self):
        state = engine.new_game()
        for p in state["pieces"]:
            if p["shape"] == PYRAMID:
                self.assertEqual(p["value"], sum(p["layers"]))

    def test_unique_squares_and_ids(self):
        state = engine.new_game()
        self.assertEqual(len({(p["r"], p["c"]) for p in state["pieces"]}), 48)
        self.assertEqual(len({p["id"] for p in state["pieces"]}), 48)

    def test_white_moves_first_and_has_moves(self):
        state = engine.new_game()
        self.assertEqual(state["turn"], WHITE)
        self.assertTrue(engine.legal_moves(state))

    def test_unknown_victory_rejected(self):
        with self.assertRaises(ValueError):
            engine.new_game("nope")


class MovementTests(SimpleTestCase):
    def targets(self, p, *others):
        state = position(p, *others)
        return set(engine.legal_moves(state).get(p["id"], []))

    def test_circle_moves_one_diagonal(self):
        p = piece(WHITE, CIRCLE, 4, 5, 3)
        self.assertEqual(self.targets(p), {(6, 4), (6, 2), (4, 4), (4, 2)})

    def test_triangle_moves_two_orthogonal(self):
        p = piece(WHITE, TRIANGLE, 6, 5, 3)
        self.assertEqual(self.targets(p), {(7, 3), (3, 3), (5, 5), (5, 1)})

    def test_square_moves_three_orthogonal_within_board(self):
        p = piece(WHITE, SQUARE, 15, 1, 1)
        self.assertEqual(self.targets(p), {(4, 1), (1, 4)})

    def test_pyramid_moves_like_all_shapes(self):
        p = piece(WHITE, PYRAMID, 91, 6, 4)
        self.assertEqual(len(self.targets(p)), 4 + 4 + 4)

    def test_no_jumping(self):
        p = piece(WHITE, TRIANGLE, 6, 5, 3)
        blocker = piece(WHITE, CIRCLE, 2, 6, 3)
        self.assertNotIn((7, 3), self.targets(p, blocker))

    def test_cannot_move_onto_occupied_square(self):
        p = piece(WHITE, CIRCLE, 4, 5, 3)
        enemy = piece(BLACK, CIRCLE, 9, 6, 4)
        self.assertNotIn((6, 4), self.targets(p, enemy))

    def test_illegal_moves_raise(self):
        state = position(piece(WHITE, CIRCLE, 4, 5, 3), piece(BLACK, CIRCLE, 3, 10, 3))
        with self.assertRaises(engine.IllegalMove):
            engine.apply_move(state, (5, 3), (6, 3))  # circles move diagonally
        with self.assertRaises(engine.IllegalMove):
            engine.apply_move(state, (10, 3), (9, 4))  # not black's turn
        with self.assertRaises(engine.IllegalMove):
            engine.apply_move(state, (0, 0), (1, 1))  # empty square

    def test_move_switches_turn_and_logs(self):
        state = engine.new_game()
        after = engine.apply_move(state, (3, 2), (4, 1))
        self.assertEqual(after["turn"], BLACK)
        self.assertEqual(after["log"][0]["to"], [4, 1])
        self.assertEqual(state["turn"], WHITE, "original state must not be mutated")


class CaptureTests(SimpleTestCase):
    def test_equality(self):
        state = position(
            piece(WHITE, CIRCLE, 9, 5, 2),
            piece(BLACK, CIRCLE, 9, 7, 4),
            piece(BLACK, CIRCLE, 3, 14, 0),
        )
        after = engine.apply_move(state, (5, 2), (6, 3))
        self.assertEqual([p["value"] for p in after["captured"][WHITE]], [9])
        self.assertEqual(after["log"][-1]["captures"][0]["rule"], "equality")

    def test_equality_needs_clear_path(self):
        state = position(
            piece(WHITE, TRIANGLE, 20, 6, 3),
            piece(WHITE, CIRCLE, 4, 7, 1),  # blocks the triangle's path to (8, 1)
            piece(BLACK, CIRCLE, 20, 8, 1),
            piece(BLACK, CIRCLE, 3, 14, 7),
        )
        after = engine.apply_move(state, (6, 3), (6, 1))
        self.assertEqual(after["captured"][WHITE], [])

        del state["pieces"][1]
        after = engine.apply_move(state, (6, 3), (6, 1))
        self.assertEqual([p["value"] for p in after["captured"][WHITE]], [20])

    def test_assault(self):
        # 5 empty squares between a 4 and a 20 on a column: 4 x 5 = 20.
        state = position(
            piece(WHITE, CIRCLE, 4, 1, 1),
            piece(BLACK, TRIANGLE, 20, 8, 2),
            piece(BLACK, CIRCLE, 3, 14, 7),
        )
        after = engine.apply_move(state, (1, 1), (2, 2))
        self.assertEqual([p["value"] for p in after["captured"][WHITE]], [20])
        self.assertEqual(after["log"][-1]["captures"][0]["rule"], "assault")

    def test_assault_blocked(self):
        state = position(
            piece(WHITE, CIRCLE, 4, 1, 1),
            piece(WHITE, SQUARE, 15, 5, 2),
            piece(BLACK, TRIANGLE, 20, 8, 2),
            piece(BLACK, CIRCLE, 3, 14, 7),
        )
        after = engine.apply_move(state, (1, 1), (2, 2))
        self.assertEqual(after["captured"][WHITE], [])

    def test_ambush(self):
        # Circle 2 and triangle 4 can both move onto the 6: 2 + 4 = 6.
        state = position(
            piece(WHITE, CIRCLE, 2, 6, 2),
            piece(WHITE, TRIANGLE, 4, 9, 5),
            piece(BLACK, SQUARE, 6, 7, 3),
            piece(BLACK, CIRCLE, 3, 14, 7),
        )
        after = engine.apply_move(state, (9, 5), (7, 5))
        self.assertEqual([p["value"] for p in after["captured"][WHITE]], [6])
        self.assertEqual(after["log"][-1]["captures"][0]["rule"], "ambush")

    def test_siege(self):
        state = position(
            piece(WHITE, SQUARE, 15, 8, 3),
            piece(WHITE, SQUARE, 45, 7, 4),
            piece(WHITE, SQUARE, 153, 8, 5),
            piece(WHITE, CIRCLE, 64, 10, 3),
            piece(BLACK, SQUARE, 361, 8, 4),
            piece(BLACK, CIRCLE, 3, 14, 7),
        )
        after = engine.apply_move(state, (10, 3), (9, 4))
        self.assertEqual([p["value"] for p in after["captured"][WHITE]], [361])
        self.assertEqual(after["log"][-1]["captures"][0]["rule"], "siege")


class VictoryTests(SimpleTestCase):
    def test_body_victory(self):
        state = position(
            piece(WHITE, CIRCLE, 9, 5, 2),
            piece(BLACK, CIRCLE, 9, 7, 4),
            piece(BLACK, CIRCLE, 3, 14, 0),
            target=1,
        )
        after = engine.apply_move(state, (5, 2), (6, 3))
        self.assertEqual(after["winner"], WHITE)

    def test_goods_victory(self):
        state = position(
            piece(WHITE, CIRCLE, 9, 5, 2),
            piece(BLACK, CIRCLE, 9, 7, 4),
            piece(BLACK, CIRCLE, 3, 14, 0),
            victory=engine.VICTORY_GOODS, target=9,
        )
        self.assertEqual(engine.apply_move(state, (5, 2), (6, 3))["winner"], WHITE)

    def test_progressions(self):
        self.assertEqual(engine.progression([2, 4, 6]), "arithmetic")
        self.assertEqual(engine.progression([4, 16, 64]), "geometric")
        self.assertEqual(engine.progression([3, 4, 6]), "harmonic")
        self.assertIsNone(engine.progression([4, 4, 4]))
        self.assertIsNone(engine.progression([2, 5, 6]))

    def test_progression_victory_only_in_enemy_half(self):
        state = position(
            piece(WHITE, CIRCLE, 2, 9, 1),
            piece(WHITE, CIRCLE, 4, 9, 2),
            piece(WHITE, CIRCLE, 6, 8, 2),
            piece(BLACK, CIRCLE, 3, 15, 7),
            victory=engine.VICTORY_PROGRESSION,
        )
        after = engine.apply_move(state, (8, 2), (9, 3))
        self.assertEqual(after["winner"], WHITE)
        self.assertEqual(after["win_reason"], {"code": "progression", "kind": "arithmetic", "values": [2, 4, 6]})

        state["pieces"] = [
            piece(WHITE, CIRCLE, 2, 6, 1),
            piece(WHITE, CIRCLE, 4, 6, 2),
            piece(WHITE, CIRCLE, 6, 5, 2),
            piece(BLACK, CIRCLE, 3, 15, 7),
        ]
        after = engine.apply_move(state, (5, 2), (6, 3))
        self.assertIsNone(after["winner"])

    def test_no_moves_loses(self):
        state = position(
            piece(WHITE, CIRCLE, 4, 5, 3),
            piece(BLACK, CIRCLE, 3, 15, 0),
            piece(WHITE, CIRCLE, 10, 14, 1),  # blocks black's only move
        )
        after = engine.apply_move(state, (5, 3), (6, 4))
        self.assertEqual(after["winner"], WHITE)
        self.assertEqual(after["win_reason"], {"code": "no_moves"})

    def test_resign_and_no_moves_after_game_over(self):
        state = engine.resign(engine.new_game(), WHITE)
        self.assertEqual(state["winner"], BLACK)
        self.assertEqual(engine.legal_moves(state), {})
        with self.assertRaises(engine.IllegalMove):
            engine.apply_move(state, (3, 2), (4, 1))
