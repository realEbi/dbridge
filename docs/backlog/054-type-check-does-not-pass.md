# 054 - Make the type checker pass

- Repo: dbridge
- Status: done
- Change: [restore-server-quality-checks](../../openspec/changes/archive/2026-09-23-restore-server-quality-checks/)
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Resolution

The full documented mypy command now reports zero errors in 46 source files.
Only unregistered `adapters/_parked/` modules are excluded from recursive discovery;
the SQLite URI is narrowed before assignment and the broken logger cache is gone.
`make check` runs types and lint, and both checks now run within the unchanged
Python 3.11/3.12 CI matrix alongside the 85% coverage gate. Adapter ports remain
owned by 019/020/021; no optional driver was added.

## Original problem / opportunity

`uv run --group types mypy src/dbridge tests` reports 21 errors in 5 files on
revision `e16c443`. [docs/development.md](../development.md) lists the command as
a standard check, but it had never been clean at that revision, so its output carried no signal:
a new error is indistinguishable from the existing noise.

The errors fall into three groups:

- **Parked adapters (19).** Missing stubs or modules for optional drivers —
  `psycopg2`, `mysql.connector`, `snowflake.connector`, `pandas` — plus imports
  of modules that no longer exist (`dbridge.adapters.interfaces`,
  `dbridge.adapters.capabilities`, `dbridge.adapters._parked.models`) and
  `dbridge.config.NO_COLS_FETCH`. The stale imports mean this code would not run
  even with its drivers installed; it needs porting, not stubs. See
  [019](019-mysql-adapter.md), [020](020-postgres-adapter.md),
  [021](021-snowflake-adapter.md).
- **`logging/__init__.py:5`** — `_loggers` needs a type annotation. Related to
  [051](051-logger-handler-stacking.md); fix both together, since that item may
  delete the dict entirely.
- **`adapters/sqlite.py:39`** — `sqlite3.connect` receives `str | None`.
  `SqliteAdapter.__init__` already raises when `uri` is falsy, so the value is
  non-`None` by construction; the checker cannot see it. Narrowing the attribute
  type resolves it and is a genuine readability improvement.

`tests/` is clean: 0 errors.

## Desired outcome

Decide the intended scope of type checking and get it to zero, so the check can
be trusted and eventually enforced alongside the coverage gate in
[the test workflow](../../.github/workflows/test.yml). Excluding
`adapters/_parked/` from the checker is the pragmatic first step, since porting
those adapters is separately owned work; that alone removes 19 of the 21.

## Notes and references

Run `uv run --group types mypy src/dbridge tests`. Mypy was not added to CI until the recorded findings were fixed. The coverage change deliberately did not fix these:
they are pre-existing and unrelated to test coverage.
