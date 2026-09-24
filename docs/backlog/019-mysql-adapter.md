# 019 - Port and register the MySQL adapter

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.4; original design 7; retained from revision `80d71d4`.

## Problem / opportunity

The MySQL adapter is parked against an older interface.

## Desired outcome

Port execution and introspection to the async DBAdapter interface using a native
async MySQL driver, chosen and verified during this work. Validate ADR-0003's
provisional cancellation contract with real MySQL: cancelling one operation stops
its work, leaves the Session usable, and cannot interrupt another request. Keep
the driver optional and verify real execution, introspection, and cleanup.

The native driver must implement these guarantees without requiring the Engine
to know its cancellation mechanism. That validation is an explicit milestone 3
outcome; the current SQLite/DuckDB thread-backed implementations alone do not
prove the interface for native async drivers.

## Notes and references

Inspect [parked MySQL](../../src/dbridge/adapters/_parked/mysql.py). Related: [concurrent execution](012-concurrent-execution.md).

Coverage: the parked module is excluded from measurement via `omit` in [pyproject.toml](../../pyproject.toml) while it stays under `adapters/_parked/`. Porting it out of that directory re-includes it automatically, so this work must land with tests that keep the suite above the 85% floor — see [docs/development.md](../development.md) The exclusion and the floor were decided in an [archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/design.md).
