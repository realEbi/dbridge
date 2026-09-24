## Context

See [proposal.md](proposal.md) — Why. The design-relevant current state, confirmed by
probing live Sessions rather than by reading alone:

```
SQLITE   TableSchema -> name='orders'  schema='main'   database='main'
         sql_identifier -> "main"."orders"                  <- 2 parts
         a client joining (database, schema, name) -> main.main.orders

DUCKDB   TableSchema -> name='orders'  schema='main'   database='memory'
         sql_identifier -> "memory"."main"."orders"         <- 3 parts
```

The fixed `database`/`schema` pair forces `sqlite.py` to assign one namespace to two
fields, so SQLite's structured metadata and its own identifier disagree about arity.
That disagreement is the `main/main` tier clients render.

Two further facts shape the approach:

- `Engine.list_databases` and `Engine.list_schemas` call the Adapter directly while
  `list_tables` and `get_table_schema` go through `SchemaRegistry`, so `refresh_schema`
  clears only part of the metadata view.
- `Engine.complete` calls `registry.list_tables()` with no scope arguments, so
  completion cannot see a non-default container at all. With two DuckDB catalogs
  attached, `list_tables()` returns `['orders', 'orders', 'shipments']`, completion
  offers two identical items, and executing the inserted `shipments` fails with
  `Catalog Error: Table with name shipments does not exist!`.

Only three places in `src/` read the fixed pair: `completion.py:136`,
`sqlite.py:97`, `duckdb.py:103`.

## Goals / Non-Goals

**Goals:**

- One way to address a table: an ordered literal Scope Path plus a name.
- An Adapter declares its own container arity, so no client hardcodes per-engine
  hierarchy knowledge and adding an Adapter needs no client change.
- Make an Adapter's arity contradiction unrepresentable rather than filtered at the
  render layer.
- Keep the server a pure function of `(Session, Scope Path, input)`.

**Non-Goals:**

- No change to the synchronous execution model, framing, UTF-8 cursor offsets, row
  capping, or Profile/Session separation.
- No new Adapter, and no revival of `adapters/_parked/`.
- No change to SELECT-scope isolation in completion. This design changes *which
  container* completion reads from, never which SELECT's sources it may use.
- No dialect-driven behavior beyond reporting the dialect.

## Decisions

### Scope lives in the request, not in the Session

Clients send a Scope Path with every metadata operation. The server holds no active
scope, and `Session.active_database`/`active_schema` are deleted.

*Why:* `CONTEXT.md` defines a Session as a live binding to one Adapter and puts
presentation in clients — which container a user is currently looking at is
presentation state. The fields have existed since the start, nothing in `src/` reads
them, and `tests/core/test_session.py:51` pins them as permanently `None` with the
comment "no protocol method sets them." Removing dead state is cheaper than wiring it
up. Decisively, backlog [022](../../../docs/backlog/022-transport-selection.md) leaves
open whether one process serves multiple clients: server-side mutable scope becomes a
contention bug the moment two clients share a Session, because one client's selection
silently changes what the other's completion returns. Stateless scope has no such
failure mode at any topology.

*Alternative considered — a `dbridge/useScope` method (server-held active scope).*
Terser calls and familiar SQL-shell ergonomics, and it would finally use the existing
fields. Rejected for the contention risk above, and because it would need revisiting
exactly when milestone 5 lands. This is what makes
[048](../../../docs/backlog/048-session-scope-selection.md) close as dropped rather
than done.

*Alternative considered — keep unscoped calls with a documented default.* Rejected:
the probe shows listing and resolution already interpret "unscoped" differently, and
a default that differs per operation is what produced the unreachable table.

### A Scope Path has the arity its Adapter declares

Scope is an ordered list of literal strings — `("main")` for SQLite,
`("memory", "main")` for DuckDB — replacing `database`/`schema` in `TableRef`,
`TableSchema`, and the wire shapes. `describeHierarchy`-style level declarations give
each tier a stable name and a client-facing label.

*Why:* it makes `main/main` inexpressible. SQLite declares one level and reports one
component, so the struct and the `sql_identifier` agree by construction. The existing
code is already simulating this: `completion.py:136` reads
`".".join(part for part in (table.database, table.schema, table.name) if part)` — that
`if part` filter exists precisely because the pair is sometimes partly empty. It is a
path join wearing a fixed-pair costume. `SchemaRegistry._get` already keys on the tuple
`("tables", database, schema)`, which becomes `("tables", *path)` with no structural
change.

*Alternative considered — keep `{database, schema}` and let levels be render labels.*
Smaller diff, and named fields read better than positional ones (`ts.schema` beats
`ts.scope[1]`). Rejected because it encodes "every engine has exactly two container
levels" as a protocol invariant that is already false for SQLite, leaving the
duplication in the data model and asking clients to ignore it — and it would be
re-litigated for every Adapter in roadmap milestone 3.

*Alternative considered — variable arity on the wire plus named accessors inside
Adapters.* Rejected: two representations of one concept, and the named form is exactly
the one that cannot express SQLite honestly.

### The hierarchy is primed on connect and re-delivered on refresh

`dbridge/connect` returns the levels and a default Scope Path; `dbridge/refreshSchema`
returns them again and is authoritative. No separate `describeHierarchy` method.

*Why:* a client must send a Scope Path on its first call but has none at connect time,
and both engines can answer cheaply (`SELECT current_database(), current_schema()` for
DuckDB, `PRAGMA database_list` for SQLite). The hierarchy is *not* static — `ATTACH`
changed `list_databases()` from `['memory','system','temp']` to
`['memory','system','temp','side']` mid-Session — so it must be re-fetchable. Rather
than add a method for that, it rides `refreshSchema`, which already means "my metadata
view is stale" and which the client already uses to rebuild its tree (backlog
[029](../../../docs/backlog/029-client-schema-refresh.md), done: "Refresh now
invalidates metadata and rebuilds the tree against the same live Session"). Net effect
is one fewer method than today's surface plus a discovery call. This is also what makes
`refreshSchema` honest about [004](../../../docs/backlog/004-introspection-cache-coverage.md):
it returns the complete refreshed view — levels, default scope, and an emptied cache.

Priming on connect and re-reading on refresh is one truth with two delivery points, not
two truths, because the spec names `refreshSchema` authoritative and `connect`'s copy
as of connect time.

*Alternative considered — a standalone `describeHierarchy` call.* Costs a mandatory
round trip every client pays on every connect, to deliver something connect could
include for free.

*Alternative considered — no default scope; clients walk `listDatabases` then
`listSchemas` and pick.* Purest stateless form, but every client then needs a "skip
`system`/`temp`, take the first" heuristic — the per-engine knowledge this design exists
to keep out of clients.

### Dialect on connect, hierarchy for rendering

`connect` reports the Adapter's dialect because it is static for the Session. It is
explicitly *not* how a client learns tree shape.

*Why:* backlog [008](../../../docs/backlog/008-session-dialect.md) already suggests
"potentially alongside session_id in the connect response." Keeping rendering keyed on
declared levels rather than on a dialect string is what stops MySQL, PostgreSQL,
Snowflake, and BigQuery (roadmap milestone 3) from each forcing a client change.

### Naming: Scope Path, not Scope

`completion.py:9` imports `Scope` from `sqlglot.optimizer.scope`, and
`completion.py:120` has the signature
`_physical_table(source: exp.Expression | Scope, scope: Scope)`. That file is the one
place SQL name resolution and catalog addressing meet, so the catalog concept is named
**Scope Path** (`ScopePath`, carried in a `path` field) and sqlglot's `Scope` keeps its
meaning untouched. `CONTEXT.md` gains **Scope Path** and **Scope Level**; it has no term
for either today. `sqlite.py:77`'s private `_namespace` helper becomes the Adapter's
single path component, so that name stays accurate.

### ADR relationship

No ADR is superseded. [ADR-0001](../../../docs/adr/0001-sync-core-for-phase-1.md) scopes
the synchronous core and is untouched — nothing here makes the core concurrent or adds
background work. This change is a protocol and data-model decision, and its rationale
lives in this document rather than in a new ADR; if server-held scope is ever revisited
under a multi-client topology, that reversal would warrant an ADR because it would
contradict the reasoning above.

## Risks / Trade-offs

- **Stale hierarchy after `ATTACH` without a refresh** → Bounded by design: every
  metadata call carries its own explicit Scope Path, so nothing resolves against stale
  hierarchy; only the level list and default scope go stale, and the trigger is the
  user's own statement. Automatic invalidation is
  [043](../../../docs/backlog/043-ddl-cache-invalidation.md), which this change hands the
  extra consequence. Classifying schema-changing SQL inside this change would be scope
  creep into a decision that needs its own design.
- **Wordier client calls; the client must track scope per buffer and tree node** →
  Backlog [028](../../../docs/backlog/028-active-session-indicator.md) already has the
  client tracking per-buffer Session state, so Scope Path is an increment on an existing
  structure rather than a new one.
- **Positional path components read worse than named fields** → Accepted deliberately.
  The level declaration supplies names for display, and the alternative cannot represent
  SQLite honestly. Tests assert against declared level names, not bare indices.
- **Large simultaneous break: 6 of 13 RPCs, ~103 test call sites across 9 files** →
  Sequenced in [tasks.md](tasks.md) so the Adapter interface and registry land before the
  protocol surface, keeping the suite meaningful between slices rather than red
  throughout. Coverage must stay at or above 85%.
- **Cross-repository lockstep with `dbridge.nvim`** → See Migration Plan. The risk is a
  client pinned to an older server, or the reverse; there is no negotiation mechanism, so
  the mismatch surfaces as `INVALID_REQUEST` on the first metadata call.
- **Marked-but-returned internal containers could clutter client trees** → Marking is a
  server guarantee; collapsing them by default is client presentation, and the marker is
  what makes that possible without per-engine knowledge. Filtering server-side was
  rejected because it would hide `information_schema` from anyone wanting to inspect it.

## Migration Plan

No protocol negotiation and no compatibility window: this is the `dbridge-2.0` line, and
the dual-input path that a compatibility shim would extend is itself part of what is
being removed. A client speaking the old surface receives `INVALID_REQUEST` on its first
metadata call rather than silently wrong data, which is the intended failure mode.

Ownership split, per AGENTS.md: this change owns server behavior and the DSP contract.
`dbridge.nvim` owns its explorer, completion source, and per-buffer state, and needs its
own linked change in that repository — nothing here authorizes editing it. Compatibility
is defined by the server's declared levels: the client reads levels and the default
Scope Path from `connect`, sends a Scope Path of matching arity on every metadata call,
re-reads both from `refreshSchema`, and stops reading `.database`/`.schema`.

Rollback is `git revert` of the server change together with the client change; because
the break is simultaneous and unnegotiated, reverting one without the other reproduces
the mismatch above.

Integration verification spans both repositories and must cover a DuckDB Session with a
second catalog attached and a SQLite Session with an attached namespace — the two cases
that produced the original defects. The SQLite case is the one that proves `main/main` is
gone from the client tree.

## Open Questions

- Labels for the declared levels: whether DuckDB's tiers present to users as
  "catalog"/"schema" or "database"/"schema". Engine-accurate terms are the default; this
  is display text that can change without touching the specs, the approach, or the task
  breakdown.
- Whether a future Adapter needs a level marked optional (a container tier that some
  Sessions lack). Neither shipped Adapter does, so the declaration stays fixed-arity per
  Adapter until a real case appears in roadmap milestone 3.
