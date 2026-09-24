## Context

listTables returns strings, while getTableSchema already returns an object. The client currently joins raw database/schema/table names for metadata and executes a bare table name. SQLite supports schema.table and DuckDB supports catalog.schema.table; their metadata parsing must retain literal punctuation within components.

## Goals / Non-Goals

Provide a server-generated executable identifier for an explicit table identity and keep old callers working. Do not expose dialect names, alter listTables shape, flatten the explorer hierarchy, or change the synchronous execution model in ADR-0001.

## Decisions

Add `sql_identifier: string | null` to TableSchema. Extend getTableSchema with optional `table: {name, database?, schema?}` alongside required legacy fqn. A provided table object takes precedence and its string values are literal components; invalid shapes produce INVALID_REQUEST. The registry cache includes structured identity. Adapters own component quoting (double quotes escaped by doubling), metadata scope, and qualification. SQLite uses its database/schema namespace once; DuckDB uses catalog/schema/table. Structured explicit identity avoids parsing SQL on the client. Legacy fqn keeps its dot-separated interpretation.

DuckDB unscoped legacy requests use the current catalog/schema rather than merging same-named tables. SQLite scoped metadata and listings include attached databases so selected identities remain consistent; its existing database/schema tree levels are preserved. An unknown or unresolvable table has no executable identifier. Metadata errors propagate as query errors.

The client companion [use-server-table-identifiers](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-use-server-table-identifiers) sends both forms so older servers ignore the additive field. It falls back only when a successful response lacks sql_identifier, never on a metadata error or explicit null. Shared tests drive real explorer activation and rendered results.

## Risks / Trade-offs

Waiting for table metadata introduces one asynchronous step before the first generated query. Identity is cached with existing TTL/refresh semantics; concurrent schema changes can still make a previously valid identifier stale. Legacy fqn cannot represent literal dots unambiguously, so new callers should send structured identity. Quoting bounds SQL syntax but does not add authorization.

## Combined-worktree integration correction

Review of SELECT completion together with generated identifiers found that joining
decoded AST components into one dotted string discarded literal boundaries. A
real table named `sales.products` could consequently return columns from a
different products table in the sales namespace (both SQLite and DuckDB); the
generated SQLite identifier reproduced that wrong-source result too.

Scoped qualified and unqualified SELECT completion now passes a frozen TableRef
with literal name, schema, and catalog fields through the existing registry to
the Adapter. Dotted completion detail/sort text is formatted separately and stays
compatible. The legacy string metadata API keeps its previous interpretation;
legacy unqualified WHERE source extraction remains outside this correction.
