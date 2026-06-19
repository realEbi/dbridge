# Synchronous core engine and adapters for Phase 1

The design doc mandates an `asyncio`-everywhere core with `AsyncIterator` streaming. For Phase 1 we deliberately build a **synchronous** core engine and synchronous adapters instead.

Phase 1's only transport is stdio serving a single Neovim client, so there is no concurrency to exploit, and every driver we ship (`sqlite3`, `duckdb`) is blocking with no usable async equivalent. Going async would force `run_in_executor` wrapping or driver swaps for negligible benefit. Consequently we also drop streaming results, query cancellation, and transactions from the Phase 1 adapter interface — these only make sense alongside async/multi-client transports.

Async is revisited in a later phase if/when socket, TCP, or WebSocket transports serve multiple concurrent clients.
