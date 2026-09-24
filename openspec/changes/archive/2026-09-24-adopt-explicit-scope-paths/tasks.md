## 1. Scope Path data model and Adapter declaration

- [x] 1.1 Add `ScopePath` and the Scope Level declaration to `adapters/base.py`, and verify a unit test asserts a level carries a stable name and a display label and that a path of nonempty literal strings round-trips unchanged
- [x] 1.2 Replace `TableRef.database`/`.schema` with a `path` tuple and `TableSchema.database`/`.schema` with a reported `scope` path, and verify `TableRef` stays hashable and usable as a cache key with a path component containing a dot
- [x] 1.3 Add the abstract hierarchy declaration and default-Scope-Path methods to `DBAdapter`, removing nothing else from the interface, and verify `mypy` via `make check` passes with both shipped Adapters implementing the declarations

## 2. Adapter implementations

- [x] 2.1 Declare one Scope Level in the SQLite Adapter, derive its default Scope Path from `PRAGMA database_list`, and rework `_namespace` into the single path component; verify a test asserts one declared level and that `TableSchema.scope` has exactly one component for a table in `main`
- [x] 2.2 Scope SQLite listings and metadata by Scope Path and verify a test with an attached namespace asserts listings stay inside the requested path and that the reported path and `sql_identifier` have the same container arity
- [x] 2.3 Declare two Scope Levels in the DuckDB Adapter, derive its default Scope Path from `current_database()`/`current_schema()`, and verify a test asserts catalog-before-schema order and a two-component default
- [x] 2.4 Require a full Scope Path in DuckDB listings and metadata, removing the fallback to the Adapter's current catalog/schema, and verify a test with two attached catalogs asserts each path returns only its own catalog's tables and that the previous `['orders','orders']` duplication is gone
- [x] 2.5 Mark engine-internal containers in both Adapters' database and schema listings, and verify a test asserts DuckDB's `system`/`temp`, `information_schema`, and `pg_catalog` are returned and marked while user catalogs are unmarked
- [x] 2.6 Return name plus `sql_identifier` per entry from `list_tables` in both Adapters, and verify a test executes a statement built from a returned identifier and reads that exact table, including for a name with a space, a keyword, and an embedded double quote

## 3. Registry and Engine

- [x] 3.1 Key `SchemaRegistry` on full Scope Path tuples and move database and schema listings into it, and verify a test asserts two paths differing only in their first component never return each other's cached result
- [x] 3.2 Make `refresh()` clear every cached introspection result, and verify a test asserts a newly created schema appears in the next schema listing after refresh without waiting for TTL expiry
- [x] 3.3 Require a Scope Path in `Engine.list_schemas`, `list_tables`, `get_table_schema`, `get_erd`, and `complete`, dropping the `fqn` parameter, and verify existing engine tests updated to pass paths still pass
- [x] 3.4 Return the hierarchy declaration, default Scope Path, and dialect from `Engine.connect`, and return the declaration from `refresh_schema`, and verify tests assert both shapes for a SQLite and a DuckDB Session
- [x] 3.5 Delete `Session.active_database` and `active_schema` and replace `tests/core/test_session.py`'s always-`None` assertion with one asserting the Session exposes no scope state

## 4. Protocol surface

- [x] 4.1 Require and validate a Scope Path in the `listSchemas`, `listTables`, `getTableSchema`, `getERD`, and `complete` handlers, and verify tests assert `INVALID_REQUEST` for a missing path, a non-string component, an empty-string component, and an arity the Adapter did not declare — each without terminating the server
- [x] 4.2 Replace `getTableSchema`'s `fqn` input with Scope Path plus table name, and verify a test asserts a path component containing a literal dot is preserved whole and does not select a table in a differently named container
- [x] 4.3 Keep `listDatabases` free of a Scope Path and verify a test asserts it enumerates the first Scope Level and rejects a supplied path
- [x] 4.4 Verify the end-to-end stdio flow in `tests/test_e2e_stdio.py` covers connect (levels, default path, dialect), a scoped listing, a scoped table lookup, and refresh returning the declaration, over a real subprocess with an isolated temporary database

## 5. Completion

- [x] 5.1 Thread the request's Scope Path through `Engine.complete` into table listing and column lookup, and verify a test with two attached DuckDB catalogs asserts a `FROM ` completion offers the table name once, for the requested catalog only
- [x] 5.2 Resolve a partly qualified physical source's missing leading components from the request's Scope Path instead of the Adapter's current catalog/schema, and verify a test asserts `sales.products` resolves inside the requested catalog when a same-named table exists in another catalog's `sales` schema
- [x] 5.3 Insert the executable qualified `sql_identifier` for every table suggestion while retaining bare table labels and unchanged column insertion text, and verify a test executes the inserted text unedited and reads the intended table — the case that previously failed with `Catalog Error: Table with name shipments does not exist!`
- [x] 5.4 Verify SELECT-scope isolation is unchanged: existing nested-scope, sibling-SELECT, UNION-branch, CTE/derived, literal/comment, and bare-`SELECT`-keyword tests still pass unmodified except for the added Scope Path argument

## 6. Documentation

- [x] 6.1 Add **Scope Path** and **Scope Level** to `CONTEXT.md`, noting the deliberate distinction from sqlglot's SELECT `Scope` and the `_Avoid_` terms, and verify no existing glossary entry still describes a fixed database/schema pair
- [x] 6.2 Update the README JSON-RPC method table for all six changed methods, the new connect and refresh response shapes, and the removal of `fqn`, and verify every documented param matches the dispatcher
- [x] 6.3 Update `docs/architecture.md` — *Sessions and Profiles* (no scope state), *Schema browsing and completion* (Scope Paths, listings inside the cache, refresh returning the declaration, marked internal containers), and the `main/main` note — and verify no claim describes removed behavior as current
- [x] 6.4 Update `docs/roadmap.md` milestone 1 to record hierarchy, cache coverage, and dialect as shipped while the milestone stays open on 001 and 005, without marking the milestone complete
- [x] 6.5 Mark backlog 003, 004, and 008 done with resolutions and archive links; close 048 as dropped recording that server-held scope was rejected rather than deferred; add the hierarchy-staleness consequence to 043; and verify each item keeps a resolution useful to anyone following its ID

## 7. Cross-repository integration

- [x] 7.1 Open the linked `dbridge.nvim` change in that repository (owner: `dbridge.nvim`) covering reading levels/default path/dialect from connect, sending a Scope Path per metadata call, re-reading the declaration on refresh, and dropping `.database`/`.schema`; verify this change's proposal links it, that the client change lives in `dbridge.nvim/openspec/`, and that client edits follow that repository's AGENTS.md and remain separate, with commits only on user authorization
- [x] 7.2 Verify the shared flow against a DuckDB Session with a second catalog attached: browse both catalogs, complete in each, and execute a completed identifier unedited — following `docs/manual-testing-guide.md`, updating it if the demonstrated steps change
- [x] 7.3 Verify the shared flow against a SQLite Session with an attached namespace, confirming the client tree renders one container tier and `main/main` is gone

## 8. Verification

- [x] 8.1 Run `make check` and confirm lint and type checks pass with no new suppressions
- [x] 8.2 Run `uv run --group test pytest --cov` and confirm the suite passes with `src/dbridge` coverage at or above 85%, restoring coverage with behavior-asserting tests rather than lowering the gate
- [x] 8.3 Run `openspec validate adopt-explicit-scope-paths --strict` and confirm the delta specs, including the removed `table-identifiers` requirement, validate before synchronizing
- [x] 8.4 Record any unrelated defect or dead code found while implementing as a new `docs/backlog/` item with evidence and owning repository, rather than fixing it here
