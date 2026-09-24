# Verification

Verified on 2026-09-24. This is a documentation-only workflow change with
`skip_specs: true`; no capability deltas need synchronization.

## Policy review and walkthroughs

An independent reviewer read the edited policy documents and walked through all
six required cases. These are instruction walkthroughs, not automated GitHub
end-to-end tests or filesystem enforcement checks.

| Case | Writes and delivery |
|---|---|
| Fresh propose on `dbridge-2.0` | Write the change artifacts and directly related planning edits in the original checkout. Create no worktree and leave the draft unpublished. After finalization and preflight, commit only the reviewed planning content locally, push that exact HEAD as `plan/<change>`, open the PR, wait for required checks, merge with a merge commit, fast-forward the original, and delete the unchanged remote plan branch. |
| Revision before finalization | Revise the same original-checkout artifacts locally. No commit, push, PR, or merge is authorized by drafting alone. Finalization delivers the reviewed final contents through the same flow. |
| Other unpushed commits or staged changes | Stop finalization delivery before its commit or push. Report the failed precondition and ask; retain the current branch, commits, index, and files. Do not publish unrelated history or silently unstage it. |
| Failing plan-PR checks | Keep the original plan commit, remote plan branch, and open PR. Report the failure. Do not merge, fast-forward, delete the branch, or start implementation. |
| Plan finalized on a non-target branch | Keep artifacts on that original branch; report the delivery precondition and ask. Do not switch, create a planning worktree, or open a plan PR from that branch. A later apply request may copy an absent selected plan and its required related edits into a topic worktree based on the fetched PR target, preserving the originals. |
| Cold apply for a merged plan | Fetch the target and create or verify the topic worktree there. The plan already exists, so nothing transfers. Implementation, plan revisions during apply, verification, archive, commit, push, and implementation PR delivery all use that worktree. Its merge still requires a separate instruction. |

Additional checks confirmed that same-file unrelated hunks are excluded by content,
unrelated unstaged/untracked files are preserved during plan delivery, and the
reviewed PR head is enforced with `--match-head-commit`. Planning refresh is
explicitly distinct from implementation's clean, unchanged, zero-ahead gate.
A differing local revision of an already-present target plan requires scope
resolution; the absence-only fallback does not authorize replacing that plan.

The review found two wording gaps, both fixed and independently rechecked: staged
changes now get `git diff --cached --check`, and planning refresh compares HEAD
against the post-commit `plan_head`. No remaining review findings within scope.

## Checks and limits

- `openspec instructions apply --change plan-in-original-checkout --json` returns
  the revised planning location, normally-present finalized plan, fallback-only
  transfer guidance, and separate implementation merge authorization.
- `rg -n -i 'plan|merg' AGENTS.md docs/development.md openspec/config.yaml` reviewed
  the current policy references; no development instruction prefers worktree
  planning. The old preference remains historical context in the design.
- `openspec validate plan-in-original-checkout --strict` passed with the explicit
  documentation-only exemption. `openspec validate --all --strict --no-interactive`
  passed all 12 active change/spec items before archive; existing long-requirement
  notices are informational.
- `git diff --check` passed. Local Markdown links and heading anchors in the policy
  documents and change artifacts resolve; all 40 were rechecked after archiving.
- Installed `gh pr checks --help` and `gh pr merge --help` confirm the documented
  required-check watch, fail-fast, merge-commit, and head-match options.
- Diff scope is the three policy owners and this change's artifacts. No skill,
  command, product code, runtime tests, capability spec, or branch-protection
  setting changed. No backlog or roadmap outcome applies; architecture, glossary,
  ADRs, usage, and manual examples are unaffected.
- Runtime tests, mypy, and Ruff were not run locally: repository instructions call
  for documentation checks for prose changes. The usual PR CI remains applicable.
  No known verification failures remain.

## Archive

`openspec archive plan-in-original-checkout --skip-specs --yes` completed the
required archive. Its 4/5 notice referred only to task 2.2, which includes the
archive itself; that checkbox was marked complete afterward. All five tasks are
complete. Historical proposal links were adjusted for the archive location.
No capability specs were changed or synchronized.

## Session isolation

The topic worktree started at the fetched target, which already contained this
plan and the earlier transitional plan PR. No plan transfer was needed. All edits
and verification used that worktree. The original checkout stayed on its recorded
branch and HEAD with a clean index and working tree. This apply request authorizes
an implementation PR, not its merge; no original-checkout refresh or worktree
cleanup is performed before a separately authorized merge.
