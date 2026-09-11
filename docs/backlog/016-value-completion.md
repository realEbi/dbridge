# 016 - Complete values and enums in SQL predicates

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.3; original design 10; retained from revision `80d71d4`.

## Problem / opportunity

Completion does not suggest enum or distinct values after a predicate such as WHERE status = '.

## Desired outcome

Define when value suggestions are appropriate, where they come from, and how their retrieval is bounded and cached.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py). Resolve performance and data-exposure implications before issuing additional queries.
