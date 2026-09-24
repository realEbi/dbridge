# 059 - Preserve Profiles after interrupted file writes

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Profile storage inspection during `rename-profiles-atomically`; its design explicitly defers crash-safe file replacement.

## Problem / opportunity

`save_profile` and a successful `delete_profile` in
[`config/profiles.py`](../../src/dbridge/config/profiles.py) serialize the updated
data, then call `path.write_bytes` on `connections.toml`. This opens the existing
file for an in-place rewrite. A process interruption or write failure after
truncation can leave the file empty or partially written and lose persisted
Profiles. This is a code-inspection finding; an interrupted write has not been
reproduced as part of the rename change.

Profile renames use a single read-modify-write and reject missing sources and
name collisions before writing. That prevents the logical partial update of
separate save/delete requests, but does not make the underlying file replacement
crash-safe. Every save and successful delete shares this limitation.

## Desired outcome

Preserve a complete, readable Profile file if writing a replacement fails or the
process stops during persistence. Define the supported crash and durability
guarantees for the server's Profile operations before selecting an implementation.

## Notes and references

Consider writing a temporary file beside `connections.toml` and atomically
replacing the destination only after the complete serialization is written.
Decide how permissions, temporary-file cleanup, and filesystem synchronization
affect the promised guarantees. Concurrent changes by other processes are a
separate coordination question, not solved by file replacement alone.

Use isolated files and failure injection when this work is selected. Existing
storage behavior is covered in
[`tests/config/test_profiles.py`](../../tests/config/test_profiles.py); see
[current architecture](../architecture.md#sessions-and-profiles) and
[001](001-profile-rename.md) for the distinct rename outcome.
