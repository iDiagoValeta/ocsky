# Contributing

The rules for coding agents are in [AGENTS.md](AGENTS.md); they are the same rules, written for a tool. This file covers how to work on ocsky as a person.

## Setup

```bash
git clone https://github.com/iDiagoValeta/ocsky
cd ocsky
git config commit.template .gitmessage
PYTHONPATH=src python3 -m ocsky --demo     # run from the checkout
```

There is nothing to install: ocsky uses only the standard library. Development tools are `ruff` (lint) and Pillow (only for the demo images).

## Checks

```bash
python3 -m unittest discover -s tests
ruff check src tests tools
```

CI runs the tests on Python 3.9 and 3.12 (with deprecation warnings as errors on 3.12), the lint, and an install smoke test on Linux, macOS and Windows. A change that alters behaviour needs a test that fails without it.

## Workflow

Trunk-based. `main` is the only long-lived branch and is protected.

1. Open an issue first. A bug report needs the output of `ocsky --version`, your OS and terminal.
2. Branch from `main`, named `<prefix>/GH-<issue>-<context>`, for example `bugfix/GH-12-clock-wraps-at-midnight`. The context starts with a letter and uses only letters, digits and hyphens.
3. Allowed prefixes: `feature`, `bugfix`, `hotfix`, `improvement`, `refactoring`, `documentation`, `dependency`, `deprecation`, `removal`, `revert`, `security`, `internal`, `automated`. `internal`, `revert` and `automated` may omit the issue.
4. Keep the branch short-lived and the change small, 250 changed lines or fewer when you can. One concern per PR.
5. Open the PR with the title `<type>(<scope>): <summary> (GH-<n>)` and `Closes #<n>` in the description. The PR template lists the rest.
6. Merge with squash once CI is green. Delete the branch on merge. Whoever opened the PR merges it.

Everything in git is in English: code, comments, commit messages, issues and PRs.

## Commits

[Conventional Commits](https://www.conventionalcommits.org): `<type>(<scope>): <summary>`, imperative, lowercase, no trailing period. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. The body explains why, not what the diff shows. Mark a breaking change with `!` or a `BREAKING CHANGE:` footer.

Releases are automatic: release-please reads the squashed commits on `main`, keeps a release PR with the changelog and the version, and merging that PR tags the release. Do not edit `CHANGELOG.md` by hand.

## Architecture rules

ocsky is hexagonal: the core knows nothing about SQLite, the terminal or the operating system.

```
src/ocsky/
  main.py                 composition root: the only module that builds adapters
  core/                   model, states, tree, observatory (pure, no IO)
    ports/                one Protocol per thing the core needs from outside
  adapters/
    driven/               SQLite, processes, clock, launcher, clipboard, preferences
    driving/              command line and the terminal interface (app, views, i18n)
```

`tests/test_architecture.py` fails the build when one of these is broken:

- `core/` imports only `ocsky.core` and `__future__`, `dataclasses`, `typing`, `json`, `hashlib`, `math`, `unicodedata`. No `os`, `time`, `sqlite3`, `subprocess`, no `open()`.
- `core/ports/` holds one `Protocol` per thing the core needs from outside. Port names say what they are for, not which technology serves them.
- `adapters/driven/` and `adapters/driving/` never import each other.
- Only `main.py` imports both adapter families and builds adapters.
- Every driven port has an in-memory double in `tests/doubles.py`, so core and interface tests need no database, process or terminal.

## Constraints

- Standard library only, at runtime and in tests (`unittest`). No new dependency.
- Python 3.9 compatible. Every file starts with `from __future__ import annotations`; annotations use `typing.List`, `Dict`, `Optional`, `Tuple`.
- Read-only on opencode's data, and only the tables `session_v2` and `session_message`.
- No user-visible string outside `src/ocsky/adapters/driving/tui/i18n.py`.
- No network access.

## Adding a language

1. In `src/ocsky/adapters/driving/tui/i18n.py`, add a block to `STRINGS` with exactly the keys of `"en"`, and add the language code to `LANGS`.
2. In `src/ocsky/adapters/driving/tui/fmt.py`, add the number, cost and duration formats for the code.
3. Run the tests: they check that every language has the same keys and the same placeholders.

## Regenerating the demo images

```bash
pip install Pillow
python3 tools/render_demo.py
```

This rewrites `docs/demo.gif` and the four stills listed in `STILLS` from the demo database with a fixed clock, so the output is the same on every run. Commit the images only when the interface changed.
