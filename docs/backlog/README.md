# Backlog

One file per deferred idea, defect, or open design decision. The
[roadmap](../roadmap.md) groups future direction; an [OpenSpec change](../../openspec/changes/)
owns the implementation plan once work is selected. Check an item's current
Status before acting on it.

## Conventions

- Name items `NNN-descriptive-slug.md`, allocating the next unused number. Keep
  IDs stable and never reuse them.
- Each item owns its Repo, Status, Change, Origin, problem, desired outcome, and
  relevant references. The index links titles without duplicating those fields.
- Status is `deferred`, `planned`, `done`, or `dropped`. New items are deferred;
  writing an idea here does not schedule or authorize its implementation.
- When selected, link the OpenSpec change and mark the item planned. Keep detailed
  tasks and acceptance scenarios in that change, with a link back to the item.
- After verified completion and archive, mark done and link the archived change.
  Keep a brief resolution so references to the ID remain useful. Record a reason
  for dropped items. If work is abandoned, return it to deferred with context.
- For work spanning repositories, name each owner and link its corresponding
  change. Recheck client findings in that repository before implementing them.

The initial entries preserve unresolved material from revision `80d71d4`, before
retiring the old design and phase documents. They include both reported defects
and speculative ideas; migration did not reproduce every client report or approve
every design option. Any retained legacy priority is historical context.

## Item template

```markdown
# NNN - Short outcome

- Repo: dbridge / dbridge.nvim / other owner
- Status: deferred
- Change: none
- Origin: report, document section, or observed evidence

## Problem / opportunity

What is missing or wrong, why it matters, and what is known versus assumed.

## Desired outcome

The behavior or decision needed. Leave detailed implementation tasks to OpenSpec.

## Notes and references

Relevant source/tests, dependencies, and questions to resolve before planning.
```

## Daily use and correctness

- [001 - Rename Profiles without leaving duplicates](001-profile-rename.md)
- [002 - Generate correctly qualified SQL identifiers](002-qualified-identifiers.md)
- [003 - Represent each database's browsing hierarchy accurately](003-database-hierarchy.md)
- [004 - Cache database and schema listings consistently](004-introspection-cache-coverage.md)
- [005 - Extract DuckDB primary and foreign keys](005-duckdb-constraints.md)
- [006 - Execute the SQL statement under the cursor](006-statement-under-cursor.md)
- [008 - Expose the Session's SQL dialect to clients](008-session-dialect.md)
- [018 - Offer columns after a SELECT comma](018-select-comma-completion.md)
- [027 - Remove known unused imports](027-unused-imports.md)
- [028 - Show which Session will execute SQL](028-active-session-indicator.md)
- [029 - Refresh schema without reconnecting the Profile](029-client-schema-refresh.md)
- [048 - Select a Session's active database and schema](048-session-scope-selection.md)

## Query execution and transports

- [009 - Cancel an in-flight query](009-query-cancellation.md)
- [010 - Deliver server-to-client notifications](010-server-notifications.md)
- [012 - Evolve the synchronous core for concurrent work](012-concurrent-execution.md)
- [013 - Retrieve large results with bounded fetching](013-large-results.md)
- [014 - Expose explicit transaction control](014-transactions.md)
- [022 - Choose transport and process topology](022-transport-selection.md)
- [026 - Add a WebSocket transport with authentication](026-websocket-transport.md)
- [040 - Serve local clients over Unix sockets](040-unix-socket-transport.md)
- [041 - Serve remote clients over TCP](041-tcp-transport.md)
- [049 - Execute queries with bound parameters](049-query-parameters.md)

## Adapters and metadata

- [019 - Port and register the MySQL adapter](019-mysql-adapter.md)
- [020 - Port and register the PostgreSQL adapter](020-postgres-adapter.md)
- [021 - Port and register the Snowflake adapter](021-snowflake-adapter.md)
- [024 - Choose a cache policy for slow remote introspection](024-remote-cache-policy.md)
- [038 - Persist reusable schema metadata](038-persistent-schema-cache.md)
- [042 - Add a BigQuery adapter](042-bigquery-adapter.md)
- [043 - Invalidate schema metadata after DDL](043-ddl-cache-invalidation.md)
- [045 - Support persistent server settings](045-settings-file.md)
- [046 - Manage pooled adapter connections](046-adapter-pooling.md)
- [047 - Browse database indexes](047-index-introspection.md)

## SQL assistance

- [011 - Return an actual entity-relationship graph](011-erd-extraction.md)
- [015 - Complete alias-qualified columns](015-alias-completion.md)
- [016 - Complete values and enums in SQL predicates](016-value-completion.md)
- [017 - Rank and filter completion suggestions](017-completion-ranking.md)
- [025 - Support custom completion providers](025-completion-providers.md)
- [030 - Resolve dbt models in completion](030-dbt-completion.md)
- [032 - Expose structured EXPLAIN plans](032-explain-plans.md)
- [044 - Introspect and complete SQL functions](044-function-completion.md)

## Clients and operations

- [007 - Save and browse reusable SQL queries](007-saved-queries.md)
- [023 - Reference secrets from Profiles](023-secret-managers.md)
- [031 - Persist and browse query history](031-query-history.md)
- [033 - Connect through SSH tunnels](033-ssh-tunnels.md)
- [034 - Execute multiple statements with separate results](034-notebook-execution.md)
- [035 - Build a browser client](035-web-client.md)
- [036 - Build a VS Code client](036-vscode-client.md)
- [037 - Trace and observe server operations](037-observability.md)
- [039 - Expire idle Sessions and release resources](039-session-idle-timeout.md)
