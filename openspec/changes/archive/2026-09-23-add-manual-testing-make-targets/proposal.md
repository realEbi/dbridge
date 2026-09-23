## Why

Preparing reusable databases for interactive manual testing currently requires
knowing about a separate sample generator. A small Makefile can make preparation
and automated testing discoverable from the repository root.

## What Changes

- Add a help-first Makefile with `manual-prepare`, `test`, and `test-cov` targets.
- Reuse the existing sample generator to retain SQLite and DuckDB databases for
  interactive testing; document that preparation resets these generated files.
- Update the manual and development guides with commands, sample connection
  parameters, and a short interactive checklist. Remove the embedded Python
  walkthrough so fixture setup lives in the existing generator and automated
  protocol checks use the test suite; refresh descriptions of the guide's contents.

## Capabilities

### New Capabilities

None. This is a developer tooling and documentation change with `skip_specs: true`.

### Modified Capabilities

None. The accepted test-coverage contract and server behavior remain unchanged.

## Impact

Only the dbridge repository is affected: a root Makefile and developer-facing
documentation/examples. Make becomes an optional convenience alongside existing
uv commands; no Python dependencies or DSP compatibility changes are introduced.
Profile management remains through public RPCs. No existing backlog item applies;
this supports verification for roadmap milestone 1 (Reliable daily use) without
completing any of its deferred outcomes.
