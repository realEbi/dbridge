## Why

Applying a plan in the original checkout mixes implementation with local planning
work and makes returning to the integration branch error-prone. The normal
workflow should preserve that checkout while delivering verified changes through
GitHub PRs, then refresh it safely after merge.

## What Changes

- Require a separate topic worktree for applying an OpenSpec plan, based on the
  fetched PR target rather than incidental local commits.
- Treat an apply request as authorization to commit the scoped work, push its
  topic branch, and open a PR after verification. Merging remains separately
  authorized.
- Record the original checkout and refresh it after confirmed merge only when
  it can safely fast-forward; preserve and report local work or divergence.
- Document paired server/client worktrees and consistent delivery guidance in
  each repository's own policy and development instructions.

## Capabilities

### New Capabilities

None. This is a documentation-only workflow change with `skip_specs: true`.

### Modified Capabilities

None. Server behavior and the DSP contract remain unchanged.

## Impact

The server owns its `AGENTS.md`, `docs/development.md`, and
`openspec/config.yaml`. The client owns equivalent updates in the linked
[dbridge.nvim change](https://github.com/realEbi/dbridge.nvim/blob/dbridge-2.0/openspec/changes/archive/2026-09-24-adopt-worktree-change-delivery/proposal.md); the paired
changes use the same worktree parent and independent commits and PRs. There is
no protocol compatibility or runtime dependency between their merges.

No product roadmap milestone or existing backlog item applies. No runtime ADR
is superseded, and no generated OpenSpec integrations or production code change.
