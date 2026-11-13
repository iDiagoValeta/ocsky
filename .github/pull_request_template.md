## Issue

Closes #

## What changes

<!-- What problem it solves and how. If there are design decisions, state them here. -->

## Type

- [ ] `kind/feature`
- [ ] `kind/bug`
- [ ] `kind/improvement`
- [ ] `kind/refactoring`
- [ ] `kind/documentation`
- [ ] `kind/dependency`
- [ ] `kind/internal`
- [ ] `kind/security`

## How it was tested

<!-- Commands, tests or manual steps. If something was not tested, say so. -->

## Checklist

- [ ] The PR solves only the linked issue, with no side changes
- [ ] Title in Conventional Commits and with the issue reference
- [ ] `kind/*` labels also set on the issue
- [ ] Tests covering the change, or the reason there are none
- [ ] `python3 -m unittest discover -s tests` and `ruff check src tests tools` pass
- [ ] No new dependency and no user-visible string outside `i18n.py`
- [ ] No secrets, credentials or personal data
- [ ] Reasonable size (250 lines or less); if not, I explain why
