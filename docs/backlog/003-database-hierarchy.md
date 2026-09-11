# 003 - Represent each database's browsing hierarchy accurately

- Repo: dbridge, dbridge.nvim
- Status: deferred
- Change: none
- Origin: Legacy backlog 1.3; retained from revision `80d71d4`.

## Problem / opportunity

SQLite returns main for both database and schema, producing a redundant main/main level in the client tree.

## Desired outcome

Define a browsing contract that accommodates different catalog/schema hierarchies and lets clients render them consistently.

## Notes and references

Inspect [SQLite introspection](../../src/dbridge/adapters/sqlite.py) and the client explorer before choosing the protocol shape.
