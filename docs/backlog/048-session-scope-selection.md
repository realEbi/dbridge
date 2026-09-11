# 048 - Select a Session's active database and schema

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 12 and multi-database use cases; retained from revision `80d71d4`.

## Problem / opportunity

Session has active_database and active_schema fields, but the current protocol has no operations to set them.

## Desired outcome

Define selection, adapter search-path behavior, introspection defaults, and client display without losing fully qualified identity.

## Notes and references

Coordinate [database hierarchy](003-database-hierarchy.md) and [qualified identifiers](002-qualified-identifiers.md).
