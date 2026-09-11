# 030 - Resolve dbt models in completion

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 19; retained from revision `80d71d4`.

## Problem / opportunity

SQL containing dbt ref/source expressions has no project-aware completion support.

## Desired outcome

Resolve {{ ref(...) }} and {{ source(...) }} with a defined project context and useful suggestions.

## Notes and references

Related: [custom providers](025-completion-providers.md). Decide how project context reaches the server.
