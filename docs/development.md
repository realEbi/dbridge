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
changes. `pytest-asyncio` runs async tests and fixtures in auto mode with a loop
per test. Await Adapter/Engine database methods and close every Session in fixture
teardown; Profile operations and Adapter declarations remain synchronous.

Concurrency ordering tests use Event-gated jobs rather than elapsed-time guesses.
Real SQLite/DuckDB cancellation tests use explicit timeouts and verify the same
Session remains usable. In-process pipe tests cover reply ordering and shutdown;
subprocess tests also check exit status and clean stdout. Run both supported
Python versions for changes to the execution model:

```console
uv run --python 3.11 --group types mypy src/dbridge tests
uv run --python 3.11 ruff check src/dbridge tests
uv run --python 3.11 --group test pytest --cov
uv run --python 3.12 --group types mypy src/dbridge tests
uv run --python 3.12 ruff check src/dbridge tests
uv run --python 3.12 --group test pytest --cov
```

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
and in the owning documents. The apply entry points carry a narrow local extension
that requires loading and following those instructions before writes or delegation:

- [Codex apply skill](../.agents/skills/openspec-apply-change/SKILL.md)
- [Claude apply skill](../.claude/skills/openspec-apply-change/SKILL.md)
- [Claude apply command](../.claude/commands/opsx/apply.md)

Keep that generic preflight and repository completion behavior aligned across all
three entry points. Branch names, worktree layouts, verification gates, and
publication policy still belong in this guide, AGENTS.md, and OpenSpec context.
The extension checks current on-disk instructions and policy from a fetched known
target before resolving the owning worktree; it is an agent instruction, not a
filesystem write restriction.

Refresh integrations with `openspec update` when intentionally upgrading OpenSpec;
review that diff and record the new version here. OpenSpec 1.13.0 replaces whole
generated files: even a same-version update can replace customized Claude commands
and skills when it detects command drift, and forced/version updates can replace
the Codex skill too. Preserve or reapply equivalent repository preflight and
completion behavior in all three entry points before using the regenerated apply
workflow. Verify stale local instructions, required worktree setup, nested/other
repository ownership, explicit user constraints, and CLI blocked-state handling.
Remove the local extension only when the generator supplies equivalent behavior.
For installation and supported tools, see the
[OpenSpec project](https://github.com/Fission-AI/OpenSpec).

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

### Planning

Explore, propose, and revise plans in the original checkout on its current branch.
Do not create a worktree for planning. Drafts stay local while the user reviews
and revises them. When the artifacts are complete, ask "Is this plan final?"
unless the user has already declared it final. Proposing alone does not authorize
publication or implementation. A later revision before apply follows the same
finalization flow; revisions discovered during apply belong in the topic worktree
and its implementation PR.

Declaring a plan final authorizes committing its plan-only paths, pushing a
`plan/<change>` branch, opening its PR, and merging that PR after the required
checks pass. Plan-only paths are the selected change directory and directly
related planning edits, such as marking its backlog item planned and linking the
change. Inspect the actual hunks: implementation edits and unrelated changes are
excluded even if they share a file with a planning edit. Implementation PR merges,
tags, and releases still need a separate instruction.

1. Fetch the selected target (`dbridge-2.0` by default) and inspect the original
   branch, HEAD, upstream, index, working tree, and commits ahead of the target.
   Delivery requires the current branch to be the PR target branch, no unpushed
   commits except this plan's, and no staged changes outside its plan-only edits.
   Record the state and the plan-only paths before writing. If a precondition
   fails, report it and ask how to proceed; do not switch branches, reset, rebase,
   stash, or publish unrelated work. A plan finalized on a non-target branch stays
   there for the [apply transfer fallback](#start-or-resume), without a plan PR
   from that branch. Unrelated unstaged or untracked files may remain and must be
   preserved; do not stage them.
2. Review and stage only the selected plan-only paths or hunks, then inspect
   `git diff --cached` and commit on the current branch. Do not use `git add .`.
   Validate the plan with `openspec validate <change> --strict` and check
   both `git diff --check` and `git diff --cached --check` before committing.
   Inspect all commits and the complete diff against the fetched target, not just
   the latest commit, to confirm the
   plan branch will contain only this plan's edits.
3. Push that same commit to a uniquely named plan branch without switching the
   checkout or changing its upstream, then open the PR. For example, substitute
   the selected change and target and write a reviewed PR description first:

   ```sh
   change_name=example-change
   target_branch=dbridge-2.0
   plan_branch="plan/$change_name"
   plan_head=$(git rev-parse HEAD)
   git push origin "HEAD:refs/heads/$plan_branch"
   gh pr create --base "$target_branch" --head "$plan_branch" \
     --title "Plan $change_name" --body-file /path/to/plan-pr-body.md
   ```

   Reuse an existing PR only after verifying it belongs to this plan and its diff
   remains plan-only. Never force-push over another branch's work.
4. Wait for required checks on the PR's current head. Inspect its base, head,
   full diff, and mergeability again before merging. For the selected PR number:

   ```sh
   gh pr checks <number> --required --watch --fail-fast
   gh pr view <number> --json baseRefName,headRefName,headRefOid,mergeable
   gh pr diff <number>
   gh pr merge <number> --merge --match-head-commit "$plan_head"
   ```

   Run the merge only when required checks have passed, the head still matches
   the reviewed commit, the diff is exactly the plan-only edits, and GitHub
   reports it mergeable. Pending or unknown results require waiting; failing
   checks, conflicts, or any other diff stop delivery and must be reported.
   Leave a failing PR open. Do not bypass protection or use squash/rebase: a merge
   commit preserves the local plan commit as an ancestor of the target.
5. Confirm GitHub reports the PR as `MERGED` with the intended base and head, then
   fetch the target. Recheck that the original branch and HEAD still match the
   target branch and post-commit `plan_head`, all local plan commits are now
   ancestors of the fetched target, and the index and unrelated files are
   unchanged. Run
   `git pull --ff-only origin "$target_branch"` in the original checkout. Verify
   HEAD equals the fetched target and ahead/behind counts are both zero. With
   no unrelated files the checkout is now clean; otherwise they remain as they
   were. If identity changed or fast-forward would overwrite local files, leave
   the checkout unchanged and report it. Do not reset, stash, or rebase to make
   the refresh fit. This planning refresh permits the previously recorded
   unrelated files; implementation refresh uses the stricter conditions below.
6. After confirmed merge and successful fast-forward, verify the remote plan
   branch still points at the merged PR head and delete it with
   `git push origin --delete "$plan_branch"`. If it has advanced, retain it and
   report the new work. This flow creates no local plan branch to delete.

A cold apply session fetches the PR target and finds the finalized plan there.
The topic worktree starts from that target with no plan transfer. The workflow is
instruction-based; these checks do not create a filesystem write barrier.

## Worktree and PR lifecycle

Applying a plan starts or resumes a separate topic worktree. The original checkout
is the user's stable repository location; keep its current branch, files, index,
and local commits intact. This also applies when the plan was written there.
[Planning](#planning) delivers finalized plans to the PR target before apply.

### Start or resume

Record the original absolute path, branch, HEAD, upstream, and status, together
with the chosen PR target and topic worktree/branch, in the session handoff. These
are local session details, not machine-specific paths to commit to project docs.
Inspect existing worktrees before making another one:

```sh
git status --short --branch --untracked-files=all
git branch --show-current
git rev-parse HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
git worktree list
```

The integration target is `origin/dbridge-2.0` unless the user selects another
target. Fetch it, then branch from its remote tip. Do not use the original HEAD
as the base: it may include unrelated local planning commits. For example, from
the original repository, substitute the selected change name:

```sh
repo_dir=$(git rev-parse --show-toplevel)
change_name=example-change
topic_branch="change/$change_name"
topic_dir="$(dirname "$repo_dir")/.worktrees/$change_name/dbridge"
git fetch origin
git worktree add --no-track -b "$topic_branch" "$topic_dir" origin/dbridge-2.0
cd "$topic_dir"
```

Use a unique topic name. If the change already has a worktree, verify its branch,
base, selected plan, and local state, then resume there without replacing or
discarding existing work. Never force a second checkout of a branch. A detached
original checkout or missing upstream does not prevent isolated work, but must
be recorded and prevents automatic post-merge refresh.

Finalized plans normally already exist on the fetched PR target. Only if the
selected plan is absent there, copy its local change directory and only necessary
related edits into the topic worktree as a fallback. Inspect
committed and uncommitted content before transferring; cherry-pick only commits
whose entire diff belongs to this change, otherwise transfer reviewed paths or
hunks. Preserve the original files, commits, and index. Do not copy unrelated
plans or generate a replacement plan that loses agreed decisions. If the required
edits cannot be separated confidently, resolve that scope before implementing.

Run OpenSpec from this worktree so its nearest root is the intended repository.
All implementation, dependency setup, verification, documentation updates, spec
synchronization, and archive happen here. Worktrees share Git history but have
separate working files and environment setup; use the checks documented above.

For server/client changes, use sibling worktrees under the same change directory:

```text
dbms/.worktrees/<change>/dbridge
dbms/.worktrees/<change>/dbridge.nvim
```

Each owner needs its own linked OpenSpec change, verification, commit, and PR.
Run client integration checks from its worktree against the paired server
worktree, using the client's documented `DBRIDGE_SERVER_CMD` override if the
layout differs. Never accidentally test the original server checkout. Follow
each repository's own development instructions and compatibility/merge order.

### Deliver the PR

An apply request authorizes the scoped commit, topic-branch push, and GitHub PR
after verification, unless the user explicitly limits delivery. Finish the
closure steps below, inspect the complete diff against the PR target, and stage
only intended paths. Reuse the existing topic PR when resuming. A typical delivery
from the worktree is:

```sh
git diff --check
git diff origin/dbridge-2.0...HEAD
git diff
git status --short
git add <explicit-paths>
git diff --cached
git commit -m "<describe the change>"
git push -u origin "$topic_branch"
gh pr create --base dbridge-2.0 --head "$topic_branch" \
  --title "<describe the change>" --body-file /path/to/pr-body.md
```

Set these values explicitly when resuming in a new shell. Use the selected base
when it differs from `dbridge-2.0`. The PR description explains the result,
verification, limitations, and any linked owner PR or required merge order.
Report the PR URL and checks. Merging is a separate user decision, as are tags and
releases; do not infer their authorization from applying a plan or opening a PR.

### Refresh after merge

These conditions govern implementation PRs; plan PRs use the finalization flow
in [Planning](#planning). After an authorized implementation merge, confirm GitHub
reports the intended PR as `MERGED`.
Then fetch the recorded original checkout and inspect it again. Substitute the
recorded absolute path and selected upstream in these commands:

```sh
gh pr view <number> --json state,baseRefName,headRefName,headRefOid,mergeCommit
git -C "$repo_dir" fetch origin
git -C "$repo_dir" status --short --branch --untracked-files=all
git -C "$repo_dir" branch --show-current
git -C "$repo_dir" rev-parse HEAD
git -C "$repo_dir" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
git -C "$repo_dir" rev-list --left-right --count HEAD...origin/dbridge-2.0
```

The last output is **ahead, behind**. Refresh only if the recorded branch, HEAD,
and upstream still match, the branch/upstream are the selected PR target, the
index and working tree are clean (including untracked files), and ahead is zero.
Then run `git -C "$repo_dir" pull --ff-only` and verify its HEAD equals the fetched
upstream. If it was already equal, no pull is necessary. `--ff-only` alone is
insufficient: an ahead-only branch can report "already up to date" while still
holding local commits.

If any condition fails, leave the checkout unchanged and report the branch,
dirty state, or ahead/behind counts that prevented refresh. Keep an original
checkout on another branch where it is; report that the merged target has been
fetched. Never automatically merge, rebase, reset, stash, or switch that checkout
to complete the refresh. Resolving existing local work needs a separate decision.

After confirmed merge, a topic worktree may be removed only when it is clean and
its HEAD matches the merged PR's `headRefOid`, with no later or
unpublished work. Check each repository separately. Use `git worktree remove
<topic-path>` without force. Retain a branch if Git cannot safely delete it with
`git branch -d`; squash/rebase merges may require a separate cleanup decision.
Never remove the original checkout or another change's worktree.

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
