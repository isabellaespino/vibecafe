# Workflow

Work in this loop. Never skip a step.

- **study**: write a timestamped markdown doc in doc/study/ analyzing a request. Feasibility and tradeoffs. No code.
- **plan**: write a timestamped markdown checklist in doc/plan/ of concrete steps to achieve an outcome. Usually derived from a study.
- **execute plan**: carry out an existing plan doc. Do this on a Git branch off main.
- **rendezvous**: merge the branch back to main and confirm the codebase runs.
- **sync docs**: update doc/wiki/, the living manual of the codebase, to match reality.

# Rules

- Scope every change to one conventional commit (feat: fix: chore: build:).
- Stack: Django, SQLite, Django built-in auth and admin, server-rendered templates. No frontend framework.
- Do not add dependencies without saying why in a study first.
- Never reset or reseed `db.sqlite3` (no `rm db.sqlite3`, no `Model.objects.all().delete()` against it, no blind `migrate` used as a reset). It's a local, gitignored file — the only copy of whatever data is in it, including anything added through the admin. To verify behavior, use Django's test framework (`manage.py test`, which runs against its own throwaway test database) or a separate throwaway SQLite file, never the working `db.sqlite3`.
