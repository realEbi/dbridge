# 01 — Land the client migration + delete the REST island

Status: ready-for-agent
Repo: `dbridge.nvim`

## Parent

`.scratch/phase-2-client-hardening/PRD.md`

## What to build

Get the finished-but-uncommitted stdio rewrite safely into git, then remove the
dead REST code it replaced. **This work is currently untracked and at risk —
do this first.**

- Commit the new stdio modules: `client.lua`, `explorer.lua`, `editor.lua`,
  `results.lua`, `profiles.lua`, plus the rewritten `init.lua`, `cmp.lua`,
  `plugin/dbridge.lua`, the `Makefile`, `scripts/minimal_init.lua`, and
  `tests/`.
- Add `deps/` to `.gitignore` — `deps/mini.nvim` is a cloned dependency the
  Makefile fetches, not source.
- Delete the orphaned REST island: `api.lua`, `config.lua`, `dbconnection.lua`,
  `dbexplorer.lua`, `node_utils.lua`, `query_editor.lua`, `query_result.lua`,
  `file_utils.lua`, `sql_extractor.lua`, `help.lua`, `cmp_format.lua`.
  Verify with a `require` grep that nothing reachable references them first.
- `config.lua` ran `mkdir` and shelled out to `python -c 'import dbridge'` at
  require-time. Confirm nothing depends on those side effects before deleting.
- Make the server command usable: the default `server_cmd` is
  `{"python", "-m", "dbridge.server"}`, which will not resolve inside a
  uv-managed install. Document the `setup({ server_cmd = ... })` override in
  the README and pick a default that fails with a clear message.
- Rewrite `README.md`/`AGENTS.md` for the stdio architecture (they still
  describe the REST server and `serverUrl`).

## Acceptance criteria

- [ ] Working tree is clean; `git log` shows the migration
- [ ] No file under `lua/` requires a deleted module (grep for `require("dbridge.`)
- [ ] `:Dbridge` opens the three-panel layout against a running server
- [ ] `deps/` is gitignored and `make test` still bootstraps it
- [ ] README documents `server_cmd` and no longer mentions `serverUrl` or curl

## Blocked by

Nothing — this is the entry point for the phase.
