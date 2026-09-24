# AGENTS.md

dbridge is a Python stdio JSON-RPC server with Transport / Core Engine / Adapters
boundaries. The package lives under `src/dbridge/`; the entry point is
`python -m dbridge.server`.

## Before starting work

1. Read [CONTEXT.md](CONTEXT.md) for domain terms and
   [current architecture](docs/architecture.md) for implemented behavior.
2. Read the relevant [roadmap](docs/roadmap.md) milestone,
   [backlog item](docs/backlog/README.md), and [ADRs](docs/adr/).
3. Inspect active OpenSpec changes, relevant capability specs, source, and tests.
   Use `openspec list --json` for changes and `openspec list --specs` for specs.
4. Keep the distinction between implemented behavior, accepted requirements,
   proposed changes, and future ideas explicit. If evidence conflicts, record
   the mismatch and resolve it in the change; do not silently rewrite intent.

## Documentation ownership

Each document has one job. Update the relevant owners in the same change as the
work they describe; use links for detail owned elsewhere.

| Document | Owns | Update when |
|---|---|---|
| [README.md](README.md) | User setup, usage, supported RPCs and settings | Public usage or support changes |
| [CONTEXT.md](CONTEXT.md) | Domain vocabulary | A term is introduced or its meaning changes |
| [docs/architecture.md](docs/architecture.md) | Current runtime structure, boundaries, and limits | Implemented architecture changes |
| [docs/roadmap.md](docs/roadmap.md) | Future outcomes, proposed sequencing, dependencies | Direction changes or an outcome ships |
| [docs/adr/](docs/adr/) | Enduring architectural decisions and rationale | A significant decision is accepted or superseded |
| [docs/backlog/](docs/backlog/README.md) | One file per deferred idea, defect, or open question | Work is discovered, selected, resolved, or dropped |
| [docs/development.md](docs/development.md) | Tool setup, workflow commands, verification, release process | The development process changes |
| [docs/manual-testing-guide.md](docs/manual-testing-guide.md) | Reproducible manual checks | The demonstrated behavior or test setup changes |
| [openspec/specs/](openspec/specs/) | Accepted, testable capability contracts | A verified change is synchronized |
| [openspec/changes/](openspec/changes/) | Active proposal, requirement deltas, design, and tasks | Scope, decisions, implementation, or verification progresses |
| [openspec/config.yaml](openspec/config.yaml) | Concise OpenSpec context and artifact/operation guidance | Project-wide planning conventions change |
| AGENTS.md | Reading order, routing, and document maintenance rules | Ownership or engineering conventions change |

Current architecture describes implemented code. The roadmap does not establish
current behavior. Specs are contracts, not proof that the implementation conforms;
check the code/tests and record discrepancies. New capability specs can grow
incrementally as their areas are changed.

## OpenSpec workflow

Use the standard `spec-driven` schema for features, behavior changes, substantial
refactors, and workflow migrations. Small spelling/link corrections can be direct
edits. A tracked change with no requirement changes uses `skip_specs: true` in
its `.openspec.yaml`; do not invent product requirements for documentation work.

- Explore uncertain scope; propose one coherent outcome with a descriptive
  kebab-case name. Create change scaffolds with the OpenSpec CLI. Planning
  (explore, propose, and revisions before apply) happens in the original checkout
  on its current branch; do not create a worktree for planning.
- Put requirements and testable scenarios in the change's delta specs, technical
  choices in its design, and the only implementation checklist in `tasks.md`.
  Include design when the schema's conditions apply.
- When the artifacts are complete, ask whether the plan is final unless the user
  has already declared it final. Finalization authorizes delivery of the change
  directory and directly related planning edits through a plan-only PR: commit
  in place, push the same commit as `plan/<change>`, merge with a merge commit
  after required checks pass, then fast-forward locally. Follow the preconditions
  and failure handling in [Planning](docs/development.md#planning).
- Review the artifacts, then apply the requested implementation. Plan revisions
  discovered during apply stay in its topic worktree and implementation PR.
- Verify each task before checking it off. New unrelated findings go into
  individual backlog files, with evidence and the owning repository.
- Before completion, update every affected document in the ownership table.
  Synchronize verified spec deltas, archive the completed change, and update
  backlog links to its archive location. Update roadmap outcomes and remaining
  dependencies; do not mark a milestone done because just one task finished.

Backlog conventions and the item template live in
[docs/backlog/README.md](docs/backlog/README.md). Keep item IDs stable. A selected
item links its OpenSpec change; completed/dropped items retain a brief resolution.
Auxiliary engineering skills may assist within this workflow. Do not create
separate phase PRDs, duplicate task trackers, or skill-specific implementation
plans. Read relevant history from Git when needed.

## Worktrees and PR delivery

Applying an OpenSpec plan uses a separate topic worktree. The original checkout
stays on its current branch with its files, index, and local commits preserved.
Do not switch it, stash its changes, or implement there as part of apply.

- Before apply, record the original path, branch, HEAD, upstream, and working-tree
  status, plus the selected PR target, topic branch, and worktree path in the
  session handoff. Fetch and create the topic worktree from the remote PR target
  (`origin/dbridge-2.0` by default), not from incidental original-checkout commits.
  Resume an existing change worktree only after checking its identity and state.
- Keep worktrees outside the original checkout, preferably under
  `../.worktrees/<change>/<repo>`. Finalized plans normally already exist on the
  fetched PR target. Only when the selected plan is absent there, transfer its
  local directory and required related edits as a fallback. Preserve their
  originals and keep unrelated work out of the topic branch.
- Run implementation, verification, documentation updates, and OpenSpec commands
  inside the owning worktree, including spec synchronization and archive before
  PR delivery. Follow [development instructions](docs/development.md#worktree-and-pr-lifecycle)
  for setup, paired repositories, and cleanup.
- A request to apply a plan authorizes scoped commits, pushing the topic branch,
  and creating or updating its GitHub PR after verification. Review the final
  diff and report the PR and checks. An explicit user restriction overrides this
  standing authorization. Implementation merges, tags, and releases still
  require a separate user instruction. Declaring a plan final authorizes only
  its plan-only PR merge, after required checks pass and GitHub reports it
  mergeable; any other diff, failing checks, or conflicts stop that delivery.
- After GitHub confirms an authorized implementation merge, fetch and refresh
  the recorded original checkout only when its branch, HEAD, and upstream still
  match the record, it is on the PR target, it is clean (including untracked
  files), and it has no commits ahead of the upstream. Pull with `--ff-only`; never automatically
  merge, rebase, reset, or stash to make it fit. Otherwise leave it unchanged and
  report the exact condition. Do not switch another current branch to the target.
- Remove a topic worktree only after confirmed merge and after checking that it
  has no dirty or unpublished work. Never force cleanup or delete unmerged work.

## Cross-repository work

This repository owns server behavior and the DSP contract. Client repositories own
editor/UI behavior. That ownership does not change: server specs never describe
editor presentation, and client specs never restate the protocol contract.

A session may be rooted above both repositories and may edit either one. Editing a
repository requires its own linked OpenSpec change in its own `openspec/`, and that
repository's AGENTS.md governs every file under it — reading order, guardrails,
verification commands, and coverage gates. OpenSpec resolves by nearest root, so run
its commands from inside the repository they target, and keep each repository's
planning artifacts, backlog items, and commits in that repository.

Naming a backlog item owned elsewhere still does not by itself authorize editing that
repository; the linked change does. For cross-repository work, name each owner, link
the corresponding changes, define protocol compatibility, and verify the shared flow
with the owning repository's tooling. Commit each repository separately, and only with
the user's authorization, including the standing apply authorization above. Use a
paired worktree and PR for each owner; integration checks must use those worktrees.

## Engineering conventions

- Use the glossary: Profile is persisted configuration; Session is a live Adapter
  binding and can be created from inline configuration too.
- Transport, Dispatcher, and Core Engine coordinate work on one asyncio loop.
  Database-touching Adapter methods are async; driver calls and cancellation stay
  inside Adapters. SQLite uses one Lane, DuckDB query and metadata Lanes. Preserve
  per-Session execute order and cancellation isolation. ADR-0003 records the
  provisional contract, which a native async MySQL driver must validate.
- Keep driver imports in Adapters. Only SQLite and DuckDB are currently registered;
  parked adapters must not become load-time dependencies.
- DuckDB execution uses native fetch methods without pandas.
- Keep stdout reserved for protocol frames. Use logging for diagnostics.
- Preserve byte-based `Content-Length` framing and UTF-8 cursor offsets.
- Preserve result column order, explicit truncation warnings, and Profile/Session
  separation. Query execution fetches at most `max_rows + 1` rows through the
  Adapter before the executor truncates; release capped statements before replying.
- Clients manage Profiles through RPCs. Tests and examples use isolated temporary
  data/configuration and clean up subprocesses.
- Prefer small working slices and meaningful behavior verification. Test order is
  a per-change choice; match checks to risk and avoid tests for prose-only edits.
- Coverage of `src/dbridge` must stay at or above 85%; `pytest --cov` fails below
  it, and the same gate runs on pull requests. Restore coverage rather than
  lowering the threshold, and write tests that assert behavior — a test added
  only to execute a line is a liability. Record dead code and defects found while
  testing as backlog items instead of covering or fixing them in an unrelated
  change.

Use `uv run python -m dbridge.server` to start, `uv run --group test pytest` for
the server suite, and `uv run --group test pytest --cov` for the gated run. See
[development instructions](docs/development.md) for other checks and release
details. Preserve unrelated user changes. Outside the standing apply and plan
finalization authorizations above, committing and publishing require the user's
instruction. Implementation merges, tags, and releases always require a separate
instruction.

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->
