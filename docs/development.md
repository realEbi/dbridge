# Development

Read [AGENTS.md](../AGENTS.md) for document ownership and engineering conventions,
the [architecture](architecture.md) for current behavior, and the
[roadmap](roadmap.md) for future direction.

## Local setup and checks

Python 3.11+ and uv are used for the server. From the repository root:

```console
uv sync
uv run python -m dbridge.server
```

The server reads framed messages from stdin; it is not an interactive SQL prompt.
See the [manual guide](manual-testing-guide.md) for reusable sample databases and
interactive client checks.

With Make installed, these shortcuts are available from the repository root:

```console
make help
make manual-prepare                         # rebuild persistent sample databases
make check                                  # type and lint checks
make test                                   # automated suite
make test-cov                               # suite with the 85% coverage gate
make test PYTEST_ARGS="tests/adapters -q"    # focused run
```

`manual-prepare` syncs dependencies through `uv run` and replaces
`examples/sample.db` and `examples/sample.duckdb`; changes made to those samples
are discarded. It does not change Profiles. Plain `make` shows help.
Override `UV` if needed (for example, `make test UV=/path/to/uv`), and pass extra
pytest arguments with `PYTEST_ARGS`. The direct commands remain available:

```console
uv run --group test pytest
uv run --group types mypy src/dbridge tests
uv run ruff check src/dbridge tests
```

`make check` runs mypy and Ruff over `src/dbridge` and `tests`. Mypy excludes
`src/dbridge/adapters/_parked/` from recursive discovery while those adapters are
unregistered legacy ports; no missing-driver ignores apply to shipped modules.
Moving a supported port out of that directory includes it automatically. Ruff
still checks parked source without importing its optional drivers.

Use focused tests while changing behavior and run the server suite for runtime
changes.

### Coverage

Coverage is deliberately not enabled by default, so a focused single-test run
stays fast and does not trip the threshold. Add `--cov` for the gated run:

```console
uv run --group test pytest --cov                      # total only
uv run --group test pytest --cov --cov-report=term-missing   # per-module gaps
uv run --group test pytest --cov --cov-report=html    # browsable, htmlcov/index.html
```

Measurement covers `src/dbridge` and nothing else. Test modules are excluded
because a test file scores near 100% by construction and says nothing about the
server. The parked MySQL, PostgreSQL, and Snowflake adapters are excluded while
they remain unregistered and their drivers optional; porting one out of
`adapters/_parked/` brings it back into scope automatically, and that work must
land with tests that hold the floor.

**The suite must stay at or above 85%.** `fail_under = 85` in
[pyproject.toml](../pyproject.toml) makes a run below it exit non-zero, locally
and in CI alike, so a coverage regression is a failure rather than a number
someone has to notice. 85 is the floor, not the target — the suite runs well
above it, and that gap is what keeps an ordinary change from tripping the gate.
Restore coverage rather than lowering the threshold.

Coverage measures only the process pytest runs. `tests/test_e2e_stdio.py` spawns
the server as a subprocess, so the behavior it exercises is proven but not
measured; in-process tests cover the same paths deliberately. Keep both when
changing the transport or entry point.

Generated reports (`.coverage`, `htmlcov/`) are ignored by Git. Protocol/adapter changes need real driver or subprocess coverage where
those boundaries matter. Run the affected client's integration checks for work
spanning repositories. Isolate database and Profile files in temporary locations.

For documentation changes, check links, examples, stale references, and whitespace
instead of adding runtime tests. OpenSpec validation checks artifact structure;
it does not prove the implementation satisfies requirements.

```console
openspec validate --all --strict --no-interactive
git diff --check
```

Do not claim a linter or type checker is clean unless it was run. The
[backlog](backlog/README.md) records known findings; record unrelated failures and
their effect on verification rather than silently expanding a change.

## OpenSpec setup

The initial integration was generated with OpenSpec 1.13.0 using the standard
`spec-driven` schema. Keep the CLI and generated skills/commands aligned across
the coding tools used in the repository.

```console
openspec --version
openspec context --json
openspec list --json
openspec list --specs
```

`openspec/config.yaml` holds shared project guidance. Edit project policy there
and in the owning documents, not in generated tool integrations. Refresh
integrations with `openspec update` when intentionally upgrading OpenSpec; review
that diff and record the new version here. For installation and supported tools,
see the [OpenSpec project](https://github.com/Fission-AI/OpenSpec).

## Working on a change

OpenSpec CLI commands run in a terminal. Workflow skills run in the assistant's
chat. In Codex, use these names (or request the same work in plain language):

```text
$openspec-explore <topic>                  # investigate uncertain scope
$openspec-propose <change>                # create the planning artifacts
$openspec-apply-change <change>           # implement the tasks
$openspec-update-change <change>          # revise the plan when needed
$openspec-sync-specs <change>             # synchronize verified requirements
$openspec-archive-change <change>         # close the completed change
```

Other tool integrations may spell these `/opsx:explore`, `/opsx:propose`,
`/opsx:apply`, `/opsx:update`, `/opsx:sync`, and `/opsx:archive`.

Select a [backlog item](backlog/README.md) or define a focused new outcome. Link
its roadmap milestone and owning repository. Inspect existing specs before
proposing new capabilities. Resolve scope and compatibility, then break the
implementation into verifiable slices. Keep the artifacts coherent as decisions
change. The optional verify skill can review artifact/code agreement; actual
behavior still needs appropriate tests or other direct evidence.

For a documentation/tooling change with no requirement changes, set
`skip_specs: true` in the scaffolded change's `.openspec.yaml`. Design is conditional
under the standard schema. Follow the current CLI instructions rather than
creating placeholder artifacts to make a progress counter green.

## Completing a change

Apply the [ownership table](../AGENTS.md#documentation-ownership): update usage,
current architecture, accepted decisions, domain terms, and examples where
affected. Update roadmap direction/progress and resolve linked backlog items.
Mark tasks complete only after verification, synchronize implemented spec deltas,
and archive the change. Replace active change links with archive links. A
documentation-only change can finish without adding any product specs.

Keep a short verification summary with the change, distinguishing checks that
passed, checks not run, and known failures. For meaningful architecture changes,
add an ADR and mark any superseded ADR accordingly. Preserve historical rationale.

## CI and release

The [test workflow](../.github/workflows/test.yml) runs mypy, Ruff, and the server
suite with coverage on **every** pull request, whatever branch it targets, and on pushes to
`main` and `dbridge-2.0`, across a Python 3.11 and 3.12 matrix. It fails when
coverage falls below the 85% floor, so the threshold is enforced without anyone
choosing to run it. The matrix sets `fail-fast: false` so both versions always
report.

The `pull_request` trigger carries no branch filter deliberately. Work integrates
into `dbridge-2.0` rather than `main`, so a filter on the default branch would
produce a gate that never fires while appearing configured.

Its checks are named `test (3.11)` and `test (3.12)` — GitHub derives them from
the job id, which is why the job deliberately has no `name:` field. Those two
names are what a branch protection rule must require; renaming the job renames
the checks and silently stops the rule from matching.

The [release workflow](../.github/workflows/publish-pypi.yml) runs on tag pushes
and is unaffected by the test workflow. It builds wheel/sdist artifacts; TestPyPI
and PyPI publishing both depend on the build and can run independently. Signing
and GitHub Release creation follow PyPI publication.

Tags use the `alpha_X.Y.Z` convention, such as `alpha_0.2.10`. The package version
is in [pyproject.toml](../pyproject.toml). Completing an OpenSpec change does not
automatically authorize creating tags, publishing packages, or a release.
