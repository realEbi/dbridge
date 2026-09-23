## 1. Scoped SELECT completion

- [x] 1.1 Implement scoped unqualified SELECT expressions and keyword fallback in dbridge, preserving qualified completion and DSP compatibility.
- [x] 1.2 Verify core scope boundaries, prefix/UTF-8 behavior, metadata failures, and real SQLite/DuckDB Engine/stdio flows; run the full coverage gate and focused lint/type checks; verify the companion dbridge.nvim acceptance flow against this server.

## 2. Documentation and completion

- [x] 2.1 Update README, architecture, manual checks, roadmap, and backlog 018/053 to describe verified behavior and remaining limits.
- [x] 2.2 Record verification, strictly validate the change and specs, synchronize the verified delta, and archive the change with corrected backlog links.
