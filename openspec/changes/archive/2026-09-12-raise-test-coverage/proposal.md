## Why

The server suite passes but does not measure what it claims to. `[tool.coverage.run]`
puts `tests` in `source_pkgs` alongside `dbridge` and omits nothing under
`adapters/_parked/`, so the reported total (71%) mixes test files that score near
100% by construction with three parked adapters whose optional drivers are not
installed and that sit at 0%. Neither group says anything about how well the
server is covered.

Measured over the code that actually ships — `src/dbridge` with the parked
adapters omitted — the suite is at **86%** (branch mode, 559 statements, 67
missed). That clears 85% by one point with no margin, and the margin is thin for
a reason: the end-to-end tests spawn `python -m dbridge.server` as a subprocess,
so every line they exercise through the real stdio loop is counted as uncovered.
`server.py` reads 0%, `transport/stdio.py` 66%, and six `Engine` methods are
credited to nothing. Nothing enforces the number either — there is no
`fail_under` and, as [docs/development.md](../../../../docs/development.md) records,
no pull-request test workflow at all. A later change can drop coverage to 60%
and every check still passes.

## What Changes

- Redefine the measured scope: `src/dbridge` only, with `adapters/_parked/*`
  omitted. Parked adapters are excluded because their drivers are optional and
  uninstalled, and porting them is owned by separate backlog items — not because
  untested code is acceptable.
- Close the real gaps with in-process tests so the subprocess boundary stops
  hiding behavior: the stdio `serve` loop and header parsing, `server.main`
  wiring, `Engine` introspection and completion methods, executor truncation,
  adapter connection/query error paths, completion fallbacks, and the dispatcher
  error mapping.
- Target **≥93%** in the new scope so the 85% floor has real headroom rather
  than sitting one statement away from failing.
- Enforce the floor: `fail_under = 85` in the coverage config, so
  `uv run --group test pytest --cov` fails below it.
- Add the pull-request test workflow the repository lacks, running the suite
  with the gate on supported Python versions, and make its checks **required**
  on `main` so a coverage regression blocks the merge rather than merely
  reporting red. Applying the branch protection rule is a repository-settings
  action needing admin rights, planned here and done with the user's
  authorization — merging this change alone does not make the check binding.
- Normalize the test layout while touching it: consistent `test_*.py` naming
  (`tests/logging_test.py` is the lone outlier), `__init__.py` in the test
  subpackages, a shared `conftest.py` for the profile-isolation and temporary
  database fixtures currently duplicated across files, and
  `[tool.pytest.ini_options]` for `testpaths` and default options.
- Document the coverage commands, the measured scope, and the threshold in
  [docs/development.md](../../../../docs/development.md).

Not in scope: any change to server behavior or the DSP wire contract. This
change adds tests, test configuration, and CI; it does not alter what the server
does. If a test uncovers a genuine defect, the defect is recorded as a backlog
item rather than fixed here.

## Capabilities

### New Capabilities

- `test-coverage`: How the project measures test coverage of the server —
  the measured scope, the enforced minimum, and where the gate runs. This is the
  repository's first capability spec; it establishes the flat
  `openspec/specs/<capability>/spec.md` organization.

### Modified Capabilities

None. No existing capability specs exist yet (`openspec list --specs` returns
none), and no DSP requirement changes.

## Impact

**Repository**: dbridge (server) only. No client repository is affected; the
Neovim client owns no part of this.

**Protocol compatibility**: None. The DSP contract, framing, and every
request/result shape are untouched, so no client needs to change.

**Affected code and configuration**
- `pyproject.toml` — `[tool.coverage.run]` source and omit, `fail_under` under
  `[tool.coverage.report]`, new `[tool.pytest.ini_options]`.
- `tests/` — new and extended tests across `adapters/`, `core/`, `protocol/`,
  and `config/`; new `conftest.py`; `__init__.py` added to subpackages;
  `logging_test.py` renamed to `test_logging.py`.
- `.github/workflows/` — a new pull-request test workflow. The existing
  `publish-pypi.yml` is untouched.
- `docs/development.md` — coverage commands, scope, and threshold.

**Dependencies**: None added. `coverage[toml]`, `pytest`, `pytest-cov`, and
`pytest-mock` are already in the `test` group; `pytest-mock` is currently unused
and this change either uses it or records its removal.

**Related backlog and roadmap**
- No backlog item covers test coverage or CI; none is being resolved here. A new
  item is not required, since this change owns the outcome directly.
- [019](../../../../docs/backlog/019-mysql-adapter.md),
  [020](../../../../docs/backlog/020-postgres-adapter.md), and
  [021](../../../../docs/backlog/021-snowflake-adapter.md) own bringing the parked
  MySQL, PostgreSQL, and Snowflake adapters onto the supported interface. Each
  must bring its module back into the measured scope when it lands; this change
  notes that obligation on those items rather than testing parked code now.
- Roadmap: no milestone owns verification infrastructure. This supports every
  milestone by making regressions visible, and completes none of them.
- `DspError` in `protocol/errors.py` is defined but never raised or caught
  anywhere in the package — it is the only reason that module is below 100%.
  That is a finding, not a coverage problem; it becomes a new backlog item
  alongside [027](../../../../docs/backlog/027-unused-imports.md) rather than
  getting a test written for dead code.
