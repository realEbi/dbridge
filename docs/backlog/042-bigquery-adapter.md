# 042 - Add a BigQuery adapter

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 7; retained from revision `80d71d4`.

## Problem / opportunity

BigQuery was listed as a planned adapter, but there is no registered or parked implementation.

## Desired outcome

Define query jobs, polling, authentication, types, and introspection behind the Adapter boundary.

## Notes and references

Coordinate [large results](013-large-results.md) and [cancellation](009-query-cancellation.md); choose client-library integration during design.
