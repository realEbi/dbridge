## 1. Current architecture and future direction

- [x] 1.1 Create the current architecture reference and update CONTEXT.md and ADR-0001; verify the synchronous request path and documented limits against source.
- [x] 1.2 Create the roadmap and individual backlog entries; verify that all unresolved legacy backlog and design ideas have a destination.

## 2. Workflow and navigation

- [x] 2.1 Update AGENTS.md, README, development instructions, and OpenSpec configuration; verify ownership rules cover planning through archive and roadmap progress.
- [x] 2.2 Update the manual testing guide to use isolated data and profile RPCs; check the example's syntax and run it if dependencies are available.

## 3. Retirement and validation

- [x] 3.1 Delete the exact legacy design, plans, phase PRDs/issues, skill-routing documents, and old backlog; verify they were tracked and their useful content has been transferred.
- [x] 3.2 Check Markdown links and anchors, obsolete references, backlog metadata and coverage, whitespace, and OpenSpec validity; verify runtime source and tests remain untouched.

## Verification

- Checked 61 Markdown files, 258 local links/anchors, and 49 backlog entries;
  no missing targets, duplicate IDs, missing metadata, or whitespace problems.
- Mapped every legacy backlog section, all seven design questions, and all eight
  future-work entries; retained further deferred interface and architecture ideas.
- Executed the Python walkthrough extracted from the manual guide with the
  installed .venv interpreter: SQLite and DuckDB both passed Profile, Session,
  schema, query, completion, row-cap, refresh, and reconnect-persistence checks.
- `openspec validate --all --strict --no-interactive` passed. The CLI also loaded
  the new context and apply guidance successfully.
- `git diff --check` passed; a repository-wide search found no retired document
  references. The AGENTS.md Custom Instructions block was preserved exactly.
- Deleted 23 previously tracked legacy files, recoverable at revision `80d71d4`.
  Runtime source, automated tests, dependencies, and CI configuration are unchanged.
- The full runtime suite, linter, and type checker were not run for this
  documentation-only change. Their unchanged state is not a claim that they pass.
