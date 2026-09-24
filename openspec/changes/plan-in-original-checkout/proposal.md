## Why

Planning and applying usually happen in separate sessions: a plan is explored and
proposed in one context window, then a fresh session is asked only to apply it. The
development guide currently prefers writing new plans in their eventual topic
worktree, which ties planning to implementation setup. Its fallback, transferring
a locally written plan into the worktree, produces duplicate commits or leftover
files that block the original checkout's post-merge fast-forward refresh.

## What Changes

- Planning (explore, propose, update of a plan not yet being applied) happens in
  place in the original checkout, on its current branch. No worktree is created
  for planning.
- When the user declares a plan final, its plan-only paths are committed on the
  current branch and that branch is pushed. This happens at the end of planning,
  independent of any later apply. Plan-only paths are the change directory and the
  directly related planning edits, such as marking the selected backlog item
  planned and linking the change.
- Declaring a plan final authorizes that plan-only commit and push. It does not
  authorize implementation, merges, tags, or releases.
- Apply is unchanged in principle: it starts from a topic worktree based on the
  fetched PR target, which now already contains a finalized plan pushed to that
  target. Transferring a plan from the original checkout remains only as the
  fallback for a plan that is not on the PR target, such as one finalized on
  another branch.
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
step simply does not trigger when the plan is on the PR target.

No backlog item or roadmap outcome applies. This refines the archived
[adopt-worktree-change-delivery](../archive/2026-09-24-adopt-worktree-change-delivery/proposal.md)
and [check-repository-policy-before-apply](../archive/2026-09-24-check-repository-policy-before-apply/proposal.md)
changes. Only this repository changes. Client repositories keep their own
workflow policy.
