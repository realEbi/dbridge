# Review Notes

## Consistency Check

No contradictions found across documents. The following cross-references were verified:

- Connection ID format (`md5--name`) is consistent across `interfaces.md`, `data_models.md`, `components.md`, and `architecture.md`.
- Cache TTL default (120s) matches `config.py` `expiration_seconds` field and is consistent across `components.md`, `codebase_info.md`, and `index.md`.
- Port 3695 is consistent across `architecture.md`, `codebase_info.md`, and `index.md`.
- `INSTALLED_ADAPTERS = ["sqlite", "duckdb"]` is consistent with `dependencies.md` (core vs optional split).
- `is_single_connection()` behavior is consistent between `architecture.md`, `components.md`, and `workflows.md`.

---

## Completeness Gaps

### 1. MySQL / PostgreSQL / Snowflake adapter internals not fully documented
**Severity**: Low  
**Reason**: These files were not read in full during analysis (only the overview was used). The `components.md` adapter sections for MySQL, PostgreSQL, and Snowflake contain accurate but minimal detail compared to the SQLite and DuckDB sections.  
**Recommendation**: Read `mysql.py`, `postgres.py`, `snowflake.py` and expand the per-adapter notes in `components.md`.

### 2. `output_formatters/` and `exceptions/` are empty
**Severity**: Informational  
**Reason**: Both packages exist but contain only empty `__init__.py` files. They are documented as "Reserved" in `codebase_info.md`.  
**Recommendation**: No action needed until these are populated.

### 3. `run_query` multi-statement behavior is undocumented
**Severity**: Medium  
**Reason**: The README mentions "Run a sql file with multiple statements" as a feature, and `extract_table.py` uses `sqlparse.split()`. However, it is unclear whether `run_query` itself handles multiple statements or delegates that to the adapter. The DuckDB adapter's `run_query` uses `_execute_query` which calls `con.execute()` — DuckDB's `execute()` only runs the last statement.  
**Recommendation**: Clarify multi-statement behavior per adapter and document in `interfaces.md` under `POST /run_query`.

### 4. Optional adapter import behavior is a potential runtime hazard
**Severity**: Medium  
**Reason**: `server/config.py` imports `MySqlAdapter`, `PostgresAdapter`, and `SnowflakeAdapter` at the top level. If the optional packages are not installed, the server will fail to start entirely — even if the user only wants SQLite/DuckDB.  
**Recommendation**: Document this clearly in `dependencies.md` (done) and consider lazy imports as a future improvement.

### 5. No authentication or authorization documented
**Severity**: Informational  
**Reason**: The API has no auth layer. This is by design (local tool), but worth noting for users exposing the server on a network.  
**Recommendation**: Add a security note to `interfaces.md` or `architecture.md`.

### 6. `test.env` file contents not documented
**Severity**: Low  
**Reason**: A `test.env` file exists at the repo root but was not read. It likely sets env vars for local test runs.  
**Recommendation**: Document its purpose in `codebase_info.md`.

### 7. `tests/server.py` is not a standard pytest file
**Severity**: Low  
**Reason**: The file is named `server.py` not `server_test.py` or `test_server.py`. It may not be picked up by pytest's default discovery. Contains `test_add_connection`.  
**Recommendation**: Verify pytest discovery and rename if needed.

---

## Language Support Limitations

The codebase is 100% Python. No documentation gaps from language support limitations.

---

## Recommendations Summary

| Priority | Action |
|---|---|
| Medium | Clarify and document multi-statement SQL behavior per adapter |
| Medium | Document the optional-import startup failure risk more prominently |
| Low | Read and expand MySQL/PostgreSQL/Snowflake adapter details |
| Low | Document `test.env` contents |
| Low | Verify `tests/server.py` pytest discovery |
| Informational | Add security/auth note for network-exposed deployments |
