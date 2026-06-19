# 01 — Groundwork: FastAPI teardown + three-layer skeleton

Status: ready-for-agent

## Parent

`.scratch/phase-1-restructure/PRD.md`

## What to build

Tear down the FastAPI REST surface and scaffold the three-layer package
structure (Transport / Core Engine / Adapters) so later slices have a place to
land. This is groundwork — no runtime behavior yet — but it must leave the
package importable and the test suite collectable.

- Remove the FastAPI server (routes, app entry point, connection-dedup manager,
  in-memory caching helper) and the standalone `extract_table` script (its logic
  is reabsorbed in the completion slice).
- Replace the flat `config.py` with a `config/` package directory.
- Scaffold empty `protocol/` (with `protocol/transport/`), `core/`, and
  `config/` packages under `src/dbridge/`.
- Park the optional adapters (mysql, postgres, snowflake) so they are neither
  imported at module load nor registered — the server must start without their
  optional dependencies installed.
- Drop `fastapi` and `uvicorn` from project dependencies; ensure `sqlglot` and
  `pydantic>=2` are present.
- Retain the **src layout** (`src/dbridge/`).

## Acceptance criteria

- [ ] `uv run python -c "import dbridge"` succeeds with no FastAPI/uvicorn imports
- [ ] No module imports mysql/postgres/snowflake adapters at load time
- [ ] FastAPI routes, `Connections` manager, caching helper, and `extract_table`
      script are removed from the tree
- [ ] `fastapi`/`uvicorn` removed from `pyproject.toml`; `sqlglot` present
- [ ] `uv run pytest --collect-only` runs without import errors

## Blocked by

None - can start immediately.
