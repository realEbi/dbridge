# Verification

- `uv run --group test pytest --cov`: 315 passed; 98.62% total coverage, above the
  unchanged 85% gate. The worktree has its own editable environment pointing to
  this checkout, verified through `dbridge.__file__`.
- Focused completion/Engine/stdio run: 185 passed. Core cases cover SELECT commas,
  expressions, prefixes/midword positions, multiline UTF-8, source/schema order,
  nested/UNION/statement/CTE/derived boundaries, metadata failures, literals and
  comments. Real in-memory SQLite/DuckDB Engine and subprocess tests establish
  the DSP behavior and bare SELECT keyword fallback.
- `uv run ruff check src/dbridge/core/completion.py tests/core/test_completion.py
  tests/core/test_engine.py tests/test_e2e_stdio.py`: passed.
- `uv run --group types mypy src/dbridge/core/completion.py`: passed. A full-project
  type run was not part of this completion slice; backlog 054 is separate work.
- Companion dbridge.nvim `FILE=tests/test_cmp.lua make test_file`: 24 passed.
  `make test`: 66 passed, against this worktree's actual server. Both Adapters
  exercise comma targets, automatic typed prefixes, Insert acceptance, Unicode
  midword/multiline positions, and bare-SELECT keywords. The prior client source
  reproduced `nameme` on both Adapters before its current-word range fix.
- `openspec validate complete-unqualified-select-targets --strict` and
  `git diff --check`: passed. Main-spec validation and local link/whitespace
  checks were completed as part of synchronization/archive.

The DSP item shape, byte framing and cursor offset convention are unchanged.
CTE/derived projected columns, outer correlated sources, ranking/deduplication,
and the legacy unqualified WHERE source-extraction limit remain deferred.
README, architecture, roadmap, manual checks and backlog 018/053 describe the
verified behavior; no domain terminology, architectural decision or development
command changed. Headless real-client checks do not claim a user's live GUI was
operated. No commits, pushes, releases, or unrelated changes were made.
