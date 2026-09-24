## Context

See proposal.md for motivation and specs/profile-management/spec.md for the contract.

`config/profiles.py` reads `connections.toml`, changes a dict, and rewrites the file
with `path.write_bytes` for each save or delete. `ProfileNotFoundError` lives there
and the dispatcher maps it to `PROFILE_NOT_FOUND`. The Engine's `save_profile` passes
`name`, `adapter`, and `config` straight through. Profile file operations run
directly on the event loop (see current architecture); there is no lock because the
loop runs one Profile operation at a time.

The Neovim Client's edit flow (`explorer.lua` `handle_edit_profile`) calls
`saveProfile` with the new name only. Its explorer tracks Sessions by tree node id,
not by Profile name.

## Goals / Non-Goals

**Goals:**

- A rename is one read-modify-write of the Profile file, with every failure decided
  before the write.
- Existing `saveProfile` callers keep their behavior.

**Non-Goals:**

- No crash-safe file replacement (write to a temporary file, then rename). The
  current in-place write applies to every Profile operation and is recorded as a
  separate backlog item.
- No protection against another process editing `connections.toml` concurrently.
- No Profile name validation beyond the new `previous_name` check.

## Decisions

### D1. An optional `previous_name` on `saveProfile`, not a new RPC

An edit replaces one Profile definition with another, possibly under a new name.
`saveProfile` with `previous_name` expresses that as one request. A separate
`renameProfile {from, to}` would still need a second request when the config also
changes, which brings back the partial-failure window this change removes.

### D2. Storage owns the rename

`save_profile(name, adapter, config, path=None, previous_name=None)` reads the file
once, raises `ProfileNotFoundError` if `previous_name` is absent from it, raises a new
`ProfileExistsError` if `name` is already present, and otherwise builds the new
`connections` table and writes once. Checking inside the same read as the write
keeps the decision and the change together. The rename keeps the Profile at its
original position in the table, so `listProfiles` order does not jump after an edit.

### D3. `PROFILE_ALREADY_EXISTS` is a new error code

`ProfileExistsError` maps to `PROFILE_ALREADY_EXISTS` (-32007), the next unused
dbridge code. A client can tell a collision from an invalid request without parsing
the message. `INVALID_REQUEST` was considered, but the request is well formed; the
conflict is with stored state.

### D4. The dispatcher validates `previous_name`

A present `previous_name` that is not a nonempty string raises `InvalidRequestError`
before storage is touched, matching how `getTableSchema` validates `name`.

## Risks / Trade-offs

- [A client uses `previous_name` against an older server] → The older server ignores
  the parameter and upserts, which reproduces the duplicate. The client change states
  that it requires this server; both merge together as a pair.
- [Interrupted write corrupts `connections.toml`] → Pre-existing for all Profile
  writes; tracked as a separate backlog item rather than widened into this change.

## Migration Plan

Merge the server change first, then the linked client change. Rollback reverts both;
Profile files written by either version stay readable by the other.
