# 034 - Execute multiple statements with separate results

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design 19; retained from revision `80d71d4`.

## Problem / opportunity

The original vision proposed notebook-style execution with one result block per statement.

## Desired outcome

Define statement boundaries, execution order, per-statement errors/results, and interaction with transactions.

## Notes and references

Related: [statement under cursor](006-statement-under-cursor.md) and [transactions](014-transactions.md). Server and client responsibilities need a joint change.
