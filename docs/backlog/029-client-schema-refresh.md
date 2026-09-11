# 029 - Refresh schema without reconnecting the Profile

- Repo: dbridge.nvim
- Status: deferred
- Change: none
- Origin: Legacy backlog 6; retained from revision `80d71d4`.

## Problem / opportunity

The explorer's R action reportedly disconnects and reconnects to rebuild the subtree.

## Desired outcome

Use refreshSchema and new introspection calls where appropriate, preserving the live Session and clearly handling errors.

## Notes and references

Recheck the client explorer and coordinate [cache coverage](004-introspection-cache-coverage.md).
