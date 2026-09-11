## Context

See [proposal.md](proposal.md) for the motivation. The stdio loop calls the
dispatcher synchronously, the Engine calls ordinary adapter methods, and SQLite
and DuckDB materialize results with `fetchall()`. The original design describes
future concurrency and streaming. Existing planning records duplicate status and
contain obsolete skill instructions.

## Goals / Non-Goals

**Goals:** Give each kind of information one owner, preserve deferred scope during
deletion, and make the OpenSpec lifecycle usable across future changes.

**Non-Goals:** Implement roadmap features, adopt a custom schema, generate an
exhaustive product spec baseline, change client repositories, or modify CI.

## Decisions

- Keep `docs/architecture.md` descriptive of implemented behavior and
  `docs/roadmap.md` directional. Roadmap themes have no promised dates or implied
  implementation authorization. A combined document would repeat the existing
  confusion between current and intended behavior.
- Put document ownership and maintenance triggers in AGENTS.md. Keep shell/chat
  workflow examples in `docs/development.md`, user instructions in README, domain
  terms in CONTEXT.md, and enduring decisions in ADRs.
- Give every deferred outcome a numbered backlog file with Repo, Status, Change,
  Origin, problem, desired outcome, and references. The index lists titles only;
  status remains in the item. Active implementation checklists live in OpenSpec.
- Delete the tracked legacy design, phase records, old backlog, and skill-routing
  docs after transferring unresolved content. The user chose deletion; the
  pre-migration revision `80d71d4` preserves history without another docs archive.
- Retain ADR-0001 as an accepted scope decision. Clarify that deferred transaction
  APIs do not inherently require an async implementation.
- Use the installed standard schema with `skip_specs: true` for this migration.
  Add concise project configuration without editing generated integration files.

## Risks / Trade-offs

- Lost future requirements during deletion -> inventory the old backlog, design
  goals, open questions, and future-work list before removal; link each to its new
  home in the roadmap/backlog.
- Historical client defects may already be resolved elsewhere -> preserve their
  provenance and require rechecking the owning repo when selected.
- More backlog files -> keep a compact linked index and one metadata convention.
- A roadmap can look like an approved implementation plan -> label sequencing as
  proposed and require a scoped OpenSpec change for implementation.

## Migration Plan

Create the replacement references and backlog first, update the routing and
cross-links, then delete the exact inventoried legacy files. Check local Markdown
links, stale references, backlog coverage, diff whitespace, OpenSpec validity, and
the documented synchronous call path. Review the Markdown structure and
run the revised manual walkthrough if local dependencies allow it. Runtime tests
are not required for editorial edits. Deleted files are recoverable from Git;
this change does not commit or publish anything.
