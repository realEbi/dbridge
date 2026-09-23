# Verification

Verified on 2026-09-23 with local Python 3.11.16 and sqlglot 30.11.0.

## Reproduction and result

Before the change, direct framed stdio RPCs against SQLite returned only keywords
at both `p.` positions in `SELECT p.name, p.category FROM products p LIMIT 100`.
The same Session returned columns at an unqualified first SELECT position.

After the change, both positions return `id`, `sku`, `name`, `category`, `price`,
and `discontinued` against the existing SQLite and DuckDB sample databases, in
that order, with unqualified insertion text. The sample checks were read-only.
Real Adapter and framed-stdio regressions additionally cover typed prefixes,
joined table isolation, and multibyte cursor positions with temporary/in-memory
data and guaranteed Session/subprocess cleanup.

## Checks

- `make test-cov`: 257 passed; total coverage 98.68%, above the 85% gate.
- Ruff check of the changed completion module and three test files: passed.
- `uv run --group types mypy src/dbridge/core/completion.py`: passed.
  The full type suite was not run; existing unrelated failures are backlog 054.
- Strict OpenSpec validation and whitespace checks: passed.
- Independent review found CTE case-folding and source-qualification issues;
  both were corrected and have behavior regressions in the final passing suite.

## Client compatibility and shared-flow verification

The user authorized the companion dbridge.nvim change
[`trigger-qualified-column-completion`](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-trigger-qualified-column-completion).
It registers the dot trigger and adds UTF-8 identifier replacement edits while
preserving full SQL, byte cursor offsets, and the existing DSP shape.

The client suite passed all 56 cases against this server using
`DBRIDGE_SERVER_CMD="/Users/ebi/Projects/dbms/dbridge/.venv/bin/python -m dbridge.server" make test`.
Fourteen new cases exercise actual nvim-cmp typing, popup contents, filtering,
and default Insert acceptance in child Neovim for both SQLite and DuckDB.
They cover both reported SELECT positions, existing suffix replacement,
multibyte text and identifiers, a later FROM line, and a line break after the dot.
Environment: Neovim 0.12.5, nvim-cmp `2ffe79f1f021def8dd1fcd81deb16f1bb0d989f3`.
These are real editor/server integration checks, not a test of the user's loaded
Neovim configuration. No personal editor configuration was changed.

The client defaults to an installed `dbridge` command. Testing this checkout
requires its documented `server_cmd` override and restarting Neovim
before reconnecting. No dependency, framing, Profile, or RPC-shape migration is
required. Backlog 055 records deferred derived/correlated sources; 018 retains
unqualified SELECT-comma completion. Glossary and ADR-0001 remain unchanged.
