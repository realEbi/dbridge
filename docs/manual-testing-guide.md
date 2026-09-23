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
| Request completion after `SELECT * FROM ` | Sample table names are offered. |
| Inspect `orders` metadata | SQLite reports its primary key and the foreign key to `customers`. DuckDB constraint extraction remains unimplemented. |

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
