# 053 - Offer something useful for a bare SELECT

- Repo: dbridge
- Status: done
- Change: [complete-unqualified-select-targets](../../openspec/changes/archive/2026-09-23-complete-unqualified-select-targets/)
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Problem / opportunity

Before this change, completion for `SELECT ` returned an empty list. The legacy
SELECT column branch found no tables and returned without reaching the existing
dialect-keyword fallback. This interrupted editing before writing a FROM clause.

## Desired outcome

Offer a useful deterministic fallback when no physical source resolves without
scanning all database columns or depending on an unimplemented ranking policy.

## Resolution

A bare `SELECT `, a source-free later SELECT target, or a SELECT containing only
unsupported CTE/derived sources now offers the Session's dialect keywords. The
server does not list tables or introspect unrelated columns for this fallback.
Known physical sources with no matching prefix or unavailable metadata still
return no columns. Core and real SQLite/DuckDB Engine/stdio tests verify this.

## Notes and references

See [completion](../../src/dbridge/core/completion.py), [SELECT target completion](018-select-comma-completion.md),
and the remaining [ranking](017-completion-ranking.md) and
[projected-source inference](055-completion-derived-and-correlated-sources.md) work.
