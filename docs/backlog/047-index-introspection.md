# 047 - Browse database indexes

- Repo: dbridge, clients
- Status: deferred
- Change: none
- Origin: Original design overview; retained from revision `80d71d4`.

## Problem / opportunity

The original vision included index browsing, but the current table schema model contains columns, primary keys, and foreign keys only.

## Desired outcome

Define useful index metadata and a protocol response, then implement and verify it for selected adapters.

## Notes and references

Inspect [TableSchema](../../src/dbridge/adapters/base.py) and client schema browsing before extending the response.
