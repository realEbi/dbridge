## Context

See [proposal.md](proposal.md). The only rule that places planning in a worktree is
the development guide's "Prefer creating new plans in their eventual topic
worktree". AGENTS.md, `openspec/config.yaml`, and the apply entry points require
worktrees for apply only. The post-merge refresh fast-forwards the original
checkout only when it is clean, including untracked files, and has no commits
ahead of its upstream. A plan kept locally breaks one of those conditions: as
untracked files or as unpushed commits.

`dbridge-2.0` requires the `test (3.11)` and `test (3.12)` checks, enforced for
administrators and with no required reviews, so a direct push is rejected. The
repository allows merge commits, and earlier PRs were merged that way.

## Goals / Non-Goals

**Goals:** planning sessions write in place and finish with the plan on the
integration branch; apply sessions start cold from the PR target with the plan
already present; the original checkout returns to clean and zero ahead without
resets or copies.

**Non-Goals:** no change to apply's worktree, verification, implementation PR
delivery, or refresh conditions; no change to branch protection; no edits to
generated skills or commands; no change to client repositories' policy.

## Decisions

- **Finalization, not the end of propose, triggers delivery.** Drafts are often
  revised within the planning session. When the artifacts are complete, the agent
  asks whether the plan is final; the user's confirmation starts delivery. A later
  `update` of a plan not yet being applied follows the same rule.
- **Commit locally, push the same commit as a plan branch, merge with a merge
  commit.** Stage only plan-only paths in the original checkout and commit them on
  its current branch. Run `git push origin HEAD:refs/heads/plan/<change>`, then
  `gh pr create --base <target> --head plan/<change>`. Wait for the required
  checks and merge with `gh pr merge --merge`. The local commit is then an
  ancestor of the target, so `git pull --ff-only` returns the original checkout
  to clean and zero ahead. Finally delete the remote plan branch.
  *Alternatives:* A squash or rebase merge rewrites the hashes and leaves the
  checkout ahead. Preparing the PR in a short-lived worktree requires copying the
  files and then deleting the local copies. A direct push is rejected by branch
  protection.
- **Preconditions, otherwise ask.** Delivery requires the original checkout to be
  on the PR target branch, with no unpushed commits other than this plan's, and no
  staged changes outside the plan-only paths. Unrelated unstaged or untracked
  files may remain; they are never staged, and `--ff-only` refuses to overwrite
  them. If a precondition fails, the agent reports it and asks. A plan finalized
  on another branch uses the apply transfer fallback instead.
- **Narrow merge authorization.** Finalization authorizes merging only a PR whose
  diff is exactly the plan-only paths, after the required checks pass, when GitHub
  reports it mergeable. Failing checks, conflicts, or any other diff stop delivery
  and are reported. Implementation PRs, tags, and releases keep their separate
  authorization.
- **No entry-point edits.** The apply preflight already reads AGENTS.md and the
  development guide, and propose and explore read AGENTS.md as project
  instructions. Policy stays in its owning documents, which avoids regeneration
  drift in the three customized apply entry points.

## Risks / Trade-offs

- [Unreviewed plan merges] → Only planning artifacts are merged, CI must pass,
  and the diff is checked against the plan-only paths before merging.
  Implementation always needs its own PR and merge decision.
- [Waiting for CI extends the planning session] → The checks are short. If they
  fail, the plan stays in its open PR and the failure is reported.
- [A finalized plan is later abandoned] → It remains an active change until it is
  archived or deleted, or its backlog item is returned to deferred, as today.
- [Prompt guidance, not enforcement] → Verified with a walkthrough of
  representative cases, not with a filesystem barrier.

## Migration Plan

Apply this change through the current worktree and PR flow. The already-final
plans for `bound-result-fetch` and this change are published by one transitional
plan PR from the current local `dbridge-2.0`, because they were committed before
this rule existed. That PR also carries a local merge commit whose content is
already on the target. Later plans use one plan PR each.
