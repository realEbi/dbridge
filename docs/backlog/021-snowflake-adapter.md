# 021 - Port and register the Snowflake adapter

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.4; original design 7; retained from revision `80d71d4`.

## Problem / opportunity

The Snowflake adapter is parked against an older interface.

## Desired outcome

Port execution and scoped introspection, define supported authentication methods, and verify integration without requiring Snowflake dependencies for other adapters.

## Notes and references

Inspect [parked Snowflake](../../src/dbridge/adapters/_parked/snowflake.py). Coordinate [remote cache policy](024-remote-cache-policy.md) and [secret-backed Profiles](023-secret-managers.md).

Coverage: the parked module is excluded from measurement via `omit` in [pyproject.toml](../../pyproject.toml) while it stays under `adapters/_parked/`. Porting it out of that directory re-includes it automatically, so this work must land with tests that keep the suite above the 85% floor — see [docs/development.md](../development.md) The exclusion and the floor were decided in an [archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/design.md).
