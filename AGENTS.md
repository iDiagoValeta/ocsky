# AGENTS.md

ocsky is a live, animated terminal view of opencode agents. It reads opencode's local SQLite database read-only and shows which sessions are working, waiting or finished, grouped by directory, with subagents under their parent, a 24 hour clock view and the trace of one session. Python 3.9+, standard library only. User docs are in `README.md` and `docs/usage.md` (keys, options, platforms), the human workflow in `CONTRIBUTING.md`.

## Architecture

Hexagonal. The rules are enforced by `tests/test_architecture.py` (it parses imports with `ast`); do not special-case it.

```
src/ocsky/
  main.py          composition root: the only module that builds adapters
  core/            model, activity, states, tree, observatory; pure, no IO
    ports/         ForReadingSessions, ForListingProcesses, ForTellingTime,
                   ForOpeningSessions, ForCopyingText, ForKeepingPreferences
  adapters/
    driven/        sqlite_sessions, processes, system_clock, opencode_launcher,
                   osc52_clipboard, json_preferences, demo_database
    driving/       cli.py and tui/ (app, views, canvas, theme, i18n, fmt, terminal)
tests/             helpers.py (import first), doubles.py (in-memory driven ports)
tools/render_demo.py   regenerates docs/demo.gif and the stills in docs/
```

- `core/` imports only `ocsky.core`, `__future__`, `dataclasses`, `typing`, `json`, `hashlib`, `math`, `unicodedata`. No `os`, `time`, `sqlite3`, `subprocess`, no `open()`.
- `driven` and `driving` never import each other. Inside `driving`, `tui` may import `tui`.
- Only `main.py` imports both families and instantiates adapters.
- A backdrop of the sky is a function in `tui/views/backdrops.py` that paints only free cells through `Pane`, plus at most a faint `Pane.glow` under them, registered in `BACKDROPS`. Keep it dim: the list is the subject. Check it on a light palette too.
- A palette lives in `tui/palettes.py`, written in Catppuccin's colour names from its project's published colours (cite the source there), with a `pair` on the other side of the day. Never invent a colour; leave a missing neutral out and `Theme` blends it.
- A new need of the core is a new port (a `Protocol`, named for its purpose) plus an in-memory double in `tests/doubles.py`.

## Constraints

- Standard library only, at runtime and in tests (`unittest`). Do not add a dependency.
- Python 3.9: every file starts with `from __future__ import annotations`; annotations use `typing.List`, `Dict`, `Optional`, `Tuple`. Line length 110.
- Read-only on opencode's data. The connection is `mode=ro` and only `session_v2` and `session_message` are ever queried. Never read another table, never write.
- No network access. The only actions are local: open a session in opencode, copy an id or a directory through OSC 52.
- No user-visible string outside `src/ocsky/adapters/driving/tui/i18n.py`. Every key exists in every language with the same placeholders (a test checks it).
- Everything in the repo is English: code, comments, docs, tests. No em dashes, en dashes or middle dots as punctuation in prose.
- Docs describe the current code, not its history. Update `docs/usage.md` when a key, an option or a platform behaviour changes; keep `README.md` short.
- Keep changes surgical: touch what the task needs, match the existing style.

## Commands

```bash
python3 -m unittest discover -s tests
ruff check src tests tools
PYTHONPATH=src python3 -m ocsky --demo --once 120x32   # one frame, no terminal needed
PYTHONPATH=src python3 -m ocsky --demo                 # interactive
python3 tools/render_demo.py                           # needs Pillow
```

A change is done when the tests and the lint pass and the effect was observed, for a visible change with `--demo --once` at a realistic size.

## Git flow

Trunk-based: `main` is the only long-lived branch. Work on a short-lived branch `<prefix>/GH-<issue>-<context>` (prefixes in `CONTRIBUTING.md`), open a PR that links its issue with `Closes #N`, squash-merge once CI is green, delete the branch. Commits and PR titles follow Conventional Commits and are in English; the body explains why. Never push to `main` directly.

## Releases

release-please (`.github/workflows/release-please.yml`) opens a release PR from the Conventional Commits on `main`, updating `CHANGELOG.md` and the version in `src/ocsky/__init__.py` (the line marked `x-release-please-version`). Do not edit either by hand. `fix` bumps the patch, `feat` the minor, a breaking change the minor while the version is below 1.0.
