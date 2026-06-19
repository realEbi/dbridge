# dbridge

dbridge is a protocol-driven backend that bridges database engines to developer clients (Neovim first), exposing a uniform interface for queries, schema browsing, and SQL completion over JSON-RPC.

## Language

**Adapter**:
The database-engine-specific implementation behind a single interface. The core engine never talks to a driver directly — only through an Adapter (e.g. the DuckDB adapter, the Postgres adapter).
_Avoid_: driver, connector, backend

**Connection** (a.k.a. Connection Profile):
A saved, named configuration describing *how* to reach a database (adapter name + config). It is data, persisted to a profiles file. It is not a live object.
_Avoid_: profile-as-something-else, datasource

**Session**:
A live, server-side binding of one Connection to one instantiated Adapter, identified by a `session_id`. Carries the active database/schema. Created fresh by `dbridge/connect`; not persisted.
_Avoid_: connection (when meaning the live object), context

**Transport**:
The layer that moves JSON-RPC messages between a client and the core engine over a specific channel (Phase 1: stdio). The core engine is transport-agnostic.
_Avoid_: protocol (the protocol is JSON-RPC/DSP; the transport is the channel)

**Core Engine**:
The transport-agnostic business-logic layer sitting between Transport and Adapters: session management, query dispatch, schema registry, completion. Owns no driver code.
_Avoid_: backend, service
