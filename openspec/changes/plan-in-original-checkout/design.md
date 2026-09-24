## Context

See [proposal.md](proposal.md). The only rule that places planning in a worktree is
the development guide's "Prefer creating new plans in their eventual topic
worktree". AGENTS.md, `openspec/config.yaml`, and the apply entry points require
worktrees for apply only. The post-merge refresh fast-forwards the original
checkout only when it is clean, including untracked files, and has no commits
ahead of its upstream. A plan kept locally breaks one of those conditions: as
untracked files or as unpushed commits.

## Goals / Non-Goals

**Goals:** planning sessions write in place and finish with a pushed plan; apply
sessions start cold from the PR target with the plan already present; the
post-merge refresh keeps working without manual rebases.

**Non-Goals:** no change to apply's worktree, verification, PR delivery, merge
authorization, or refresh conditions; no edits to generated skills or commands; no
change to client repositories' policy.

## Decisions

- **Commit and push at finalization, not at the end of propose.** Drafts are often
  revised within the planning session, so pushing each one would publish churn.
  When planning artifacts are complete, the agent asks whether the plan is final;
  the user's confirmation triggers the commit and push. A later `update` of a plan
  not yet being applied follows the same rule. *Alternative:* push automatically
  after propose. That is simpler, but it publishes unreviewed drafts.
- **Plan-only commit on the current branch.** Stage only the change directory and
  its directly related planning edits, never unrelated working-tree changes. Push
  the current branch to its upstream. If the branch has other unpushed commits,
  report them and ask before pushing, because the push would publish them too.
  *Alternative:* always commit on `dbridge-2.0`. That would force switching the
  original checkout, which the worktree policy forbids.
- **Finalization is the authorization.** It covers only the plan-only commit and
  the push. Merges, tags, releases, and implementation keep their existing
  authorization rules.
- **Keep transfer as a fallback.** A plan finalized on a branch other than the PR
  target is still absent from the apply worktree's base. The existing transfer
  rules stay, narrowed to that case.
- **No entry-point edits.** The apply preflight already reads AGENTS.md and the
  development guide, and propose/explore read AGENTS.md as project instructions.
  Policy stays in its owning documents, which avoids regeneration drift in the
  three customized apply entry points.

## Risks / Trade-offs

- [Plans reach `dbridge-2.0` without a PR] → They contain only planning artifacts,
  and CI still runs on the push. Implementation always goes through a PR.
- [A finalized plan is later abandoned] → It remains an active change until it is
  archived, deleted, or its backlog item is returned to deferred, as today.
- [The push publishes other unpushed commits] → The agent reports them and asks
  first.
- [Prompt guidance, not enforcement] → The agent may still misroute writes. The
  change is verified with a walkthrough of representative cases rather than any
  filesystem barrier.

## Migration Plan

Apply this change through the current worktree/PR flow. After it merges, the new
rule governs the next planning session. The already-planned `bound-result-fetch`
is unaffected: its plan commits are on local `dbridge-2.0` and are published when
this plan is finalized and pushed.
