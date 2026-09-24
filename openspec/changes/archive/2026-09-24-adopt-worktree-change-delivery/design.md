## Context

See [proposal.md](proposal.md) for motivation and repository ownership. Existing
policy covers OpenSpec artifacts and verification but leaves checkout isolation,
PR delivery, and post-merge refresh to each session. The original server checkout
already contains local planning commits; those must not enter this workflow PR.

## Goals / Non-Goals

**Goals:** Make checkout isolation and authorized PR delivery the normal apply
process, including paired repositories and safe resumption across sessions.

**Non-Goals:** Runtime changes, new product requirements, generated skill edits,
automatic merges/releases, or repair of existing local branch divergence.

## Decisions

- Put mandatory policy and authorization in `AGENTS.md`, executable examples and
  exceptional cases in `docs/development.md`, and short routing guidance in
  `openspec/config.yaml`. Generated integrations are replaceable and therefore
  unsuitable policy owners. No runtime ADR is superseded.
- Record the original checkout path, branch, HEAD, upstream, and status, plus the
  PR target and topic worktree, in the session handoff. Start a topic branch at
  the fetched target (`origin/dbridge-2.0` by default), not the original HEAD.
  Transfer only the selected plan when it exists locally. A direct branch switch
  or automatic stash would disturb the user's working location.
- Use `.worktrees/<change>/<repo>` beside the original repositories, with a
  linked change and independent PR per owner. The client change owns its policy
  updates. Neither merge depends on protocol migration or runtime integration.
- The user explicitly chose standing authorization for scoped commits, pushing,
  and opening a GitHub PR when applying a plan. Keep merging, tags, and releases
  separately authorized. Finish verification and existing OpenSpec closure before
  delivery, and reuse an existing change PR when resuming.
- After GitHub confirms merge, fetch the original checkout and fast-forward only
  if its recorded identity is unchanged, it is on the PR target with the expected
  upstream, its worktree/index are clean, and it has no commits ahead of that
  upstream. Otherwise report the condition without rewriting local state. A
  plain pull could merge divergence; `--ff-only` alone does not detect ahead-only
  local work. Cleanup must preserve dirty or unpublished topic work.

## Risks / Trade-offs

- Instructions depend on agent compliance rather than hooks → keep the mandatory
  entry-point rules in AGENTS and surface them in OpenSpec apply context.
- Worktrees use more disk and separate dependencies → reuse a verified existing
  change worktree and clean up only after merge with no remaining local work.
- Selected plans may be mixed with unrelated local edits → transfer only reviewed
  artifacts or hunks; do not reset, stash, or cherry-pick mixed commits wholesale.
- Primary checkout may change while the PR is reviewed → recheck its recorded
  branch, HEAD, upstream, and clean status before refreshing; preserve on mismatch.

## Migration Plan

Apply this documentation change in fresh paired worktrees from each remote
integration tip. Validate links, examples, whitespace, OpenSpec metadata, and
policy agreement; runtime tests are unnecessary for prose-only changes. Archive
each verified change and open separate PRs. Leave originals unchanged until a
separately authorized merge; any existing divergence remains outside this change.
Reverting the documentation commits reverses the policy without runtime effects.
