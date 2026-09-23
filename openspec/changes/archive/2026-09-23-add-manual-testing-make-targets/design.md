## Context

See proposal.md for motivation. The existing sample generator creates ignored
SQLite and DuckDB files from `examples/sample.sql`. The user confirmed these
databases should persist for interactive testing. The guide also embeds a Python
RPC walkthrough that repeats database setup and automated checking logic; the user
requested its removal to keep the guide focused on the existing tooling.

## Goals / Non-Goals

**Goals:** Expose existing preparation and test commands through discoverable
Make targets and explain how to use the retained samples.

**Non-Goals:** Change server behavior, create Profiles outside RPCs, modify
clients, or add another Python harness.

## Decisions

- Use a help-first, phony-target Makefile. Explicit `manual-prepare` invokes
  `uv run python scripts/make_sample_db.py`; uv already synchronizes dependencies,
  so a separate `uv sync` is unnecessary.
- Keep `test` and `test-cov` separate so focused tests need not trigger coverage.
  Allow `UV` and `PYTEST_ARGS` overrides for local tools and pytest selection.
- Replace the embedded Python walkthrough with sample paths, inline connect
  parameters, a short interactive checklist, and references to the existing
  automated suite. Setup stays in the sample generator; no second script is
  needed. Creating sample Profiles remains a client/RPC action.
- ADR-0001 remains applicable; no runtime boundaries or execution model change.
  Only dbridge owns this work, with no cross-repository migration.

## Risks / Trade-offs

- Preparation replaces existing generated samples → state this in help and the
  guide, require an explicit target, and verify in a disposable project copy.
- Make is an additional local tool → retain direct uv commands in documentation.

## Migration Plan

Add optional command wrappers and update their documentation together. Removing
the Makefile restores the prior workflow without data/configuration migration.
