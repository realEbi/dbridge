# 020 - Port and register the PostgreSQL adapter

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.4; original design 7; retained from revision `80d71d4`.

## Problem / opportunity

The PostgreSQL adapter is parked against an older interface.

## Desired outcome

Port execution and introspection to DBAdapter, select a driver based on the execution design, and verify real PostgreSQL behavior with optional dependencies.

## Notes and references

Inspect [parked PostgreSQL](../../src/dbridge/adapters/_parked/postgres.py). The earlier asyncpg suggestion is a candidate, not a current dependency decision.

Coverage: the parked module is excluded from measurement via `omit` in [pyproject.toml](../../pyproject.toml) while it stays under `adapters/_parked/`. Porting it out of that directory re-includes it automatically, so this work must land with tests that keep the suite above the 85% floor — see [docs/development.md](../development.md) The exclusion and the floor were decided in an [archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/design.md).
