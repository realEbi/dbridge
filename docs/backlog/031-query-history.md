# 031 - Persist and browse query history

- Repo: dbridge, clients; ownership to decide
- Status: deferred
- Change: none
- Origin: Original design 12 and 19; retained from revision `80d71d4`.

## Problem / opportunity

The original vision included bounded Session history and history searchable across Sessions; neither is implemented in this server.

## Desired outcome

Choose history ownership, persistence, retention, search, and handling of sensitive SQL. SQLite was suggested as storage.

## Notes and references

Inspect [Session](../../src/dbridge/core/session.py); distinguish query history from [saved queries](007-saved-queries.md).
