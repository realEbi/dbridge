## 1. Key model

- [x] 1.1 In `adapters/base.py`, add `PrimaryKey`, replace `ForeignKey` with the constraint form, and replace `TableSchema.primary_keys` with `primary_key: PrimaryKey | None` (design D1); make the Engine serialize `referenced_path` as a list; verify that `make check` passes and a `tests/core` test of `get_table_schema` serialization shows `primary_key` and list-valued `referenced_path` in the reply dict

## 2. SQLite

- [x] 2.1 Order primary-key columns by the `pk` ordinal with a null name (D4); verify with `tests/adapters/test_sqlite.py` that `PRIMARY KEY (b, a)` reports `["b", "a"]` and `id INTEGER PRIMARY KEY` reports `{name: None, columns: ["id"]}`
- [x] 2.2 Group foreign keys by pragma `id`, order columns by `seq`, set `referenced_path` to the table's path, and resolve a NULL `to` to the parent's primary key in the same namespace (D5); verify SQLite tests for one composite key, two composite keys to one parent, the shorthand `REFERENCES r`, a missing parent with empty `referenced_columns`, and a key inside an attached namespace

## 3. DuckDB

- [x] 3.1 Read catalog-table keys from `duckdb_constraints()` on the metadata cursor, ordered by `constraint_index` (D2); verify DuckDB tests for an out-of-order composite primary key with DuckDB's name, a composite foreign key, and keys inside a non-default schema and an attached catalog whose `referenced_path` retrieves the parent
- [x] 3.2 Capture `temp` constraints in the query-connection snapshot (D3); verify a DuckDB test in which a temporary parent and child report their keys under `("temp", "main")`, and that existing temporary-table and Lane tests still pass
- [x] 3.3 Verify on both Adapters that a `UNIQUE (a, b)` table reports `primary_key` None and that an unknown table reports None and `[]`

## 4. Protocol behavior

- [x] 4.1 Add a stdio end-to-end test that `dbridge/getTableSchema` returns the `table-keys` shape for a SQLite composite key, omits `primary_keys`, and reports a recreated table's keys after `dbridge/refreshSchema`; verify it passes against a spawned server with isolated configuration

## 5. Documentation and backlog

- [x] 5.1 Update the README `getTableSchema` row and add a short key-shape example beside the existing `getTableSchema` example; verify that `grep -n primary_keys README.md` finds nothing
- [x] 5.2 Update `docs/architecture.md` (metadata section) to describe both Adapters' key reporting and SQLite's null names; update the manual testing guide's `orders` metadata row to expect DuckDB keys and run that manual check against the prepared DuckDB sample
- [x] 5.3 Update backlog 011's note to say constraint metadata is available through `table-keys`, and record any unrelated finding as a new backlog item

## 6. Verification and closure

- [x] 6.1 Run `make check` and `uv run --group test pytest --cov` in the worktree; verify that types and lint are clean and coverage stays at or above 85%
- [x] 6.2 Run the linked dbridge.nvim `adopt-table-key-constraints` tests with `DBRIDGE_SERVER_CMD` pointing at this worktree's server; record the server revision and result in that change
- [x] 6.3 Validate with `openspec validate extract-table-key-constraints --strict`, sync the `table-keys` spec, archive the change, mark backlog 005 done with a link to the archive, and update the milestone 1 roadmap text to say DuckDB constraints are implemented and reconcile its remaining dependencies with the already completed Profile rename change (001)

## Verification record

Verified on 2026-09-24 with Python 3.12.12 and DuckDB 1.1.3:

- `make check`: mypy checked 55 source files; Ruff passed.
- `uv run --group test pytest --cov`: 582 passed; 96.68% coverage (85% gate).
  The two existing NumPy deprecation warnings from the cancellation fixture
  remain non-failing.
- `make manual-prepare`, followed by isolated stdio requests to each prepared
  sample: `orders` reported primary key `id` and the `customer_id → customers.id`
  foreign key. Both referenced paths retrieved the parent; SQLite names were
  null and DuckDB names were `orders_id_pkey` and `orders_customer_id_id_fkey`.
- Paired dbridge.nvim transport suite: 12 passed. Full `make test`: 184 passed,
  zero notes. Its updated assertion fails against the pre-change server as
  expected; the client archive records server revision provenance.
- Strict change/spec validation and whitespace checks passed. The new
  `table-keys` main spec matches all four verified delta requirements.
- Independent implementation review found no actionable issues. Original
  checkouts and their untracked planning files were preserved.

Profile rename (001) shipped before this implementation. The proposal and
roadmap now reflect that completed dependency while retaining deferred completion
and client presentation work in their owning backlog items.
