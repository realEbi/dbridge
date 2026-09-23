## Context

The baseline commands reproduce 21 mypy errors: 19 in parked adapters, one untyped unused logger cache, and one optional SQLite URI attribute. Ruff reports exactly the two imports named in backlog 027. The registry only imports SQLite/DuckDB. Existing CI job names are required status checks.

## Goals / Non-Goals

Make current checks clean and enforceable while fixing duplicate diagnostic output. Preserve the synchronous model in ADR-0001; this change does not supersede it. Do not port parked adapters, install their drivers, add broad type ignores, or change the coverage denominator.

## Decisions

- Remove the broken private logger cache and use the standard named logger plus its direct handler list. Configure a stderr console handler only when none exists, preserving application-provided handlers. Let the logger's level filter its console handler so repeated calls can update the level without stacking handlers.
- Exclude `src/dbridge/adapters/_parked/` from recursive mypy discovery. Keep all shipped modules and tests in scope; moving a ported adapter out of that directory includes it automatically. Ruff still checks parked source syntax and unused imports without importing drivers.
- Validate a local URI variable before assigning it to the Adapter, expressing the existing runtime invariant as a non-optional attribute.
- Add Ruff and mypy steps to the existing `test` job after proving local checks pass. Retain the Python 3.11/3.12 matrix, pull-request triggers, job identity, and coverage step. A `make check` shortcut runs the same source/test commands locally.

## Risks / Trade-offs

- Embedding applications may install handlers → retain their handlers and routing, rather than taking ownership of third-party logging configuration.
- Recursive exclusion could mask future parked ports → document that registration requires moving/including the ported module, consistent with existing coverage policy.
- Cross-worktree changes can introduce new type errors → the integrating parent reruns all checks after combining changes.

## Migration Plan

No protocol or persisted-data migration. Apply source/configuration updates together; future pull requests run the two new checks inside the existing required matrix jobs. Rollback is an ordinary source revert. Actual GitHub CI execution waits for publication, which this task does not authorize.
