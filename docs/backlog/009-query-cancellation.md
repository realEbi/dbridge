# 009 - Cancel an in-flight query

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Legacy backlog 3.2 and 4.2; retained from revision `80d71d4`.

## Problem / opportunity

QUERY_CANCELLED (-32004) is reserved, but there is no cancel method or in-flight query tracking. The current transport loop cannot read another request while executing a query.

## Desired outcome

Define query identity, cancellation races, adapter interruption, cleanup, and client feedback; provide a control path that stays responsive during execution.

## Notes and references

Coordinate with [concurrent execution](012-concurrent-execution.md), [notifications](010-server-notifications.md), and [large results](013-large-results.md). Cancellation needs concurrent control, not necessarily a particular async library.
