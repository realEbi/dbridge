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
See the [manual guide](manual-testing-guide.md) for a runnable client example.

```console
uv run --group test pytest
uv run --group types mypy src/dbridge tests
uv run ruff check src/dbridge tests
```

Use focused tests while changing behavior and run the server suite for runtime
changes. Protocol/adapter changes need real driver or subprocess coverage where
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

The current [release workflow](../.github/workflows/publish-pypi.yml) runs on tag
pushes. It builds wheel/sdist artifacts; TestPyPI and PyPI publishing both depend
on the build and can run independently. Signing and GitHub Release creation
follow PyPI publication. There is currently no pull-request test workflow.

Tags use the `alpha_X.Y.Z` convention, such as `alpha_0.2.10`. The package version
is in [pyproject.toml](../pyproject.toml). Completing an OpenSpec change does not
automatically authorize creating tags, publishing packages, or a release.
