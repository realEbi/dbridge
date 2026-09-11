# 006 - Execute the SQL statement under the cursor

- Repo: dbridge.nvim
- Status: deferred
- Change: none
- Origin: Legacy backlog 2.1; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly sends the whole buffer in normal mode or the visual selection. The earlier statement-boundary extractor was removed with the REST client.

## Desired outcome

Restore a command that selects the statement containing the cursor, with defined behavior for comments, strings, and delimiters.

## Notes and references

Recheck lua/dbridge/editor.lua get_sql. Treesitter was suggested; choose the approach after inspecting the current client.
