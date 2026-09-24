# 043 - Invalidate schema metadata after DDL

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 9; retained from revision `80d71d4`.

## Problem / opportunity

Executing DDL does not invalidate the current schema cache. Clients must refresh explicitly or wait for TTL expiry.

With explicit Scope Paths, that cache also covers database and schema listings.
After `ATTACH`, `CREATE SCHEMA`, or related changes, a client may keep a stale
container tree and the connect-time hierarchy/default-path copy until it calls
`refreshSchema`. TTL expiry makes later listing requests fresh, but does not
push a new hierarchy declaration to the client. Refresh invalidates all metadata
entries and returns the authoritative current declaration and default path.

Existing explicit paths continue to address their named containers; staleness does
not cause the server to substitute an active scope. Removed or renamed
containers can still make held paths invalid and must be reconciled by the client.

## Desired outcome

Decide how successful schema-changing statements trigger invalidation without misclassifying SQL or clearing unrelated scopes.

## Notes and references

Inspect [executor](../../src/dbridge/core/executor.py) and [SchemaRegistry](../../src/dbridge/core/schema_registry.py). Related: [cache coverage](004-introspection-cache-coverage.md).
