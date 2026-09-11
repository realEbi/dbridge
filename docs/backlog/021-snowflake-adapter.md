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
