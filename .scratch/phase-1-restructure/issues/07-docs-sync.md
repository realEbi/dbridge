# 07 — Docs sync: AGENTS.md + README

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

Bring the human/agent docs in line with the new architecture once the code
lands. The current AGENTS.md and README describe the old FastAPI REST server.

- **AGENTS.md:** rewrite the directory overview, key subsystems, and the API
  section to describe Transport (stdio JSON-RPC) / Core Engine / Adapters; replace
  the REST route table with the DSP method surface; update env vars; note
  `connections.toml` for profiles and that only sqlite/duckdb are registered.
- **README:** update run/usage to `uv run python -m dbridge.server` over stdio and
  list the supported JSON-RPC methods.

## Acceptance criteria

- [ ] AGENTS.md no longer references FastAPI routes, `Connections`, or the
      caching helper; describes the three layers and the `dbridge/*` methods
- [ ] README run instructions point at the stdio server, not uvicorn
- [ ] Env var table reflects the new settings (`dbridge_max_rows`,
      `dbridge_cache_ttl_seconds`, `dbridge_logging_level`)

## Blocked by

- `.scratch/phase-1-restructure/issues/02-tracer-connect-execute-stdio.md`
- `.scratch/phase-1-restructure/issues/03-schema-introspection-stdio.md`
- `.scratch/phase-1-restructure/issues/04-tier1-completion-stdio.md`
- `.scratch/phase-1-restructure/issues/05-duckdb-adapter-parity.md`
- `.scratch/phase-1-restructure/issues/06-profiles-erd-refresh.md`
