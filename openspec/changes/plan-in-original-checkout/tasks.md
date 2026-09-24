## 1. Policy documents

- [ ] 1.1 In `AGENTS.md`, add to the OpenSpec workflow section that planning happens in place in the original checkout, and that a plan the user declares final is committed as plan-only paths on the current branch and pushed (asking first if other unpushed commits would be published); in *Worktrees and PR delivery*, narrow plan transfer to plans absent from the PR target and add finalization to the authorization bullet. Verify that the section still says merges, tags, and releases need a separate instruction
- [ ] 1.2 In `docs/development.md`, replace "Prefer creating new plans in their eventual topic worktree" with a *Planning* subsection under *Working on a change* covering in-place planning, the finalization question, plan-only staging, and the push; narrow the *Start or resume* transfer paragraph to the fallback case. Verify with `grep -n -i "plan" docs/development.md` that no remaining sentence prefers worktree planning
- [ ] 1.3 In `openspec/config.yaml`, update the `context` line about worktrees and the first `operations.apply.guidance` entry to say that finalized plans are already on the PR target and transfer is a fallback; verify with `openspec instructions apply --change plan-in-original-checkout --json` that the returned guidance matches

## 2. Verification and closure

- [ ] 2.1 Walk through representative cases against the edited documents: a fresh propose on `dbridge-2.0`; a plan revised before finalization; finalization with other unpushed commits present; a plan finalized on a non-target branch; and a cold apply session for a pushed plan. Record in `verification.md` where each write lands and what gets committed, pushed, or transferred
- [ ] 2.2 Check changed links, run `git diff --check` and `openspec validate plan-in-original-checkout --strict`, confirm that no skill, command, or product code changed, and archive the change (no capability synchronization, since `skip_specs: true`)
