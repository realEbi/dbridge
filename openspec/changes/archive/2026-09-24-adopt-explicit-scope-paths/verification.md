# Verification

- `make check`: mypy and Ruff passed without new suppressions.
- `uv run --group test pytest --cov`: 439 passed; `src/dbridge` coverage 97.60%, above the unchanged 85% gate.
- Strict change validation passed before synchronization. All seven server capability specs passed strict validation after synchronization.
- The linked [client change](../../../../../dbridge.nvim/openspec/changes/archive/2026-09-24-adopt-explicit-scope-paths/) passed `make test`: 164 cases across 11 files, zero failures/notes. Its 12 focused scope cases use real child Neovim instances and this server, including attached DuckDB catalogs, literal SQLite namespaces, one-tier SQLite browsing, independent buffers, actual nvim-cmp acceptance, and unedited execution.
- The [manual guide](../../../../docs/manual-testing-guide.md) records the matching reproducible flows. Shared behavior was exercised by headless real UI/server tests; a separate interactive desktop walkthrough was not run.
- Peer review verified literal identities, malformed-path recovery, complete cache invalidation, and SELECT isolation. Two introduced regressions were fixed and covered: failed connect discovery now closes its unreported Session, and refresh from an attached table preserves the focused identity through cursor events. The original real UI refresh probe passes after the fix.
- No unrelated defects or dead code were discovered; no new deferred item was needed.
- The user approved always-qualified table insertion and the linked client migration. Column insertion and display labels remain unchanged. The Adapter declarations and implementations were verified together with final type checks; no temporary unimplemented Adapter stubs remain.
- This is a breaking DSP change: upgrade both repositories together. DDL still requires explicit refresh or TTL expiry; ERD extraction and DuckDB constraints remain deferred. The synchronous runtime is unchanged.
- No staging, commits, push, publication, or release performed.
