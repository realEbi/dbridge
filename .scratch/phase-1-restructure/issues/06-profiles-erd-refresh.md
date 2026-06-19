# 06 — Connection profiles + ERD placeholder + refreshSchema

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

Round out the Phase 1 protocol surface and configuration.

- **Connection profiles:** a loader for `connections.toml` (`[connections.<name>]`
  tables → adapter + config), resolving the config directory per-OS. Profiles are
  data only — loading a profile does not create a live adapter.
- **Settings:** env-var-based settings (prefix `dbridge_`) for `max_rows`,
  `cache_ttl_seconds`, and `logging_level`, consumed by the executor and registry.
- **ERD placeholder:** `dbridge/getERD` returns a structured
  `{"status": "not_implemented", "tables": [...]}` payload and never crashes.
- **refreshSchema:** `dbridge/refreshSchema` clears the session's schema registry
  cache.

## Acceptance criteria

- [ ] `connections.toml` with a named profile loads into a dict of
      adapter + config; a missing file yields an empty mapping (unit-tested)
- [ ] `dbridge/getERD` returns the not-implemented placeholder without error
- [ ] `dbridge/refreshSchema` clears the cache so the next introspection
      re-queries the adapter
- [ ] `max_rows` is sourced from settings (env override respected)

## Blocked by

- `.scratch/phase-1-restructure/issues/03-schema-introspection-stdio.md`
