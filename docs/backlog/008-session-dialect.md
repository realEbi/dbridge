# 008 - Expose the Session's SQL dialect to clients

- Repo: dbridge
- Status: done
- Change: [adopt-explicit-scope-paths](../../openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/proposal.md)
- Origin: Legacy backlog 3.1; retained from revision `80d71d4`.

## Problem / opportunity

Adapters already provided `dialect_name()`, but the previous protocol did not
report it to clients.

## Desired outcome

Expose the Session's SQL dialect alongside its identifier. The selected change
also deliberately breaks metadata addressing compatibility; old client support
is not part of this migration.

## Resolution

[Engine.connect](../../src/dbridge/core/engine.py) now returns the Adapter's
`dialect` (`sqlite` or `duckdb`) alongside `session_id`, `levels`, and
`default_path`. The dialect remains constant for that live Session. Clients learn
hierarchy from the level declaration, independently of SQL syntax.

Verified both inline and Profile-backed Sessions, refresh after attachment, and
client consumption of the reported dialect. Server-owned identifier generation remains documented in
[002](002-qualified-identifiers.md).
