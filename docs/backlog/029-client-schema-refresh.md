# 029 - Refresh schema without reconnecting the Profile

- Repo: dbridge.nvim
- Status: done
- Change: [client preserve-and-display-active-session](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-preserve-and-display-active-session/)
- Origin: Legacy backlog 6; retained from revision `80d71d4`.

## Problem / opportunity

The original record described disconnect/reconnect, but code inspection showed that the explorer's R action cleared the local binding and opened another Session without disconnecting the old one. Refresh therefore lost access to Session-local data and leaked the old binding.

## Desired outcome

Use refreshSchema and new introspection calls where appropriate, preserving the live Session and clearly handling errors.

## Notes and references

Recheck the client explorer and coordinate [cache coverage](004-introspection-cache-coverage.md).

## Resolution

Refresh now invalidates metadata and rebuilds the tree against the same live Session. Metadata is replaced only after successful listings, and stale/deleted-node replies are ignored. SQLite/DuckDB client tests preserve in-memory data and TEMP tables and verify error handling.
