# 060 - Verify the MySQL Adapter on other server versions

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: `add-mysql-adapter` planning, 2026-09-25; driver spike on MySQL 8.4.11

## Problem / opportunity

The MySQL Adapter is verified only against MySQL 8.4. Its guarantee that a late
cancel never interrupts the next statement relies on one server behavior: MySQL
discards a `KILL QUERY` that reaches an idle thread. Its cancellation and row-cap
release also rely on how `KILL QUERY` surfaces. A lone `SLEEP` returns `1`; a
statement spanning several rows fails with 1317. Neither behavior has been checked
on MySQL 8.0, MySQL 9.x, or MariaDB. MariaDB also differs in `KILL QUERY ID`
syntax, authentication defaults, and `RETURNING` support.

## Desired outcome

Run the MySQL real-server suite against MySQL 8.0, the current 9.x release, and a
supported MariaDB LTS release. Record which versions pass, and document each
version as supported or unsupported. Fix, or document, any version-specific
difference in kill semantics, key metadata, or authentication.

## Notes and references

Change: [add-mysql-adapter](../../openspec/changes/archive/2026-09-25-add-mysql-adapter/proposal.md).
Its design records the spike evidence and the kill-path decisions. The local
suite runs with `make test-mysql`; the compose server's image tag selects the
version. CI does not run MySQL.
