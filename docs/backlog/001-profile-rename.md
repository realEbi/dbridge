# 001 - Rename Profiles without leaving duplicates

- Repo: dbridge, dbridge.nvim
- Status: planned
- Change: [server](../../openspec/changes/rename-profiles-atomically/proposal.md), [client](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/rename-profiles-atomically)
- Origin: Legacy backlog 1.1; retained from revision `80d71d4`.

## Problem / opportunity

Editing a Profile name reportedly saves the new name but leaves the old entry in connections.toml. The explorer then hides that duplicate.

## Desired outcome

Preserve the old name until saving succeeds, then remove the original Profile through deleteProfile. Define name-collision and failure behavior.

## Notes and references

Recheck lua/dbridge/explorer.lua handle_edit_profile and create_interactive in the client repository.
