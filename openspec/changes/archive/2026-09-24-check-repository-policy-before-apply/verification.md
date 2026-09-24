# Verification

Verified on 2026-09-24. This change edits workflow instructions and documentation only; runtime tests were not run.

- All three apply entry points have identical repository preflight text and preserve their original tool-specific YAML metadata and invocation examples.
- An independent agent read the revised skill without the planning/review conclusions and simulated five cases: stale local policy with unrelated dirty files; nested instruction scope followed by a newly affected client repository; explicit no-commit/no-push/no-PR instructions; a blocked OpenSpec state; and resumption after checkout changes with a selected standalone store. It placed implementation only after the applicable prerequisites, preserved user constraints and blocked states, and retained store ownership.
- The review found two ambiguities: the preflight's own authorized setup writes and standalone-store context paths. Both were clarified, then independently rechecked with no remaining meaningful issue reported. This was an instruction walkthrough, not an automated execution or filesystem enforcement test.
- The skill-creator validator rejects the existing OpenSpec `compatibility` frontmatter key on both unchanged baseline skills and the edited skills. The source metadata was preserved. Disposable copies excluding only that unchanged key passed the validator; original YAML metadata also parsed and matched the baseline exactly. The Claude command metadata parsed unchanged.
- Changed documentation links resolve. `git diff --check` passes. `openspec validate check-repository-policy-before-apply --strict --no-interactive` passes with the explicit `skip_specs: true` exemption; there are no capability deltas to synchronize.
- Installed OpenSpec 1.13.0 source confirms whole-file generation and same-version Claude command-drift detection. The development guide therefore requires preservation/reapplication and review of this local extension after regeneration; no global CLI package was modified.
- The original checkout remained on its recorded branch/upstream with a clean working tree, but separate work advanced its HEAD by a bounded-result-fetch planning commit during this change. That identity change was detected and preserved; no refresh or cleanup of the original checkout was attempted. This change's skill/document edits exist only in its topic worktree, and the unrelated backlog/planning commits are excluded from its branch.

The result remains prompt guidance: it improves instruction loading and task routing but does not create a filesystem write barrier.
