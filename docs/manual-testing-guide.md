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
| Inspect `orders` metadata | Both engines report `primary_key.columns: ["id"]` and one foreign key pairing `customer_id` with `customers(id)`. Its `referenced_path` locates `customers` in the same namespace (SQLite) or catalog/schema (DuckDB). SQLite key names are null; DuckDB reports engine names. |

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

## Cancel a query and complete while it runs

Use matching server and Neovim client checkouts, including the client's
[`:DbridgeCancel` command](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-24-cancel-outstanding-query).
Start with the DuckDB sample created by `make manual-prepare`:

1. Connect to `examples/sample.duckdb`, select its `main` schema, and open two
   query buffers on the same Session. In one, prepare
   `SELECT p.name, p.category FROM products p LIMIT 100` with the cursor after
   `p.`. Refresh the Profile with `R` before starting the long query so this
   completion must fetch metadata again.
2. In the other buffer, execute this read-only query:

   ```sql
   SELECT sum(hash(i)) FROM range(20000000000) t(i);
   ```

3. While it is running, return to the products buffer and request completion
   after `p.`. All six product columns should arrive before the long query
   finishes. Table browsing on this DuckDB Session should also remain responsive.
4. Run `:DbridgeCancel`. The client should report cancellation as informational,
   without a partial result. Then run `SELECT count(*) AS n FROM products`; the
   same Session should return `10`.
5. Repeat with the SQLite sample. First request products completion to warm its
   cache, then start this query and request the same completion within the default
   60-second cache TTL:

   ```sql
   WITH RECURSIVE n(i) AS (VALUES(1) UNION ALL SELECT i + 1 FROM n)
   SELECT sum(i) FROM n;
   ```

   Cached completion should arrive while the query runs. Uncached SQLite metadata
   waits behind the query because that Adapter has one Lane. Use `:DbridgeCancel`,
   then verify `SELECT count(*) AS n FROM products` still returns `10`.

For a raw DSP client, retain `session_id` and `default_path` from connect, send the
long query as `dbridge/execute` with id `42`, then send `dbridge/complete` with id
`43`, the same Session and path, full products SQL, and `position: 9` (the UTF-8
byte position after the first `p.`). The completion reply should arrive first.
Send `{"jsonrpc":"2.0","method":"$/cancelRequest","params":{"id":42}}`
without an outer id; request `42` should reply with `QUERY_CANCELLED` (-32004),
and the notification should receive no reply. Correlate every response by id,
not arrival order. An already-finished query keeps its normal response if the
cancel arrives too late.

These queries read data only. Disconnect both Sessions when finished. The server
owns cancellation and ordering; the companion client owns its command, progress
state, and cancellation presentation.

## MySQL checks

With Docker and Compose available, run from this checkout:

```console
make mysql-up
make test-mysql
```

The first command starts MySQL 8.4 on `127.0.0.1:33084`, waits for the seeded
1,000,000-row table, and leaves the server running. The second runs the real-server
regressions. Configure your client to launch
`uv run --extra mysql python -m dbridge.server` from this checkout with the default
`dbridge_max_rows=100`. Use temporary Profile storage for disposable test Profiles,
or connect inline with these `dbridge/connect` parameters:

```json
{
  "adapter": "mysql",
  "config": {
    "host": "127.0.0.1",
    "port": 33084,
    "user": "dbridge",
    "password": "dbridge",
    "database": "dbridge_test"
  }
}
```

Retain the returned `session_id`; expect dialect `mysql`, one level named
`database`, and `default_path: ["dbridge_test"]`. For a saved Profile, pass the
same configuration and a name to `dbridge/saveProfile`, then connect by name.
Use the returned Session for each check:

| Check | Expected result |
|---|---|
| Call `dbridge/listDatabases` | Accessible databases include `dbridge_test` and `dbridge_other`; system databases returned to this account are marked internal. |
| Call `dbridge/listTables` with `path: ["dbridge_test"]` | Includes the `million_rows` table and `tiny_view`; identifiers use backticks around the database and table. |
| Call `dbridge/getTableSchema` with that path and `name: "million_rows"` | Columns are `n`, then `payload`; the primary key is named `PRIMARY` with columns `["n"]`. |
| Execute `SELECT * FROM dbridge_test.million_rows` | 100 rows, a truncation warning, and a prompt reply without fetching all one million rows. |
| Execute `SET @marker = 7; CREATE TEMPORARY TABLE manual_marker (n INT)` | Completes normally. The temporary table remains queryable but is absent from browsing. |
| Execute `SELECT n, SLEEP(30) FROM dbridge_test.million_rows LIMIT 2`, then cancel while it runs | `QUERY_CANCELLED` (-32004); no partial result. |
| Execute `SELECT @marker AS marker, COUNT(*) AS n FROM manual_marker` after cancellation | One row `[7, 0]`, confirming the same Session retained its state. |
| Execute `USE dbridge_other`, then call `dbridge/refreshSchema` | The same Session reports `default_path: ["dbridge_other"]`. |

In Neovim use `:DbridgeCancel` for the running query. With a raw DSP client, send
the long execute with id `42`, then send
`{"jsonrpc":"2.0","method":"$/cancelRequest","params":{"id":42}}`
without an outer id. Correlate replies by id; metadata on this MySQL Session can
complete while the query is running. The cancel notification has no reply.

Disconnect the Session, remove any disposable Profile through
`dbridge/deleteProfile`, and run `make mysql-down` when finished. That command
deletes the local test server and its data. For test variables and a different
local port, see [development setup](development.md#local-mysql-verification).
Use direct MySQL connections; the [README's MySQL limits](../README.md#mysql)
cover unsupported proxies, other server versions, and result-value limitations.

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
