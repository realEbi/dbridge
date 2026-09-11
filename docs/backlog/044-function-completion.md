# 044 - Introspect and complete SQL functions

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 6 and 10; retained from revision `80d71d4`.

## Problem / opportunity

The original interface included function signatures and SELECT-position function suggestions; the current interface exposes dialect keywords only.

## Desired outcome

Define function metadata and completion behavior, including signatures and dialect-specific insertion text.

## Notes and references

Coordinate [completion ranking](017-completion-ranking.md) and adapter introspection. Use the current [DBAdapter](../../src/dbridge/adapters/base.py) as the integration boundary.
