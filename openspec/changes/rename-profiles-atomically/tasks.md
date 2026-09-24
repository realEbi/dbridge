## 1. Storage

- [ ] 1.1 Add `previous_name` to `config/profiles.save_profile` and a `ProfileExistsError`, deciding missing-source and name-collision failures before a single write and keeping the renamed Profile's position (design D2); verify with `tests/config/test_profiles.py` tests for rename, rename with a changed config, collision, missing source, `previous_name == name` upsert, untouched siblings, byte-identical files after each failure, and preserved order

## 2. Protocol

- [ ] 2.1 Add `PROFILE_ALREADY_EXISTS = -32007`, pass `previous_name` through the dispatcher and Engine, validate it as a nonempty string when present (D3, D4), and map `ProfileExistsError`; verify with `tests/protocol/test_handlers.py` that each spec failure returns its code and that a request without `previous_name` still upserts
- [ ] 2.2 Verify with a `tests/core/test_engine.py` test that a Session connected from a Profile keeps executing after that Profile is renamed and its config edited

## 3. Documentation and backlog

- [ ] 3.1 Update the README Profiles section and RPC table to describe `previous_name`, and add `PROFILE_ALREADY_EXISTS` to the error-code table; verify both tables against `protocol/errors.py`
- [ ] 3.2 Update `docs/architecture.md` (Sessions and Profiles) to say rename is a single write and does not affect live Sessions; check whether the `CONTEXT.md` Profile entry needs rename wording and update it only if it would otherwise be incomplete
- [ ] 3.3 Record a new backlog item for non-atomic `connections.toml` writes (evidence: `path.write_bytes` rewrites the file in place for every save and delete), using the next unused ID and adding it to the backlog index

## 4. Verification and closure

- [ ] 4.1 Run `make check` and `uv run --group test pytest --cov` in the worktree; verify that types and lint are clean and coverage stays at or above 85%
- [ ] 4.2 Run the linked dbridge.nvim `rename-profiles-atomically` tests with `DBRIDGE_SERVER_CMD` pointing at this worktree's server; record the server revision and result in that change
- [ ] 4.3 Validate with `openspec validate rename-profiles-atomically --strict`, sync the `profile-management` spec, archive the change, mark backlog 001 done with links to both archived changes, and update the milestone 1 roadmap text; mark milestone 1 complete only if 005 has also shipped
