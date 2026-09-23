# 008 - Expose the Session's SQL dialect to clients

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 3.1; retained from revision `80d71d4`.

## Problem / opportunity

Adapters provide dialect_name(), but clients cannot obtain it through the protocol.

## Desired outcome

Expose the dialect, potentially alongside session_id in the connect response, while preserving existing callers.

## Notes and references

Inspect [Engine.connect](../../src/dbridge/core/engine.py) and [DBAdapter](../../src/dbridge/adapters/base.py). Related: [qualified identifiers](002-qualified-identifiers.md).

Identifier generation in [002](002-qualified-identifiers.md) now uses server-owned
SQL identifiers without exposing a dialect field. This item remains deferred for
client behaviors that actually need dialect information.
