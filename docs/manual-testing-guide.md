# dbridge Manual Testing Guide

Use `make manual-prepare` to create reusable SQLite and DuckDB databases for
interactive testing through your client. The sample generator owns database
setup; `make test` runs the automated server and stdio RPC checks.

## Prepare for interactive testing

With Python 3.11+, uv, and Make installed, run from the repository root:

```console
make manual-prepare
```

This uses `uv run` to sync project dependencies and runs the existing
[sample generator](../scripts/make_sample_db.py) using
[examples/sample.sql](../examples/sample.sql). It leaves these Git-ignored files
available after the command exits:

| Adapter | Database file |
|---|---|
| `sqlite` | `examples/sample.db` |
| `duckdb` | `examples/sample.duckdb` |

Both databases contain 8 customers, 10 products, 10 orders, and 220 order items.
The fixture includes foreign keys, NULL and empty-string values, and enough rows
to demonstrate the default 100-row response cap.

**Running `make manual-prepare` again replaces both databases and discards any
changes you made to them.** Disconnect Sessions using these files before
rebuilding. Preparation does not start the server or create or modify Profiles.

Configure your client to launch `uv run python -m dbridge.server` from the
repository root. Connect with the adapter and the database's absolute path. For
example, these are the parameters for `dbridge/connect` (replace the path):

```json
{
  "adapter": "sqlite",
  "config": {"uri": "/absolute/path/to/dbridge/examples/sample.db"}
}
```

For DuckDB, use `"adapter": "duckdb"` and the absolute path to `sample.duckdb`.
To persist a named Profile, use your client's Profile UI or `dbridge/saveProfile`
with the same adapter/config and a name; Profile management belongs to the RPCs.

Without Make, the equivalent preparation command is
`uv run python scripts/make_sample_db.py`.

## Interactive checks

Connect to each sample database and try these checks in your client:

| Check | Expected result |
|---|---|
| Browse tables | `customers`, `products`, `orders`, and `order_items` appear. |
| Run `SELECT id, name, email FROM customers ORDER BY id` | Eight rows; columns remain in that order. Chidi's email is NULL and Fatima's is an empty string. |
| Run `SELECT * FROM order_items ORDER BY id` | With the default 100-row cap, 100 rows and a truncation warning. |
| Request completion after `SELECT * FROM ` | Tables in the selected Scope Path are offered with simple labels; inserted text is a fully qualified, quoted identifier that executes unedited. |
| In `SELECT p.name, p.category FROM products p LIMIT 100`, put the cursor after either `p.` and request completion | `id`, `sku`, `name`, `category`, `price`, and `discontinued` are offered. Selecting `name` leaves a single `p.name`. Typing `p.na` narrows the suggestions to `name`. |
| Enter `products` in the updated Neovim explorer | Generated SQL includes `"main"."products"` for SQLite or the full quoted catalog/schema/table for DuckDB, and shows the selected table. |
| In `SELECT id, name FROM products`, request completion after the comma and space, before `name` | All six product columns are offered. Typing `na` at an empty target filters to `name`; repeat on a new line after the comma. |
| Request completion after `SELECT ` with no FROM clause | Dialect keywords such as `FROM` are offered; unrelated table columns are not. |
| In Neovim, create a TEMP table, then refresh its Profile with `R` | The same Session remains active and the TEMP table is still queryable; the editor shows the active Profile, Adapter, and Session. |
| Put two SELECT statements in the query editor and use `<leader>s` inside the second | Only the second statement runs. `<leader>r` remains the whole-buffer/visual action. |
| Inspect `orders` metadata | SQLite reports its primary key and the foreign key to `customers`. DuckDB constraint extraction remains unimplemented. |

Use matching server and client checkouts: the explicit Scope Path protocol has no
legacy fallback. Connect reports `levels`, `default_path`, and `dialect`. Metadata
and completion requests send `path`; table lookup also sends literal `name`.
For completion in the middle of SQL, the client must send the full statement and
the cursor's UTF-8 byte offset. After updating the server code, restart the
client's server process and reconnect; confirm it launches this checkout rather
than an older installed package. If the direct server suggestions work but no
menu opens after `.`, confirm the client source has dot triggering enabled.
The companion [dbridge.nvim completion source](https://github.com/realEbi/dbridge.nvim/blob/dbridge-2.0/README.md#autocompletion)
automatically requests suggestions on `.` when configured with nvim-cmp; use both
updated repositories, restart Neovim, and reconnect the Profile for this check.
The server supports physical-table qualifiers and unqualified target expressions
in the current SELECT. CTE/derived columns and outer correlated references remain
deferred; a SELECT with no resolvable physical source falls back to keywords.

To check literal names on the reusable samples, run
`CREATE TABLE "order.items" (label TEXT)` and
`INSERT INTO "order.items" VALUES ('selected literal table')` as separate queries.
Refresh the explorer and enter that table: the generated identifier must keep
`"order.items"` as one component and the result must contain the inserted label.
Run `DROP TABLE "order.items"` and refresh afterward, or reset the samples with
`make manual-prepare` after disconnecting. Metadata errors must be shown without
executing a guessed bare-name query. Both repositories must use the Scope Path contract; old `fqn`, `database`, and
`schema` request fields are rejected.

## Attached-container checks

Use an isolated in-memory Profile for each Adapter, so these checks do not change
sample files. Execute each statement separately in the same live Session:

```sql
ATTACH ':memory:' AS side;
CREATE TABLE main.shipments AS SELECT 1 AS marker;
CREATE TABLE side.main.shipments AS SELECT 2 AS marker;
```

The statements above use DuckDB syntax. Refresh the Profile with `R`, then browse
both the original catalog's `main` schema and `side` → `main`. Select each schema
and open a query buffer, request completion after `SELECT * FROM `, and accept
`shipments`. Execute the inserted identifier without editing: the original catalog
returns `1`, and `side` returns `2`. The table appears once per request; completion
keeps its simple label while inserting all quoted path components. Keep both query
buffers open and repeat completion in each to verify their Scope Paths stay separate.
Selecting metadata scope does not issue `USE` or change SQL execution defaults.

For SQLite, use these statements instead:

```sql
ATTACH ':memory:' AS side;
CREATE TABLE main.shipments AS SELECT 1 AS marker;
CREATE TABLE side.shipments AS SELECT 2 AS marker;
```

Refresh and expand the Profile. `main` and `side` each lead directly to tables:
there is one container tier and no `main/main` node. Browse and complete `shipments`
in each namespace, then execute the inserted text unedited and confirm markers
`1` and `2`. Container listings retain engine-internal entries and mark them;
clients may use the marker for presentation.

Refresh keeps the same Session and re-reads `levels` and `default_path`, while
clearing all cached container/table/column listings. After `ATTACH`, `DETACH`, or
DDL, explicitly refresh to rebuild the browser; automatic invalidation remains
[deferred](backlog/043-ddl-cache-invalidation.md). Disconnect the temporary Profiles
when finished. The companion client suite exercises these flows against a real
server with isolated temporary Profile storage.

Disconnect your Sessions when finished. The sample files remain available for
later use; rerun `make manual-prepare` when you want to reset them. See the
[README](../README.md#json-rpc-methods) for supported RPCs and settings.

## Automated tests

```console
make test
make test-cov
make test PYTEST_ARGS="tests/adapters -q"
```

`make test-cov` enforces the existing 85% coverage floor. Plain `make` or
`make help` lists the available commands. See the
[development guide](development.md) for direct uv commands and additional checks.

The suite includes [stdio subprocess tests](../tests/test_e2e_stdio.py). Use it
for automated protocol checks; no Python harness needs to be copied from this guide.
