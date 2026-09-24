"""Tutorial pages. Lesson positions and progress live in the session."""

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import engine, tutorial
from .models import TutorialProgress
from .views import ILLEGAL_MOVE_MESSAGES, _error, _json_body, js_strings

STATES_KEY = "tutorial_states"
DONE_KEY = "tutorial_done"


def _lesson(slug):
    lesson = tutorial.get(slug)
    if lesson is None:
        raise Http404
    return lesson


def _state(request, lesson):
    states = request.session.get(STATES_KEY, {})
    if lesson.slug not in states:
        states[lesson.slug] = tutorial.start(lesson)
        request.session[STATES_KEY] = states
    return states[lesson.slug]


def _save(request, lesson, state):
    states = request.session.get(STATES_KEY, {})
    states[lesson.slug] = state
    request.session[STATES_KEY] = states
    if tutorial.status(lesson, state) == tutorial.SUCCESS:
        done = request.session.get(DONE_KEY, [])
        if lesson.slug not in done:
            request.session[DONE_KEY] = done + [lesson.slug]
        if request.user.is_authenticated:
            TutorialProgress.objects.get_or_create(user=request.user, slug=lesson.slug)


def _done(request):
    """Slugs of completed lessons: this session's, plus the account's."""
    done = set(request.session.get(DONE_KEY, []))
    if request.user.is_authenticated:
        done |= set(TutorialProgress.objects.filter(user=request.user).values_list("slug", flat=True))
    return done & set(tutorial.BY_SLUG)


def _payload(lesson, state):
    status = tutorial.status(lesson, state)
    legal = {}
    if status == tutorial.PLAYING and state["turn"] == engine.WHITE:
        legal = {pid: [list(sq) for sq in sqs] for pid, sqs in engine.legal_moves(state).items()}
    return {
        "version": len(state["log"]),
        "mode": "tutorial",
        "pieces": state["pieces"],
        "turn": state["turn"],
        "captured": state["captured"],
        "winner": state["winner"],
        "win_reason": state["win_reason"],
        "log": state["log"],
        "victories": engine.victories(state),
        "your_sides": [engine.WHITE],
        "legal_moves": legal,
        "ai": None,
        "highlights": lesson.highlights(),
        "lesson": {
            "status": status,
            "moves_left": max(0, lesson.max_moves - tutorial.moves_played(state)),
        },
    }


def index(request):
    done = _done(request)
    chapters = []
    for number, lesson in enumerate(tutorial.LESSONS, start=1):
        if not chapters or chapters[-1]["title"] != lesson.chapter:
            chapters.append({"title": lesson.chapter, "lessons": []})
        chapters[-1]["lessons"].append({"lesson": lesson, "number": number, "done": lesson.slug in done})
    next_up = next((l for l in tutorial.LESSONS if l.slug not in done), None)
    return render(request, "game/tutorial_index.html", {
        "chapters": chapters,
        "done_count": len(done),
        "total": len(tutorial.LESSONS),
        "next_up": next_up,
    })


def lesson(request, slug):
    lesson = _lesson(slug)
    _state(request, lesson)
    return render(request, "game/tutorial_lesson.html", {
        "lesson": lesson,
        "number": tutorial.LESSONS.index(lesson) + 1,
        "total": len(tutorial.LESSONS),
        "next_lesson": tutorial.next_lesson(lesson),
        "js_strings": js_strings(),
        "rows": engine.ROWS,
        "cols": engine.COLS,
    })


@require_GET
def state(request, slug):
    lesson = _lesson(slug)
    return JsonResponse(_payload(lesson, _state(request, lesson)))


@require_POST
def move(request, slug):
    lesson = _lesson(slug)
    body = _json_body(request)
    try:
        frm = [int(v) for v in body["from"]]
        to = [int(v) for v in body["to"]]
    except (KeyError, TypeError, ValueError):
        return _error(ILLEGAL_MOVE_MESSAGES["illegal_destination"], 400)
    try:
        state = tutorial.play(lesson, _state(request, lesson), frm, to)
    except engine.IllegalMove as exc:
        return _error(ILLEGAL_MOVE_MESSAGES.get(exc.code, str(exc)), 400)
    _save(request, lesson, state)
    return JsonResponse(_payload(lesson, state))


@require_POST
def reset(request, slug):
    lesson = _lesson(slug)
    state = tutorial.start(lesson)
    _save(request, lesson, state)
    return JsonResponse(_payload(lesson, state))
