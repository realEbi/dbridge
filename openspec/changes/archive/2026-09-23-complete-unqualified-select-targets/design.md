## Context

The qualified completion path already repairs incomplete identifiers with a unique
cursor marker, parses full SQL, and finds the exact sqlglot SELECT scope. The old
unqualified SELECT/WHERE regex instead scans all physical tables in the first
statement, misses commas, and returns an empty result for bare SELECT. Backlog 018
and 053 are accepted for this slice; 017 and 055 remain deferred. ADR-0001's
synchronous Core Engine/Adapter boundary remains unchanged.

## Goals / Non-Goals

Complete current-scope unqualified SELECT expressions, retain UTF-8 byte cursor
conversion and response fields, and give a deterministic source-free fallback.
Do not infer CTE/derived projections, correlated sources, rank/deduplicate labels,
scan all tables, change client trigger policy, or replace legacy WHERE completion.

## Decisions

1. Share the cursor-marker scope lookup with qualified completion. A candidate
   must parse as an unqualified Column inside a SELECT target expression, not as
   a string/comment, table, or output alias. Replace the whole identifier when
   the cursor is in its middle, preserving the full SQL after it. An empty
   target immediately before FROM preserves that keyword and inserts separating
   whitespace only in the temporary parse input.
2. Read only the matching SELECT scope's selected sources. Preserve schema/catalog
   parts and reject CTEs even when sqlglot's case-sensitive name map classifies a
   differently cased CTE reference as a physical table.
3. Offer physical source columns in source/schema order with case-insensitive
   prefix filtering. Keep duplicate labels with distinct table detail. Skip
   individual metadata failures; a known physical source with no matching columns
   remains empty instead of offering unrelated keywords.
4. Fall through to existing dialect keywords when there are no physical sources
   or the SELECT context cannot be parsed. No database-wide fallback or ranking
   work is needed. Remove SELECT from the legacy regex so failed recognition
   cannot reintroduce whole-statement source leakage.
5. This is a compatible DSP behavior change. Real Adapter and stdio tests
   establish server behavior. The companion
   [client change](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-replace-unqualified-column-completions)
   extends its existing identifier replacement to unqualified columns after real
   nvim-cmp reproduced `na|me` being accepted as `nameme`. Client UI tests establish
   the shared flow for SQLite and DuckDB; no DSP migration is required.

## Risks / Trade-offs

Tolerant parsing can reinterpret incomplete SQL, so marker identity and actual
projection ancestry must be checked before metadata calls. Parsing remains the
existing generic sqlglot approach; dialect-specific projected-column inference
is outside this change. Keyword fallback is intentionally modest; its list is
owned by each Adapter. The legacy WHERE path keeps its prior source extraction
limit, documented separately from the newly scoped SELECT path.

## Verification

Exercise commas, expressions, middle-of-name replacement, UTF-8/multiline text,
JOIN ordering, nested/UNION/multiple statements, CTE/derived isolation, malformed
SQL, and metadata errors with core tests. Run real SQLite/DuckDB Engine and stdio
checks plus the full coverage gate and focused lint/type checks. Update owning
documents, synchronize verified deltas, and archive only after validation.
