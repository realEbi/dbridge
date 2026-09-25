# Verification

Verified on 2026-09-25 against MySQL 8.4.11 with aiomysql 0.3.2.

| Check | Result |
|---|---|
| `make check` (Python 3.12.12) | Mypy: 60 source files; Ruff: passed |
| Python 3.11.16 mypy and Ruff | Passed |
| `make test-cov PYTEST_ARGS=-q` (Python 3.12.12) | 585 passed, 47 MySQL tests skipped; 96.51% coverage |
| Python 3.11.16 `pytest --cov -q` | 585 passed, 44 MySQL tests skipped; 96.77% coverage; run before the final three MySQL-only regressions were added |
| `make mysql-up` | Healthy MySQL 8.4.11; seeded row count 1,000,000 |
| `make test-mysql PYTEST_ARGS=-q` | 47 passed in 1.57 seconds |
| `openspec validate add-mysql-adapter --strict` | Passed before synchronization |
| `openspec validate --specs --strict` | All 14 capability specs passed after synchronization |
| Manual guide through a disposable stdio client | Connect, browse, metadata, cap, cancel, state preservation, USE/refresh, disconnect, clean process exit passed |
| `git diff --check` | Passed |

The real-server suite uses ordinary accounts without PROCESS, CONNECTION_ADMIN,
or SUPER. An independent observer verifies running statements, connection cleanup,
and positive/negative statement-history evidence. Tests cover cancellation races,
FIFO ordering, state preservation, shared control recovery, capped procedure
effects, later result sets remaining unbuffered, cross-database keys, literal
identifiers, and framed DSP behavior. Shutdown tests include forced grace expiry,
two Sessions abandoning a shared control connection, and a stalled handshake.

The manual million-row SELECT returned the 100-row cap with its warning in
0.010 seconds. The automated test enforces the specified one-second ceiling.

Review found two implementation details beyond the throwaway spike: aiomysql's
inherited next-result transition buffers later sets, and a shared control stream
must remain available for consecutive synchronous abandonment kills. The Adapter
uses an unbuffered result bridge and marks unread abandonment replies so ordinary
reuse reopens the control stream. Handshake tasks are tracked for bounded cleanup.
These preserve the planned behavior; the design records the private-driver risk.

An initial run of the unchanged SQLite/DuckDB suite had one DuckDB metadata timeout
(581 passed, one failed); the immediate focused rerun and both full coverage runs
passed. The observation is deferred in backlog 062; no DuckDB code was changed.
The existing NumPy deprecation warnings remain. MySQL tests emit no warnings.

MySQL is excluded from coverage as specified; its missing-extra registry handling
remains measured. CI has no MySQL service. Only MySQL 8.4 is verified, proxies are
unsupported, temporary tables are not listed, and capped CALL/multi-statement
requests drain. Non-JSON result conversion remains backlog 061.
