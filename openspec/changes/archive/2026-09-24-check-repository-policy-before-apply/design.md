## Context

See [proposal.md](proposal.md). The existing worktree policy is correct for apply, but the generic skill can begin implementing after reading only stale local context. The three generated entry points share a workflow body with tool-specific invocation examples. No runtime ADR or client/server protocol decision changes.

## Goals / Non-Goals

Make repository policy an explicit prerequisite to writes and implementation delegation, including when resuming an existing session or adding an owning repository. Keep actual branch, worktree, verification, and delivery policy in the repository's existing owners. This change adds no sandbox, write hook, installed-package patch, global policy, or client-repository edit.

## Decisions

- Add a preflight before the existing apply steps. Read applicable on-disk AGENTS.md/overrides and required references, record checkout identity/state, and inspect instructions at a fetched known PR target/upstream without updating the original checkout. Reading local AGENTS alone would reproduce the reported failure.
- Fulfill the repository's checkout prerequisites before edits, dependency setup, task-checkbox writes, or implementation delegation. Worktrees are required only where repository/user instructions require them. Re-read instructions and obtain OpenSpec paths in the resulting owning worktree; keep an explicitly selected standalone store selected.
- Pass explicit owning paths and constraints to subagents. Recheck when scope, policy, or checkout changes. Preserve OpenSpec's blocked state, task evidence requirements, and explicit user authorization.
- Align completion text with required and already-authorized repository delivery steps. The generic archive suggestion is a fallback, not a reason to skip local completion requirements or grant publication permission.
- Maintain the same generic extension in all three tracked apply entry points at the user's request. This is an instruction-loading extension, not a second owner of dbridge policy. Document regeneration review because OpenSpec can overwrite generated files; do not patch the global installation or introduce a new command name.

## Risks / Trade-offs

- Prompt instructions still depend on agent compliance; they do not enforce filesystem permissions. Verify realistic decisions independently and describe that limit honestly.
- Regeneration can remove the local extension. The development guide identifies its three owners and requires retaining or reapplying equivalent behavior when refreshing integrations.
- A missing remote, inaccessible target, or genuinely conflicting instruction needs an explicit reported resolution before dependent edits; an isolated/local-only repository should not be forced into an invented remote workflow.

## Migration Plan

Update the tracked entry points together in the topic worktree, validate metadata and OpenSpec artifacts, and independently exercise the preflight with representative repository states. Archive this documentation-only change after verification. Reverting these instruction/document changes restores the upstream flow. No runtime suite or capability synchronization is needed because product code and specs are unchanged.
