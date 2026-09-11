# 049 - Execute queries with bound parameters

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 6; retained from revision `80d71d4`.

## Problem / opportunity

The original Adapter sketch accepted query parameters; current execute accepts SQL alone.

## Desired outcome

Define a transport-safe parameter representation and consistent binding/error behavior for each supported adapter.

## Notes and references

Inspect [DBAdapter.execute](../../src/dbridge/adapters/base.py). Parameter values must reach driver binding APIs rather than SQL string interpolation.
