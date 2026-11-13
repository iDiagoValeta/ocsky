# Security policy

## Supported versions

Only the latest release is maintained. Update to it before reporting.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Report it privately through GitHub's private vulnerability reporting: the repository's Security tab, then Report a vulnerability. The report stays private until a fix ships.

Include the ocsky version (`ocsky --version`), your OS, and the steps to reproduce.

## Scope

ocsky is meant to be a read-only viewer that never leaves your machine. These are vulnerabilities:

- Anything that makes ocsky write to opencode's data.
- Anything that makes it read tables other than `session_v2` and `session_message`.
- Anything that sends data off the machine.
- Anything that executes content read from the database, for example through terminal escape sequences in a session title or message that reach your terminal unfiltered.

Bugs in opencode itself belong to the opencode project.

## Response

This is a single-maintainer project. I aim to acknowledge a report within a week and to tell you what I plan to do about it soon after. I cannot promise a fixed fix time.
