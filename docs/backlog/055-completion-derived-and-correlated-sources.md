# 055 - Complete derived and correlated query sources

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Scope analysis for [complete-alias-qualified-columns](../../openspec/changes/archive/2026-09-23-complete-alias-qualified-columns/).

## Problem / opportunity

Physical-table alias completion can query Adapter metadata directly, but aliases
of CTEs and derived tables require projected-column inference. For example,
`WITH p AS (SELECT name FROM products) SELECT p.` needs the CTE's output schema,
not every products column. Outer correlated references need visibility rules
that respect subquery boundaries and local alias shadowing.

The initial qualified completion path returns no suggestions for these sources
instead of guessing physical columns from other scopes. Its tests preserve that
limitation. Quoted qualifier syntax still needs explicit dialect-aware design.
[002](002-qualified-identifiers.md) now preserves SQLite attached namespaces during
metadata lookup; ordinary qualified aliases can use that scoped introspection.
Literal quoted source components and projected-source inference remain separate
completion work.

## Desired outcome

Infer visible projected columns for CTE/derived sources and resolve valid outer
references with correct shadowing and dialect-specific visibility. Preserve
current-scope isolation and the existing completion response shape.

## Notes and references

See [completion](../../src/dbridge/core/completion.py), its
[tests](../../tests/core/test_completion.py), and
[015](015-alias-completion.md). sqlglot distinguishes physical Table sources from
query Scope sources; blindly collecting all tables would expose incorrect columns.
