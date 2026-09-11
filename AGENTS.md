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
  kebab-case name. Create change scaffolds with the OpenSpec CLI.
- Put requirements and testable scenarios in the change's delta specs, technical
  choices in its design, and the only implementation checklist in `tasks.md`.
  Include design when the schema's conditions apply.
- Review the artifacts, then apply the requested implementation. Update the
  planning artifacts when discoveries change the agreed scope or approach.
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

This repository owns server behavior and the DSP contract. Client repositories
own editor/UI behavior. For cross-repository work, name the owners, link the
changes, define compatibility, and verify the shared flow; a client-only idea in
this backlog does not authorize editing that client.

## Engineering conventions

- Use the glossary: Profile is persisted configuration; Session is a live Adapter
  binding and can be created from inline configuration too.
- The current Core Engine, Adapters, and stdio loop are synchronous. Revisiting
  that is roadmap work requiring an explicit design and a superseding decision;
  synchronous execution is not a permanent ban on future architecture changes.
- Keep driver imports in Adapters. Only SQLite and DuckDB are currently registered;
  parked adapters must not become load-time dependencies.
- DuckDB execution uses native fetch methods without pandas.
- Keep stdout reserved for protocol frames. Use logging for diagnostics.
- Preserve byte-based `Content-Length` framing and UTF-8 cursor offsets.
- Preserve result column order, explicit truncation warnings, and Profile/Session
  separation. The row cap currently applies after materialization.
- Clients manage Profiles through RPCs. Tests and examples use isolated temporary
  data/configuration and clean up subprocesses.
- Prefer small working slices and meaningful behavior verification. Test order is
  a per-change choice; match checks to risk and avoid tests for prose-only edits.

Use `uv run python -m dbridge.server` to start and
`uv run --group test pytest` for the server suite. See
[development instructions](docs/development.md) for other checks and release
details. Preserve unrelated user changes; committing, publishing, or releasing
requires the user's authorization.

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->
