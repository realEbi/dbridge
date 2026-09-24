## 1. Server workflow policy

- [x] 1.1 Update AGENTS.md with worktree isolation, standing apply authorization, PR delivery, and guarded post-merge refresh; verify the rules preserve original branch/files/commits and reconcile existing authorization language.
- [x] 1.2 Update docs/development.md with setup, local-plan transfer, paired worktrees, PR delivery, refresh, and cleanup examples; verify commands and relative links against the repository and installed Git/GitHub CLI.
- [x] 1.3 Add concise OpenSpec apply guidance pointing to the policy owners; verify `openspec instructions apply --change adopt-worktree-change-delivery --json` loads it and preserves the standard schema.

## 2. Cross-repository review and closure

- [x] 2.1 Review the linked dbridge.nvim workflow change for policy agreement and paired integration paths; verify both original checkouts retain their recorded branch, HEAD, and status.
- [x] 2.2 Validate the documentation-only change with strict OpenSpec validation and whitespace/link checks, record results, and prepare its archive links; verify the final diff contains only the intended documentation and planning artifacts.

## Verification record

- `openspec validate --all --strict --no-interactive`: 8 items passed, including
  this docs-only change and 7 existing capability specs. Existing long-requirement
  notices are informational; `skip_specs: true` correctly accepts zero deltas.
- OpenSpec apply instructions load the worktree, delivery, and refresh guidance
  under the unchanged `spec-driven` schema.
- All 31 local Markdown link targets and the new lifecycle heading resolve.
  The companion archive link targets the linked client change delivered alongside
  this PR; it becomes available on the integration branch after that PR merges.
- Installed Git and GitHub CLI help confirm the worktree flags, explicit PR
  base/head/body-file options, and PR merge/head metadata fields. New worktree
  creation from `origin/dbridge-2.0` succeeded with `--no-track`.
- `git diff --check` and whitespace checks over changed and untracked artifacts
  passed. Independent review found no policy or command contradictions; its
  missing reciprocal client link finding was fixed.
- Both original checkouts remain clean on `dbridge-2.0` at their recorded HEADs.
  The server's two pre-existing local-only commits remain intact and are excluded
  from this topic branch. No post-merge refresh or cleanup has been attempted.
- Runtime tests, lint, type checking, and client integration tests were not run:
  this change modifies only policy, development documentation, and OpenSpec
  planning/configuration. No runtime behavior or protocol requirements change.
