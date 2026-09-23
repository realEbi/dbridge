# 006 - Execute the SQL statement under the cursor

- Repo: dbridge.nvim
- Status: done
- Change: [client execute-statement-under-cursor](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-execute-statement-under-cursor/)
- Origin: Legacy backlog 2.1; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly sends the whole buffer in normal mode or the visual selection. The earlier statement-boundary extractor was removed with the REST client.

## Desired outcome

Restore a command that selects the statement containing the cursor, with defined behavior for comments, strings, and delimiters.

## Notes and references

Recheck lua/dbridge/editor.lua get_sql. Treesitter was suggested; choose the approach after inspecting the current client.

## Resolution

The query editor provides <leader>s and :DbridgeExecuteStatement. A byte-based lexical scanner selects one statement while retaining quoted/commented semicolons and SQLite trigger bodies. Whole-buffer/visual <leader>r remains available; real SQLite/DuckDB execution tests verify selection and side effects.
