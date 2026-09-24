# 001 - Rename Profiles without leaving duplicates

- Repo: dbridge, dbridge.nvim
- Status: done
- Change: [server](../../openspec/changes/archive/2026-09-24-rename-profiles-atomically/proposal.md), [client](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-24-rename-profiles-atomically)
- Origin: Legacy backlog 1.1; retained from revision `80d71d4`.

## Problem / opportunity

Editing a Profile name reportedly saves the new name but leaves the old entry in connections.toml. The explorer then hides that duplicate.

## Desired outcome

Rename and edit a Profile in one save request, rejecting name collisions and
missing sources without changing stored Profiles. Preserve the Client's node and
live Session until saving succeeds. The selected design supersedes the historical
save-then-delete suggestion, which could leave duplicates after a partial failure.

## Notes and references

The server owns the optional `previous_name` on `saveProfile` and the single
read-modify-write. The Client sends the original name when editing, changes the
node only on success, and retains its Session and scope state. Crash-safe file
replacement remains a separate issue in [059](059-crash-safe-profile-writes.md).

## Resolution

Implemented and verified in the linked archived server and Client changes. Storage
rejects collisions and missing sources before writing, preserves Profile order,
and replaces the old definition in one save. Real-server Client tests verify
rename/reload, failure feedback, and connected SQLite/DuckDB Session preservation.
