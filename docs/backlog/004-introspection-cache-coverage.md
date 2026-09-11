# 004 - Cache database and schema listings consistently

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 1.4; retained from revision `80d71d4`.

## Problem / opportunity

The Engine caches table listings and table schemas, but calls adapters directly for database and schema listings. refreshSchema therefore only clears part of the metadata view.

## Desired outcome

Decide which introspection operations share the Session cache, cache their scope arguments, and make refresh behavior explicit.

## Notes and references

Inspect [Engine](../../src/dbridge/core/engine.py) and [SchemaRegistry](../../src/dbridge/core/schema_registry.py). Related: [remote cache policy](024-remote-cache-policy.md).
