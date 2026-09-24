import json
import random

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from game import ai, engine, tutorial


class LessonTests(SimpleTestCase):
    def play_all(self, lesson, moves, seed=0):
        state = tutorial.start(lesson)
        for mv in moves:
            state = tutorial.play(lesson, state, *mv, rng=random.Random(seed))
        return state

    def test_slugs_are_unique(self):
        self.assertEqual(len(tutorial.BY_SLUG), len(tutorial.LESSONS))

    def test_every_lesson_starts_in_play(self):
        for lesson in tutorial.LESSONS:
            state = tutorial.start(lesson)
            self.assertEqual(tutorial.status(lesson, state), tutorial.PLAYING, lesson.slug)
            self.assertTrue(engine.legal_moves(state), lesson.slug)
            self.assertTrue(engine.legal_moves(state, engine.BLACK), lesson.slug)

    def test_solutions_solve_their_lesson(self):
        for lesson in tutorial.LESSONS:
            if not lesson.solution:
                continue
            state = self.play_all(lesson, lesson.solution)
            self.assertEqual(tutorial.status(lesson, state), tutorial.SUCCESS, lesson.slug)

    def test_wrong_move_fails_one_move_lessons(self):
        wrong = {
            "circle": ((5, 3), (4, 2)),
            "equality": ((5, 2), (4, 1)),
            "assault": ((1, 1), (2, 0)),
            "ambush": ((9, 5), (11, 5)),
            "siege": ((10, 3), (11, 4)),
            "danger": ((5, 3), (6, 4)),  # walks into the 1 + 3 ambush
        }
        for slug, mv in wrong.items():
            lesson = tutorial.get(slug)
            state = self.play_all(lesson, [mv])
            self.assertEqual(tutorial.status(lesson, state), tutorial.FAILED, slug)

    def test_black_passes_in_quiet_lessons(self):
        lesson = tutorial.get("triangle")
        state = self.play_all(lesson, lesson.solution[:1])
        self.assertEqual(state["turn"], engine.WHITE)
        self.assertEqual([m["side"] for m in state["log"]], [engine.WHITE])

    def test_no_moves_after_the_lesson_ends(self):
        lesson = tutorial.get("circle")
        state = self.play_all(lesson, lesson.solution)
        with self.assertRaises(engine.IllegalMove):
            tutorial.play(lesson, state, (6, 4), (7, 5))

    def test_mini_game_is_winnable(self):
        lesson = tutorial.get("corpore")
        rng = random.Random(0)
        state = tutorial.start(lesson)
        while tutorial.status(lesson, state) == tutorial.PLAYING:
            state = tutorial.play(lesson, state, *ai.choose_move(state, ai.MEDIUM, rng), rng=rng)
        self.assertEqual(tutorial.status(lesson, state), tutorial.SUCCESS)


class TutorialViewTests(TestCase):
    def setUp(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def move(self, slug, frm, to):
        return self.client.post(
            reverse("game:lesson_move", args=[slug]),
            json.dumps({"from": frm, "to": to}),
            content_type="application/json",
        )

    def test_index_lists_lessons(self):
        res = self.client.get(reverse("game:tutorial"))
        self.assertContains(res, "Start the first lesson")
        for lesson in tutorial.LESSONS:
            self.assertContains(res, reverse("game:lesson", args=[lesson.slug]))

    def test_lesson_page_and_state(self):
        res = self.client.get(reverse("game:lesson", args=["circle"]))
        self.assertContains(res, "The circle")
        self.assertContains(res, reverse("game:lesson", args=["triangle"]))  # next lesson
        data = self.client.get(reverse("game:lesson_state", args=["circle"])).json()
        self.assertEqual(data["highlights"], [[6, 4]])
        self.assertEqual(data["lesson"], {"status": "playing", "moves_left": 1})
        self.assertTrue(data["legal_moves"])

    def test_completing_a_lesson(self):
        data = self.move("circle", [5, 3], [6, 4]).json()
        self.assertEqual(data["lesson"]["status"], "success")
        self.assertEqual(data["legal_moves"], {})
        res = self.client.get(reverse("game:tutorial"))
        self.assertContains(res, "1 of 11 lessons completed")
        self.assertContains(res, "Continue")

    def test_failing_and_restarting(self):
        self.assertEqual(self.move("equality", [5, 2], [4, 1]).json()["lesson"]["status"], "failed")
        self.assertEqual(self.move("equality", [5, 2], [6, 3]).status_code, 400)
        res = self.client.post(reverse("game:lesson_reset", args=["equality"]))
        self.assertEqual(res.json()["lesson"]["status"], "playing")
        self.assertEqual(self.move("equality", [5, 2], [6, 3]).json()["lesson"]["status"], "success")

    def test_lessons_are_independent(self):
        self.move("circle", [5, 3], [6, 4])
        data = self.client.get(reverse("game:lesson_state", args=["triangle"])).json()
        self.assertEqual(data["lesson"]["status"], "playing")

    def test_bad_requests(self):
        self.assertEqual(self.client.get(reverse("game:lesson", args=["nope"])).status_code, 404)
        self.assertEqual(self.move("circle", [5, 3], [7, 3]).status_code, 400)
        res = self.client.post(reverse("game:lesson_move", args=["circle"]), "x", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_french(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        self.assertContains(self.client.get(reverse("game:tutorial")), "Apprendre à jouer")
        self.assertContains(self.client.get(reverse("game:lesson", args=["circle"])), "Le cercle")
