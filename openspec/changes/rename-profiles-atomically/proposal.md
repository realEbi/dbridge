## Why

Editing a Profile's name in the Neovim Client saves a new Profile and leaves the old
one in `connections.toml`, so the explorer shows one entry while the file holds two.
Saving under a name that already exists silently overwrites that other Profile,
because `dbridge/saveProfile` is an upsert. The client cannot fix this alone: saving
the new name and then deleting the old one takes two requests, and a failure between
them still leaves a duplicate. See [backlog 001](../../../docs/backlog/001-profile-rename.md).

## What Changes

- `dbridge/saveProfile` accepts an optional `previous_name`. When it differs from
  `name`, the server replaces the Profile stored under `previous_name` with the new
  definition under `name` in one write to `connections.toml`.
- A rename to a name that another Profile already uses fails with a new error,
  `PROFILE_ALREADY_EXISTS` (-32007), and changes nothing.
- A rename from a `previous_name` that does not exist fails with
  `PROFILE_NOT_FOUND` and changes nothing.
- Without `previous_name`, or when it equals `name`, `saveProfile` stays an upsert.
  This is backward compatible.
- The linked dbridge.nvim change sends `previous_name` from its edit flow and keeps
  the explorer consistent with the result.

## Capabilities

### New Capabilities

- `profile-management`: How `dbridge/saveProfile` creates, updates, and renames a
  Profile, including collision and missing-Profile failures and the guarantee that
  a failed save changes nothing.

### Modified Capabilities

None.

## Impact

**Roadmap and backlog.** Resolves [001](../../../docs/backlog/001-profile-rename.md),
which with [005](../../../docs/backlog/005-duckdb-constraints.md) (planned in
`extract-table-key-constraints`) completes milestone 1 (*Reliable daily use*).
001 is recorded as a client item; this change adds the server as an owner.

**Repositories.** dbridge owns the RPC contract and Profile storage. dbridge.nvim has
a linked change, `rename-profiles-atomically`, which owns the edit flow, explorer
state, and user feedback.

**Protocol compatibility.** Additive. `previous_name` is optional, and existing
requests behave as before. The new error code appears only for requests that use
`previous_name`. An older server ignores `previous_name` and upserts, so the client
change requires this server.

**Sessions.** None. A Session copies its Profile's adapter and config when it
connects, so renaming or editing a Profile does not affect a live Session.

**Code.** `config/profiles.py`, the Engine's `save_profile`, the dispatcher's
parameter handling and error mapping, and `protocol/errors.py`.

**Documentation.** README Profiles section, RPC table, and error-code table;
`CONTEXT.md` if the Profile entry needs to mention renaming; current architecture's
Sessions and Profiles section.
