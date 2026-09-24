# 058 - Reject negative query row caps

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Reproduced during [bound-result-fetch](../../openspec/changes/archive/2026-09-24-bound-result-fetch/proposal.md); the Settings validation defect predates bounded fetching.

## Problem / opportunity

`Settings(max_rows=-5)` succeeds because `max_rows` has no lower-bound validation.
The executor compares the number of fetched rows with the negative cap and then
slices `rows[:-5]`. This uses Python's negative-index semantics rather than a
meaningful row cap, and emits the misleading warning
`result truncated to -5 rows`.

Reproduction from the repository root, using an isolated in-memory database:

```sh
uv run python - <<'PY'
import asyncio
from dbridge.adapters.sqlite import SqliteAdapter
from dbridge.config.settings import Settings
from dbridge.core.executor import execute
from dbridge.core.session import Session

async def main():
    settings = Settings(max_rows=-5)
    adapter = SqliteAdapter({"uri": ":memory:"})
    await adapter.connect()
    try:
        result = await execute(
            Session(id="negative-cap-repro", adapter=adapter),
            "SELECT 42",
            settings.max_rows,
        )
        print(settings.max_rows, result.rows, result.row_count, result.warnings)
    finally:
        await adapter.disconnect()

asyncio.run(main())
PY
```

Observed output: `-5 [] 0 ['result truncated to -5 rows']`.
The bounded-fetch executor requests one row for a negative cap using
`max(max_rows, 0) + 1`, so the invalid setting cannot cause an unbounded driver
fetch. This guard does not validate the setting or correct the negative slice.
An executor probe with ten canned rows confirms that `max_rows=-5` retains the
first five rows and emits the same warning.

## Desired outcome

Reject negative `max_rows` during Settings validation, including values loaded
from `dbridge_max_rows`, with a clear configuration error. Define and preserve
the intended treatment of zero and the existing positive-cap behavior when this
work is selected.

## Notes and references

Inspect [Settings](../../src/dbridge/config/settings.py) and the
[executor](../../src/dbridge/core/executor.py). Configuration validation remains
outside [056](056-bounded-result-fetch.md); do not remove its positive fetch-limit
guard when addressing this defect. Add behavior tests for explicit and
environment-provided settings as part of the selected change.
