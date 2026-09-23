# 002 - Generate correctly qualified SQL identifiers

- Repo: dbridge, dbridge.nvim
- Status: done
- Change: [qualify-generated-table-identifiers](../../openspec/changes/archive/2026-09-23-qualify-generated-table-identifiers/)
- Origin: Legacy backlog 1.2; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly builds SELECT statements using bare table names, which can address the wrong table when schemas share a name. A uniform three-part identifier also fails for SQLite.

## Desired outcome

Have the server provide a correctly quoted, dialect-appropriate identifier for generated SQL. Choose an Adapter responsibility or response field in the change design.

## Notes and references

Related: [Session dialect](008-session-dialect.md). Recheck lua/dbridge/init.lua in the client and adapter schema responses here.

## Resolution

The server adds Adapter-owned sql_identifier to getTableSchema and accepts literal
structured table identity while retaining fqn and listTables compatibility. The
[Neovim companion](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-use-server-table-identifiers)
waits for metadata, retains the identifier and executes against the selected
Session. Real SQLite/DuckDB tests cover punctuation and duplicate scopes. Dialect
reporting (008) and hierarchy presentation (003) remain deferred.
