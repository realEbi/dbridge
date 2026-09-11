# Verification summary

Per [AGENTS.md](../../../../AGENTS.md) — "Keep a short verification summary with the
change, distinguishing checks that passed, checks not run, and known failures."

## Re-scoped baseline (after section 1, before any new test)

Command: `uv run --group test pytest --cov --cov-report=term-missing`

**Total: 87%** — 539 statements, 67 missed; 84 branches, 10 partial. 75 tests
passed.

For reference, the same suite reported **71%** under the previous configuration,
which measured the `tests` package alongside `dbridge` and did not omit the
parked adapters. Re-scoping alone moved the number to 86%; excluding
abstract-method bodies (design decision 3) moved it to 87%. Neither step added a
single test — this is the honest starting point the new tests build from.

Per-module misses at baseline:

| Module | Cover | Missing |
|---|---|---|
| `server.py` | 0% | 1-9 |
| `protocol/transport/stdio.py` | 66% | 24->17, 27, 34-42 |
| `core/executor.py` | 70% | 8-9 |
| `protocol/errors.py` | 79% | 14-16 |
| `core/engine.py` | 84% | 36-38, 46, 49, 57-58, 71-73 |
| `adapters/sqlite.py` | 85% | 29, 40-41, 44->exit, 59-60, 69, 72, 110, 113 |
| `core/completion.py` | 87% | 29->31, 56-57, 73-74, 120-121, 123-124 |
| `adapters/duckdb.py` | 88% | 34-35, 38->exit, 52-53, 115-116, 138 |
| `config/profiles.py` | 90% | 27-31, 35 |
| `protocol/handlers.py` | 90% | 47-48, 66, 68 |
| `logging/__init__.py` | 90% | 13 |
| `core/schema_registry.py` | 96% | 30 |
| `core/session.py` | 97% | 39->exit |

`fail_under` is deliberately **not** set at this point; it goes in at task 5.2,
once the suite can meet it.

## Result

**Total: 99%** — 539 statements, 4 missed; 84 branches, 1 partial.
**187 tests pass**, up from 75. Floor is 85%; headroom is 14 points.

Every measured module is at 100% except two dead-code sites, both deliberately
left uncovered and recorded as backlog items rather than tested:

| Module | Cover | Missing | Why not covered |
|---|---|---|---|
| `protocol/errors.py` | 79% | 14-16 | `DspError` is never raised or caught — [050](../../../../docs/backlog/050-unused-dsp-error.md) |
| `logging/__init__.py` | 90% | 13 | Unreachable: the `_loggers` cache is never written — [051](../../../../docs/backlog/051-logger-handler-stacking.md) |

A test for either would assert that dead code constructs correctly, which proves
nothing. Covering them is the wrong fix; deciding their fate is the right one.

## Checks run

| Check | Result |
|---|---|
| `uv run --group test pytest` | **passed** — 187 tests |
| `uv run --group test pytest --cov` (Python 3.12) | **passed** — 99.20%, gate satisfied |
| `uv run --python 3.11 --group test pytest --cov` | **passed** — 99.20% |
| Gate bites: `--cov-fail-under=99.5` | **failed as designed** — exit 1, "Required test coverage of 99.5% not reached", all tests passing |
| `uv run --group test pytest --cov --cov-report=html` | **passed** — `htmlcov/index.html` written, gitignored |
| `uv run ruff check src/dbridge tests` | **2 pre-existing failures**, see below |
| `uv run --group types mypy src/dbridge tests` | **21 pre-existing failures**, see below |
| `openspec validate --all --strict --no-interactive` | **passed** |
| `git diff --check` | **passed** |
| CI workflow green on a pull request | **not run** — requires pushing, see *Not done* |

### Known failures (all pre-existing, none introduced)

- **ruff, 2 × F401**: `operator.mul` in `_parked/mysql.py`, `ForeignKey` in
  `adapters/duckdb.py`. Both are exactly what
  [027](../../../../docs/backlog/027-unused-imports.md) already records. Not fixed
  here — that item owns them, and fixing them would widen this change.
- **mypy, 21 errors in 5 files**: 19 in parked adapters (missing driver stubs
  plus imports of modules that no longer exist), 1 for the `_loggers`
  annotation, 1 for `sqlite3.connect` receiving `str | None`. `tests/` is clean
  at 0 errors. Previously unrecorded, now
  [054](../../../../docs/backlog/054-type-check-does-not-pass.md).

Effect on verification: neither checker was clean before this change, so neither
provides a regression signal for it. The suite and the coverage gate do.

## Defects found while testing (recorded, not fixed)

Per AGENTS.md — "New unrelated findings go into individual backlog files". Three
came out of writing the tests; each is pinned by a test asserting *current*
behavior, with a comment saying so, so the backlog item is actionable and the
test changes with the fix:

- **[051](../../../../docs/backlog/051-logger-handler-stacking.md)** — `get_logger`
  declares a `_loggers` cache and never writes to it. Every call adds another
  `StreamHandler` to the same Logger, and `DBAdapter.__init__` calls it, so each
  Session created duplicates the server's log output once more. Measured: five
  adapters → five handlers.
- **[052](../../../../docs/backlog/052-truncated-frame-crashes-loop.md)** — a frame
  whose body is shorter than its `Content-Length` raises `JSONDecodeError` out of
  `read_message`, through `serve`, killing the server. `PARSE_ERROR` (-32700) is
  defined for this and never emitted.
- **[053](../../../../docs/backlog/053-bare-select-offers-nothing.md)** — completion
  for a bare `"SELECT "` returns an empty list rather than falling through to
  keywords, so the more common input behaves worse than a malformed one.

Two plan assumptions were wrong and were corrected against the code rather than
worked around: the `isolated_profiles` fixture was **not** duplicated across two
files (only `test_handlers.py` had it), and a truncated frame is **not** handled
without raising. Both are noted where they mattered.

## Documentation

Updated per the [AGENTS.md](../../../../AGENTS.md#documentation-ownership) table:

- **[docs/development.md](../../../../docs/development.md)** — new *Coverage*
  section (commands, scope, floor, the subprocess caveat); *CI and release*
  rewritten for the new workflow and the required check names.
- **[AGENTS.md](../../../../AGENTS.md)** — *Engineering conventions* gained the
  coverage rule and the gated command. *Custom Instructions* left byte-for-byte
  unchanged.
- **[docs/backlog/](../../../../docs/backlog/README.md)** — items 050–054 added and
  indexed; 019/020/021 annotated with the obligation that porting a parked
  adapter brings it into the measured scope.

Confirmed **no edit needed**: `README.md` (no public usage change — coverage is
developer-facing), `CONTEXT.md` (no new or changed domain term),
`docs/architecture.md` (no runtime or boundary change),
`docs/roadmap.md` (no milestone outcome shipped; this supports every milestone
and completes none), `docs/manual-testing-guide.md` (no manual check changed),
`docs/adr/` (ADR-0001 stands; nothing superseded).

## Not done — needs the user

Tasks 5.4, 5.5, and 5.6 are unchecked. They require pushing to GitHub, opening
pull requests, and a repository-settings change with admin rights on
`realebi/dbridge` — none of which this session performed.

The workflow file is in place and its shape is verified (YAML parses; job id
`test` with no `name:`, so checks derive as `test (3.11)` / `test (3.12)`;
`fail-fast: false` so both always report). The suite passes locally on both
matrix versions at 99%, so the jobs are expected green. **But the coverage gate
is not yet binding**: until the branch protection rule requires those two checks,
a red check can be merged past, and the spec's "Coverage is enforced on pull
requests" requirement is not satisfied. Per task 5.7, this change is not
complete until that is done or explicitly deferred by the user.

## Correction during apply: the CI trigger would never have fired

The workflow originally filtered `pull_request` to `branches: [main]`, following
design decision 8's assumption that `main` is the integration branch. Checked
against the repository, that assumption was wrong:

```console
$ git rev-list --count main..dbridge-2.0
24
$ git log -1 --format='%h %ad %s' --date=short main
4756d18 2026-06-04 adds agent related files and docs
$ git ls-tree --name-only main docs/ openspec/
docs/agents
```

`main` is 24 commits and three months behind `dbridge-2.0` and contains neither
`openspec/` nor `docs/backlog/` — this change builds on both. Work integrates
into `dbridge-2.0`. A base-branch filter on `main` would have shipped a gate
that never fires while looking fully configured, which is worse than no gate at
all.

Fixed by dropping the `branches:` filter from `pull_request` entirely, and
listing both `main` and `dbridge-2.0` under `push`. Dropping the filter is also
the better rule independent of this repository's layout: there is no base branch
where a coverage regression is acceptable. The spec requirement, design decision
8, and `docs/development.md` were all updated to match; the spec gained a
scenario for a pull request into a non-default branch.

## CI enforcement verified end to end

Committed to branch `raise-test-coverage` (off `dbridge-2.0`) and pushed;
[PR #2](https://github.com/realEbi/dbridge/pull/2) targets `dbridge-2.0`.

**Positive case — the checks run and pass (task 5.4).** Both matrix jobs went
green on PR #2, with the total in each job log:

```
test (3.11)  TOTAL  539  4  84  1  99%
test (3.11)  Required test coverage of 85.0% reached. Total coverage: 99.20%
test (3.12)  TOTAL  539  4  84  1  99%
test (3.12)  Required test coverage of 85.0% reached. Total coverage: 99.20%
```

Check names as GitHub reports them: **`test (3.11)`** and **`test (3.12)`** —
observed, not assumed, then used verbatim in the protection rule.

**Protection rule applied (task 5.6).** On `dbridge-2.0`, per the user's choice
of that branch over the stale `main`:

```json
{"checks": ["test (3.11)", "test (3.12)"], "strict": true, "enforce_admins": true}
```

`strict: true` requires a branch to be up to date before merging, so a branch cut
before a coverage-dropping merge cannot go green against stale base state.
`enforce_admins: true` because the repository has a single admin — with it
`false`, the only person the rule applies to could merge past a red check, making
the guard advisory for exactly the wrong person. `required_pull_request_reviews`
is `null`: requiring a review on a solo repository would block every pull request,
since an author cannot approve their own.

To relax the rule if CI ever breaks for an unrelated reason (a runner outage, a
`setup-uv` regression):

```console
gh api -X DELETE repos/realEbi/dbridge/branches/dbridge-2.0/protection
```

**Negative case — the gate actually blocks (task 5.5).** A scratch pull request
deleted seven test files, dropping coverage to 61% while every remaining test
passed. Both jobs failed, attributed to coverage rather than to a test error:

```
ERROR: Coverage failure: total of 61 is less than fail-under=85
FAIL Required test coverage of 85.0% not reached. Total coverage: 60.67%
============================== 75 passed in 2.75s ==============================
##[error]Process completed with exit code 1.
```

GitHub reported that pull request as `mergeStateStatus: BLOCKED` (its
`mergeable: MERGEABLE` refers only to the absence of merge conflicts; `BLOCKED`
is the protection rule refusing the merge). PR #2, with both checks green, reports
`CLEAN`. The scratch pull request was closed unmerged and its branch deleted
locally and on `origin`.

This is the check that distinguishes a real guard from a configured-looking one:
all tests passing plus coverage below the floor still refuses the merge.

Task 5.7 did not apply — it was the contingency for 5.6 being blocked.

## Remaining

Nothing in this change. PR #2 is open and mergeable, awaiting the user's review;
merging is the user's call. After it merges, the change is ready for
`/opsx:sync` and `/opsx:archive`.
