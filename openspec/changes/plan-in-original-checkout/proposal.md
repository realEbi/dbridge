## Why

Planning and applying usually happen in separate sessions: a plan is explored and
proposed in one context window, then a fresh session is asked only to apply it. The
development guide currently prefers writing new plans in their eventual topic
worktree, which ties planning to implementation setup. Its fallback, transferring
a locally written plan into the worktree, produces duplicate commits or leftover
files that block the original checkout's post-merge fast-forward refresh.
`dbridge-2.0` is protected by required CI checks, enforced for administrators, so
plans cannot be pushed to it directly either.

## What Changes

- Planning (explore, propose, and updating a plan not yet being applied) happens in
  place in the original checkout, on its current branch. No worktree is created
  for planning.
- When the user declares a plan final, its plan-only paths are committed in the
  original checkout. The commit is pushed as its own `plan/<change>` branch, a PR
  to the integration branch is opened, and after the required checks pass it is
  merged with a merge commit. The original checkout then fast-forwards. This
  happens at the end of planning, independent of any later apply. Plan-only paths
  are the change directory and directly related planning edits, such as marking
  the selected backlog item planned and linking the change.
- Declaring a plan final authorizes that commit, the plan branch push, the plan
  PR, and merging it once the required checks pass. It does not authorize merging
  implementation PRs, tags, or releases.
- Apply is unchanged in principle: its topic worktree is based on the fetched PR
  target, which already contains any finalized plan. Transferring a plan from the
  original checkout remains only as the fallback for a plan absent from the PR
  target.
- Plan revisions discovered during apply stay in the topic worktree and are
  delivered with the implementation PR.

## Capabilities

### New Capabilities

None. This is a documentation-only workflow change with `skip_specs: true`.

### Modified Capabilities

None. Server capabilities and DSP compatibility are unchanged.

## Impact

`AGENTS.md` (OpenSpec workflow and worktree delivery), `docs/development.md`
(working on a change, worktree lifecycle), and `openspec/config.yaml` (context and
apply guidance) change. The apply, propose, and explore skills and commands are
not edited. They already defer to repository instructions, and apply's transfer
step simply does not trigger when the plan is on the PR target. Branch protection
settings are unchanged.

No backlog item or roadmap outcome applies. This refines the archived
[adopt-worktree-change-delivery](../archive/2026-09-24-adopt-worktree-change-delivery/proposal.md)
and [check-repository-policy-before-apply](../archive/2026-09-24-check-repository-policy-before-apply/proposal.md)
changes. Only this repository changes. Client repositories keep their own
workflow policy.
