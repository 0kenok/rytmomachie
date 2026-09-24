# Rythmomachie

Rythmomachy (*rithmomachia*), the medieval "philosophers' game" of numbers, as a
Django web app. White plays the even numbers and Black the odd ones. You capture
pieces by equality, multiplication, addition or by surrounding them.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Then open http://127.0.0.1:8000/ and start a game:

- **Against the computer**: pick your side and one of four levels (Beginner,
  Easy, Medium, Hard). The bot lives in `game/ai.py`: it is an alpha-beta search
  that looks up to three moves ahead.
- **Same screen**: both players share one browser and take turns.
- **Two browsers**: you play White and get an invite link to send to the
  person playing Black. Each page updates every 2 seconds. Anyone who opens the
  game URL without a key can watch as a spectator.

The rules are at `/rules/`. New players can start with the interactive tutorial
at `/tutorial/`: eleven short lessons, from moving a circle to winning a small
game against the computer. Progress is kept in the browser session.

## Accounts

Accounts are optional: anyone can play without one. With an account (sign up
at `/account/signup/`), games you create or join are saved to it, and the
account page at `/account/` shows your wins, losses, games in progress (with a
link to resume each one) and tutorial progress. Lessons finished before logging
in are added to the account when you log in.

To use the Django admin at `/admin/`, create an administrator first:

```bash
.venv/bin/python manage.py createsuperuser
```

## Tests

```bash
.venv/bin/python manage.py test game
```

## Layout

- `game/engine.py`: the rules engine (movement, captures, victory). It is plain
  Python, and the game state is a JSON dict stored in `Game.state`.
- `game/ai.py`: the computer opponent.
- `game/accounts.py`: sign up, log in and the account page.
- `game/tutorial.py`: the tutorial lessons (positions, goals, hints). To add a
  lesson, append a `Lesson` with a `solution`; the tests check it can be solved.
- `game/views.py`: HTML pages plus a small JSON API (`state/`, `move/`, `resign/`).
- `game/static/game/board.js`: draws the board and handles clicks and polling.

## Languages

The app is available in English and French. On their first visit, people choose
a language, and they can switch at any time with the EN / FR buttons in the
header. Translations are in `locale/fr/LC_MESSAGES/django.po`, and the rules page
has one template per language (`rules_en.html`, `rules_fr.html`). After editing
the `.po` file, recompile it:

```bash
cd game && ../.venv/bin/python ../manage.py makemessages -l fr   # pick up new strings
cd .. && .venv/bin/python manage.py compilemessages --ignore=.venv
```

## Configuration

Set these environment variables when you deploy:

| Variable | Default |
| --- | --- |
| `DJANGO_SECRET_KEY` | insecure development key |
| `DJANGO_DEBUG` | `1` (set to `0` in production) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |
