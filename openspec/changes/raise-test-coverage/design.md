## Context

See [proposal.md](proposal.md) — Why. The constraints that shape the approach:

- **Measured baseline (verified, not estimated).** With the scope this change
  adopts — `source = ["src/dbridge"]`, `branch = true`,
  `omit = ["src/dbridge/adapters/_parked/*"]` — the suite today reports **86%**:
  559 statements, 67 missed, 104 branches, 20 partial. Per-module gaps:
  `server.py` 0%, `transport/stdio.py` 66%, `core/executor.py` 70%,
  `protocol/errors.py` 79%, `transport/base.py` 83%, `core/engine.py` 84%,
  `adapters/sqlite.py` 85%, `core/completion.py` 87%, `adapters/base.py` 87%,
  `adapters/duckdb.py` 88%, `config/profiles.py` 90%, `protocol/handlers.py` 90%,
  `logging/__init__.py` 90%, `core/schema_registry.py` 96%.
- **The subprocess boundary is the single largest distortion.**
  `tests/test_e2e_stdio.py` spawns `python -m dbridge.server` and drives it over
  pipes. It genuinely exercises `main()`, `StdioTransport.serve`, six `Engine`
  methods, executor truncation, and completion — and every one of those lines is
  counted as missed, because the coverage process and the server process are
  different processes.
- **`adapters/base.py` and `transport/base.py` lose points to syntax, not
  behavior.** Their misses are all `->exit` partial branches on `...` bodies of
  `@abstractmethod` declarations. No test can cover an ellipsis body; these are
  measurement artifacts.
- **No conftest, no pytest configuration.** `tests/` subdirectories have no
  `__init__.py`, so pytest imports `tests/core/test_session.py` as top-level
  module `test_session` under rootdir insertion. It works today only because no
  two test basenames collide. The profile-isolation fixture is duplicated
  verbatim between `tests/protocol/test_handlers.py` and
  `tests/config/test_profiles.py`.
- **ADR-0001** (synchronous core, stdio-only transport) stands and is not
  touched. This change supersedes no decision. It does depend on the core being
  synchronous: driving `StdioTransport.serve` in process with fake streams is
  only simple because `serve` is a plain blocking loop. If the execution model
  later changes under a superseding ADR, that change owns updating these tests.

## Goals / Non-Goals

**Goals:**

- A reported coverage number that describes `src/dbridge` and only `src/dbridge`.
- Enough real headroom above the 85% floor that an ordinary change does not trip
  the gate — target ≥93%.
- Tests that fail for a behavioral reason. A test written only to execute a line
  is a liability; if the only way to cover something is to assert nothing
  meaningful, the right move is to exclude it or delete the code.
- A gate that runs without a developer choosing to run it.

**Non-Goals:**

- Any change to server behavior, the DSP contract, or framing semantics.
- Testing the parked adapters. Their coverage arrives with
  [019](../../../docs/backlog/019-mysql-adapter.md) /
  [020](../../../docs/backlog/020-postgres-adapter.md) /
  [021](../../../docs/backlog/021-snowflake-adapter.md).
- Chasing 100%. The floor is 85% and the target is ≥93%; the remainder is
  defensive branches whose tests would assert nothing.
- Mutation testing, property-based testing, or a new test framework.

## Decisions

### 1. Cover subprocess-exercised behavior with in-process tests, not subprocess coverage measurement

**Chosen:** Add in-process tests that drive the same code paths directly —
`StdioTransport.serve` against `io.BytesIO`-backed fake stdin/stdout, `main()`
with `sys.stdin`/`sys.stdout` monkeypatched, and `Engine` methods called
directly against an in-memory SQLite Session. Keep `tests/test_e2e_stdio.py`
exactly as it is.

**Alternative rejected:** measuring the subprocess, via `parallel = true`,
`COVERAGE_PROCESS_START`, a `sitecustomize.py` calling
`coverage.process_startup()`, and a `coverage combine` step. This is the
approach that would credit the existing e2e tests without writing anything new,
and it is genuinely tempting because `parallel = true` is already set in
`pyproject.toml`.

Rejected because it buys a number rather than a test. It requires environment
plumbing that behaves differently under pytest-cov than under bare `coverage
run`, breaks confusingly when `combine` is skipped, and needs a `sitecustomize`
that affects every Python process started from the repository. Worse, it would
let the suite hit the target without a single new assertion — the coverage would
go up and the verification would not. In-process tests are faster, assert on
specific behavior, and pin down cases a subprocess test cannot reach at all: a
`Content-Length`-less header block, an unparseable request mid-stream, EOF in
the middle of a frame.

The spec records this: "Behavior verified through a subprocess is measured in
process," with the e2e tests explicitly retained.

### 2. `source` over `source_pkgs`, and drop `tests` from the measured set

**Chosen:**

```toml
[tool.coverage.run]
source = ["src/dbridge"]
branch = true
omit = ["src/dbridge/__about__.py", "src/dbridge/adapters/_parked/*"]
```

`source_pkgs = ["dbridge", "tests"]` is replaced. Removing `tests` is the point;
switching `source_pkgs` → `source` with the filesystem path also resolves the
`module-not-measured` warning the current configuration emits ("Module dbridge
was previously imported, but not measured"), which occurs because the installed
package is imported before the measurement of the named package begins.

`parallel = true` is removed along with it — it exists to support combining data
files from multiple processes, which decision 1 declines to do. Leaving it set
while never running `coverage combine` is how partial data files accumulate
unnoticed. `[tool.coverage.paths]` keeps its `dbridge` entry for report path
normalization and drops the now-meaningless `tests` entry.

**Alternative rejected:** keeping `tests` measured and raising the combined
number. It clears 85% trivially and measures nothing worth measuring.

### 3. Exclude abstract-method bodies from the report rather than pretending to test them

**Chosen:** extend `exclude_lines` with a pattern for bare `...` bodies:

```toml
exclude_lines = [
  "no cov",
  "if __name__ == .__main__.:",
  "if TYPE_CHECKING:",
  "^\\s*\\.\\.\\.$",
  "@(abc\\.)?abstractmethod",
]
```

`adapters/base.py` (87%) and `transport/base.py` (83%) are fully covered in
substance; their misses are `->exit` partials on ten `@abstractmethod` ellipsis
bodies. Excluding them is honest — they contain no behavior. Verified effect of
adding these two patterns to the current suite: both modules report 100%, the
denominator drops from 559 statements / 104 branches to 539 / 84, partial
branches fall from 20 to 10, and the total moves 86% → 87%. Without the
exclusion those phantom misses push someone toward writing a test that
instantiates an ABC to satisfy a number.

**Alternative rejected:** a concrete `DBAdapter` test double that calls `super()`
on each abstract method. It covers the lines and asserts nothing about dbridge.

### 4. `fail_under` in the coverage config, not in a CI-only flag

**Chosen:** `fail_under = 85` under `[tool.coverage.report]`, so the same floor
applies to `uv run --group test pytest --cov` locally and in CI. A developer
discovers a coverage regression before pushing, and CI needs no special
invocation to enforce it.

Set to 85, the number the user specified, while the suite is driven to ≥93%. The
gap is deliberate: a floor set at the achieved value fails on the next change
that adds a defensive branch, which trains people to lower the gate.

**Alternative rejected:** `--cov-fail-under=85` only in the workflow. Splits the
rule from the configuration and lets local runs pass on code CI will reject.

### 5. Coverage off by default for plain `pytest`, on via an explicit flag

**Chosen:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

Coverage is not in `addopts`. `uv run --group test pytest` stays fast for the
tight edit loop that `docs/development.md` recommends ("Use focused tests while
changing behavior"); `uv run --group test pytest --cov` is the gated run.

**Alternative rejected:** `addopts = "--cov --cov-fail-under=85"`. It makes every
focused single-test run fail the gate, since one test never covers 85% — the
fastest route to people passing `--no-cov` reflexively.

### 6. Test layout: packages, one conftest, consistent naming

**Chosen:** add `__init__.py` to `tests/adapters/`, `tests/config/`,
`tests/core/`, and `tests/protocol/`; move the duplicated `isolated_profiles`
fixture and a shared in-memory-Session fixture into `tests/conftest.py`; rename
`tests/logging_test.py` → `tests/test_logging.py`.

Test packages make the import names unambiguous, which matters as soon as this
change adds more files per directory (a second `test_engine.py` under two
directories would currently collide). Both `test_*.py` and `*_test.py` collect
under pytest defaults, so the rename is for consistency, not function — it is
cheap while the file is being touched anyway, and it is the only outlier.

### 7. New tests target behavior, and defects found become backlog items

**Chosen:** each new test asserts an observable outcome — an error type, an
error code, a returned shape, a truncation warning — not merely that a line ran.
Where a gap is dead code rather than untested behavior, it is recorded, not
covered. `DspError` in `protocol/errors.py` is the clear case: defined, never
raised, never caught, and the sole reason that module sits at 79%. It gets a
backlog item, not a `test_dsperror_sets_code`.

This follows AGENTS.md: "New unrelated findings go into individual backlog
files, with evidence and the owning repository." If a new test surfaces a real
behavioral defect, the same rule applies — record it, do not expand this change
into a bug-fix change.

### 8. CI matrix on 3.11 and 3.12

**Chosen:** a `test.yml` workflow on **every** `pull_request` (no `branches:`
filter) and on pushes to the integration branches `main` and `dbridge-2.0`,
using `astral-sh/setup-uv` (matching the existing `publish-pypi.yml`), running
`uv run --group test pytest --cov` across a
`python-version: ["3.11", "3.12"]` matrix.

**Corrected during implementation.** This decision originally filtered
`pull_request` to `branches: [main]`, on the assumption that `main` is the
integration branch. It is not: `main` sits 24 commits and three months behind
`dbridge-2.0`, has no `openspec/` or `docs/backlog/`, and receives nothing.
Active work integrates into `dbridge-2.0`. A base-branch filter would therefore
have shipped a gate that never fires — the worst failure mode available, since it
looks configured. Dropping the filter entirely is also the better rule on its own
terms: there is no base branch where a coverage regression is acceptable.

`pyproject.toml` declares `requires-python = ">=3.11"` and classifiers for 3.11
and 3.12; testing only the local 3.12 would leave the declared 3.11 support
unverified. `tomllib` (3.11+) is already relied on in `config/profiles.py`.

**Alternative rejected:** adding the coverage job to `publish-pypi.yml`. That
workflow is tag-triggered and release-shaped; a test gate belongs on pull
requests, and the spec requires the release workflow to stay unchanged.

### 9. The check blocks the merge — required status check, not advisory

**Chosen:** register the workflow's jobs as **required status checks** via a
branch protection rule on the branch that actually integrates work, so a pull
request whose coverage falls below the floor cannot be merged. The user directed
that coverage be guarded at the CI level; a red check a reviewer can merge past
is a notification, not a guard.

**Which branch to protect is the user's call** and is not settled by this design.
`main` is the default branch but stale and idle; `dbridge-2.0` is where work
lands. Protecting only `main` would satisfy the letter of "protect the default
branch" while guarding nothing that currently happens. Protecting `dbridge-2.0`
guards real work but leaves the default branch open. Both is defensible.

Because the matrix produces one check per Python version, both
`test (3.11)` and `test (3.12)` are required — requiring only the job name
`test` matches nothing, since the matrix never produces a check by that bare
name. The rule also enables *Require branches to be up to date before merging*,
without which a pull request branched before a coverage-dropping merge can go
green against stale base state and still land the regression.

The workflow additionally runs on pushes to `main`, so a change that reaches the
default branch outside the pull-request path is still measured.

**Two things this decision does not do.** First, branch protection lives in
repository settings, not in a file in the tree, so it is not delivered by
merging this change — it is a `gh api` call or a settings-page edit against
`realebi/dbridge` requiring admin rights on the repository. It is planned here
and listed as a task, but executing it needs the user's authorization and their
permissions; nothing in this change performs it automatically.

Second, the rule is applied **after** the workflow has been observed green on a
real pull request (task ordering in section 5). Requiring a check that has never
run, or whose name is guessed rather than observed, blocks every pull request on
a check that can never report — GitHub holds the merge waiting for a status that
does not exist. The exact check names are read from the first successful run.

**Alternative rejected:** leaving it advisory and relying on reviewer
discipline. That is the status quo the change exists to fix — `fail_under`
already makes the failure visible; only branch protection makes it binding.

**Alternative rejected:** enforcing via a coverage service (Codecov and similar)
with a status-check integration. It offers per-pull-request deltas and trend
history that a local `fail_under` cannot, but it adds a third-party dependency,
a token, and an upload step to a repository whose only current workflow is
publishing, and it moves the authoritative threshold out of `pyproject.toml`
into a service configuration. The floor is enforceable locally and in CI from
one number in one file; keep it there.

## Risks / Trade-offs

- **In-process tests duplicate what the e2e tests already prove** → Accepted,
  and the duplication is the smaller cost. The two layers answer different
  questions: e2e proves the real process wiring works for a client, in-process
  proves each branch behaves. The spec requires both.
- **Monkeypatching `sys.stdin`/`sys.stdout` to test `main()` risks polluting the
  test session or, worse, writing protocol frames to the real stdout** →
  Use pytest's `monkeypatch` so restoration is automatic, back both streams with
  `io.BytesIO` exposed through a small object with a `.buffer` attribute (what
  `stdio.py` reads), and feed a stream that reaches EOF so `serve` returns
  instead of blocking. Assert on the captured bytes.
- **`fail_under` makes a previously green local command red** → Intended, but it
  will surprise someone. It is documented in `docs/development.md` as part of
  this change, and 93% vs an 85% floor means it only triggers on a real drop.
- **Excluding abstract bodies could later hide a real uncovered line** → The
  patterns are narrow: a line that is exactly `...` and the `@abstractmethod`
  decorator line. Neither can hide executable logic.
- **The new gate blocks pull requests in a repository that has never had a
  required check** → Intended, per decision 9, and the disruption is real: every
  future pull request now depends on a green suite. Mitigated by ordering —
  the rule is applied only after the workflow is observed green on a real pull
  request, and the required check names are read from that run rather than
  guessed, so no pull request is ever held waiting on a status that cannot
  report. Applying the rule needs repository admin rights and the user's
  authorization; this change plans it but does not perform it.
- **A required check makes an urgent fix unmergeable when CI is broken for an
  unrelated reason** (a runner outage, a `setup-uv` regression) → A repository
  admin can temporarily lift the requirement; the escape hatch is deliberately a
  privileged, visible action rather than an automatic bypass. Worth knowing
  before the first incident rather than during it.
- **A parked adapter is later registered and silently stays omitted, so it
  ships unmeasured** → The `omit` glob is `adapters/_parked/*`, keyed to the
  directory. Porting an adapter moves the module out of `_parked/`, which
  re-includes it automatically. The obligation is also recorded on backlog items
  019/020/021 so the porting change does not have to rediscover it.

## Migration Plan

Not applicable in the deployment sense — nothing ships to a user and no data
changes. The rollout is ordered so the gate is never enforced against a suite
that cannot meet it:

1. Land the coverage/pytest configuration and the test-layout changes, and
   confirm the re-scoped baseline reads 86%. Do **not** set `fail_under` yet.
2. Add the new tests, module by module, until the measured total is ≥93%.
3. Set `fail_under = 85` and verify the suite still passes.
4. Add the CI workflow and confirm it passes on both Python versions on a real
   pull request. Read the exact check names from that run.
5. Apply the branch protection rule requiring those checks (decision 9), then
   confirm a deliberately coverage-dropping pull request is refused.
6. Update `docs/development.md`.

Rollback is a git revert of the configuration; no state outside the repository
is touched.

## Open Questions

None. The one question this design previously carried — whether the workflow
should be an advisory check or a required one — was resolved by the user in
favour of blocking, and is now decision 9.
