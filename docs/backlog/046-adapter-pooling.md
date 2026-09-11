# 046 - Manage pooled adapter connections

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 6; retained from revision `80d71d4`.

## Problem / opportunity

The original design allowed internal connection pools, but current Sessions each own a single Adapter connection.

## Desired outcome

Decide when pooling is beneficial and how pool ownership, health checks, reconnects, and transaction affinity interact with Sessions.

## Notes and references

Coordinate [concurrency](012-concurrent-execution.md), [transactions](014-transactions.md), and remote adapters. Pooling is a candidate implementation, not a current invariant.
