# 053 - Offer something useful for a bare SELECT

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Observed while raising test coverage (OpenSpec change `raise-test-coverage`).

## Problem / opportunity

Completion for `"SELECT "` returns an empty list. The prefix classifies as a
column context, so [completion.py](../../src/dbridge/core/completion.py) tries to
resolve tables in scope; `sqlglot` cannot parse a bare `SELECT`, the exception is
swallowed, no table is in scope, and the column branch returns `[]` without
falling through to the keyword fallback.

A user typing `SELECT ` before writing a `FROM` clause therefore gets no
suggestions at all, rather than keywords or the full table/column set. By
contrast `"SELECT ((( "` matches neither context regex and does return keywords,
so the emptier and more common input is the one that behaves worse.

Evidence: `tests/core/test_completion.py::test_unparseable_sql_does_not_propagate`
asserts the current empty result.

## Desired outcome

Decide what a column context with no resolvable tables should return. Falling
back to keywords is the smallest change and matches what the surrounding code
already does elsewhere; offering every table's columns is more useful but noisier
and needs a ranking story. Either way, an empty list is the least useful of the
three options.

## Notes and references

[core/completion.py](../../src/dbridge/core/completion.py) — the `_SELECT_WHERE_RE`
branch returns `columns` unconditionally, never reaching the keyword fallback
below it. Related: [018](018-select-comma-completion.md) (columns after a SELECT
comma), [017](017-completion-ranking.md) (ranking, which a broader fallback would
need).
