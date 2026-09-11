# 019 - Port and register the MySQL adapter

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.4; original design 7; retained from revision `80d71d4`.

## Problem / opportunity

The MySQL adapter is parked against an older interface.

## Desired outcome

Port execution and introspection to DBAdapter, select the driver for the chosen execution model, and verify real MySQL behavior with optional dependencies.

## Notes and references

Inspect [parked MySQL](../../src/dbridge/adapters/_parked/mysql.py). Related: [concurrent execution](012-concurrent-execution.md).

Coverage: the parked module is excluded from measurement via `omit` in [pyproject.toml](../../pyproject.toml) while it stays under `adapters/_parked/`. Porting it out of that directory re-includes it automatically, so this work must land with tests that keep the suite above the 85% floor — see [docs/development.md](../development.md).
