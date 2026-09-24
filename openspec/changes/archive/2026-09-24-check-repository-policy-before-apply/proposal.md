## Why

Apply read stale checked-out instructions and edited the original server checkout even though the fetched PR target already required isolated worktrees. The apply entry points need an explicit repository-instruction check before the first write or implementation delegation.

## What Changes

- Add the same repository-policy preflight to the Codex skill, Claude skill, and Claude apply command.
- Read current applicable AGENTS.md files and their required workflow references, inspect target-policy freshness, and fulfill checkout/worktree prerequisites before implementation.
- Re-resolve OpenSpec paths after moving to a worktree; give delegated agents the owning worktree and instruction scope.
- Respect repository verification and authorized completion/delivery steps, while preserving OpenSpec's blocked states and user authorization boundaries.
- Document the narrow local extension and how to preserve it when regenerating integrations.

## Capabilities

### New Capabilities

None. This is a workflow instruction change with `skip_specs: true`.

### Modified Capabilities

None. Server capabilities and DSP compatibility are unchanged.

## Impact

Only dbridge's three tracked apply entry points and development documentation change. Repository policy stays in AGENTS.md, the development guide, and OpenSpec configuration. The user explicitly requested this skill update; no installed OpenSpec package or other repository is edited. This follows the archived adopt-worktree-change-delivery change and supports the development workflow across roadmap outcomes; no product backlog item is selected.
