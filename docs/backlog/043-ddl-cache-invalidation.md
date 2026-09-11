# 043 - Invalidate schema metadata after DDL

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 9; retained from revision `80d71d4`.

## Problem / opportunity

Executing DDL does not invalidate the current schema cache. Clients must refresh explicitly or wait for TTL expiry.

## Desired outcome

Decide how successful schema-changing statements trigger invalidation without misclassifying SQL or clearing unrelated scopes.

## Notes and references

Inspect [executor](../../src/dbridge/core/executor.py) and [SchemaRegistry](../../src/dbridge/core/schema_registry.py). Related: [cache coverage](004-introspection-cache-coverage.md).
