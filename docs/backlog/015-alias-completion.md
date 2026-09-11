# 015 - Complete alias-qualified columns

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.3; original design 10; retained from revision `80d71d4`.

## Problem / opportunity

Tier-1 completion does not resolve alias-qualified positions such as JOIN orders o ON o.

## Desired outcome

Resolve aliases and query scope to offer the appropriate columns in SELECT, WHERE, and JOIN conditions.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py). Include partial SQL and multiple table scopes in the change's scenarios.
