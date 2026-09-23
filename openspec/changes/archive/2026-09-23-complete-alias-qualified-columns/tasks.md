## 1. Qualified completion

- [x] 1.1 Implement current-scope physical-table qualifier resolution in dbridge and verify focused completion regressions for the reported SQL, prefixes, cursor offsets, scope isolation, malformed inputs, and metadata failures.
- [x] 1.2 Add real SQLite/DuckDB Engine and stdio coverage for alias completion; verify item insertion text and unchanged existing completion behavior with the focused integration tests and full gated suite (at least 85% coverage).
- [x] 1.3 Record compatibility and shared-flow evidence from the companion dbridge.nvim `trigger-qualified-column-completion` change, using its client tests against this updated server.

## 2. Documentation and completion

- [x] 2.1 Update README, architecture, manual checks, roadmap, and backlog 015 with the verified server behavior and client verification limits; track unsupported source inference separately and verify links/examples.
- [x] 2.2 Record verification evidence, run strict OpenSpec validation and whitespace checks, then synchronize the verified sql-completion contract and archive the completed change.
