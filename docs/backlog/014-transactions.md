# 014 - Expose explicit transaction control

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.2; original design 6 and 12; retained from revision `80d71d4`.

## Problem / opportunity

The protocol has no begin/commit/rollback operations. SQLite currently autocommits, while transaction state is absent from Session.

## Desired outcome

Define per-Session transaction ownership, failures, disconnect cleanup, and adapter behavior, including how explicit transactions interact with autocommit.

## Notes and references

Inspect [SQLiteAdapter](../../src/dbridge/adapters/sqlite.py) and [Session](../../src/dbridge/core/session.py). This can be designed independently of adopting asyncio.
