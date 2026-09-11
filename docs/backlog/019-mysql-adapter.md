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
