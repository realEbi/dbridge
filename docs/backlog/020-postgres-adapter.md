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
