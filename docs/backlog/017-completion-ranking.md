# 017 - Rank and filter completion suggestions

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.3; original design 10; retained from revision `80d71d4`.

## Problem / opportunity

Completion uses simple label or table.column sort keys and lacks meaningful context ranking.

## Desired outcome

Define prefix filtering, deduplication, ranking, and insertion behavior while keeping the response compatible with completion clients.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py) and the consuming client before choosing server versus client responsibilities.
