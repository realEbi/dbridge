# 002 - Generate correctly qualified SQL identifiers

- Repo: dbridge, dbridge.nvim
- Status: deferred
- Change: none
- Origin: Legacy backlog 1.2; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly builds SELECT statements using bare table names, which can address the wrong table when schemas share a name. A uniform three-part identifier also fails for SQLite.

## Desired outcome

Have the server provide a correctly quoted, dialect-appropriate identifier for generated SQL. Choose an Adapter responsibility or response field in the change design.

## Notes and references

Related: [Session dialect](008-session-dialect.md). Recheck lua/dbridge/init.lua in the client and adapter schema responses here.
