## 1. Storage

- [x] 1.1 Add `previous_name` to `config/profiles.save_profile` and a `ProfileExistsError`, deciding missing-source and name-collision failures before a single write and keeping the renamed Profile's position (design D2); verify with `tests/config/test_profiles.py` tests for rename, rename with a changed config, collision, missing source, `previous_name == name` upsert, untouched siblings, byte-identical files after each failure, and preserved order

## 2. Protocol

- [x] 2.1 Add `PROFILE_ALREADY_EXISTS = -32007`, pass `previous_name` through the dispatcher and Engine, validate it as a nonempty string when present (D3, D4), and map `ProfileExistsError`; verify with `tests/protocol/test_handlers.py` that each spec failure returns its code and that a request without `previous_name` still upserts
- [x] 2.2 Verify with a `tests/core/test_engine.py` test that a Session connected from a Profile keeps executing after that Profile is renamed and its config edited

## 3. Documentation and backlog

- [x] 3.1 Update the README Profiles section and RPC table to describe `previous_name`, and add `PROFILE_ALREADY_EXISTS` to the error-code table; verify both tables against `protocol/errors.py`
- [x] 3.2 Update `docs/architecture.md` (Sessions and Profiles) to say rename is a single write and does not affect live Sessions; check whether the `CONTEXT.md` Profile entry needs rename wording and update it only if it would otherwise be incomplete
- [x] 3.3 Record a new backlog item for non-atomic `connections.toml` writes (evidence: `path.write_bytes` rewrites the file in place for every save and delete), using the next unused ID and adding it to the backlog index

## 4. Verification and closure

- [x] 4.1 Run `make check` and `uv run --group test pytest --cov` in the worktree; verify that types and lint are clean and coverage stays at or above 85%
- [x] 4.2 Run the linked dbridge.nvim `rename-profiles-atomically` tests with `DBRIDGE_SERVER_CMD` pointing at this worktree's server; record the server revision and result in that change
- [x] 4.3 Validate with `openspec validate rename-profiles-atomically --strict`, sync the `profile-management` spec, archive the change, mark backlog 001 done with links to both archived changes, and update the milestone 1 roadmap text; mark milestone 1 complete only if 005 has also shipped

## Verification record

- Python 3.12.12: focused storage, Dispatcher, and Engine checks passed (173 tests).
- `make check`: mypy passed over 55 source files; Ruff passed.
- `uv run --group test pytest --cov`: 559 passed; coverage 96.59% (85% floor).
  Two existing NumPy deprecation warnings came from DuckDB cancellation tests.
- README RPC/error tables, the JSON example, and documentation links were checked;
  `CONTEXT.md` already defines Profile/Session separation and needed no change.
- The old save-then-delete suggestion in backlog 001 is superseded by the accepted
  single-request rename. In-place file-write crash safety remains backlog 059;
  coordinating separate processes is also outside this change.
- Paired Neovim Client: full `make test` passed 184 cases against this server
  worktree; 30 Lua files passed Neovim `loadfile` syntax checks. The Client has no
  configured static/style linter. Its archived change records the exact server
  commit and invocation. Both SQLite and DuckDB retain Session data, selected
  scope, and query execution after rename; collisions and missing sources keep
  the node unchanged.
- Strict OpenSpec change/spec validation and `git diff --check` passed. Verified
  `profile-management` requirements were synchronized before archive.
