# 019 - Port and register the MySQL adapter

- Repo: dbridge
- Status: done
- Change: [add-mysql-adapter](../../openspec/changes/archive/2026-09-25-add-mysql-adapter/proposal.md)
- Origin: Legacy backlog 4.4; original design 7; retained from revision `80d71d4`.

## Problem / opportunity

The MySQL adapter was parked against an older interface.

## Desired outcome

Port execution and introspection to the async DBAdapter interface using a native
async MySQL driver, chosen and verified during the work. Validate ADR-0003's
cancellation contract with real MySQL: cancelling one operation stops
its work, leaves the Session usable, and cannot interrupt another request. Keep
the driver optional and verify real execution, introspection, and cleanup.

The native driver must implement these guarantees without requiring the Engine
to know its cancellation mechanism. That validation is an explicit milestone 3
outcome; the SQLite/DuckDB thread-backed implementations alone do not
prove the interface for native async drivers.

## Resolution

Registered an optional aiomysql Adapter through the `dbridge[mysql]` extra, with
native async query and metadata Channels and a shared control connection for
cancellation, cap release, and shutdown. Real MySQL 8.4 tests verify execution,
ordered results, cancellation isolation and state preservation, metadata and keys,
qualified identifiers, and lifecycle cleanup. ADR-0003's native-driver validation
trigger is met; [ADR-0004](../adr/0004-mysql-interruption.md) records the design.

PostgreSQL and Snowflake remain parked. Other MySQL/MariaDB versions remain
[060](060-mysql-server-versions.md); non-JSON result conversion remains
[061](061-non-json-result-values.md). Proxies and load balancers are unsupported,
temporary tables are not listed, and capped procedures/multi-statement requests
drain to preserve later effects.

## Notes and references

Inspect [MySQL](../../src/dbridge/adapters/mysql.py). Related:
[concurrent execution](012-concurrent-execution.md).

The optional module is excluded from coverage measurement because it needs a
driver extra and a real server; the registry loader remains measured. Run its
suite with `make test-mysql`. CI skips the MySQL tests and retains the 85% floor
for measured code; see [development](../development.md#coverage).
