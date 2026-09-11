# 039 - Expire idle Sessions and release resources

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 12-13; retained from revision `80d71d4`.

## Problem / opportunity

The original design included last-active timestamps and configurable idle cleanup; current Sessions remain until disconnected or the process exits.

## Desired outcome

Define what counts as idle, how active queries and transactions are treated, and how clients learn about expiry.

## Notes and references

Inspect [SessionManager](../../src/dbridge/core/session.py). Coordinate [concurrency](012-concurrent-execution.md) and [transactions](014-transactions.md).
