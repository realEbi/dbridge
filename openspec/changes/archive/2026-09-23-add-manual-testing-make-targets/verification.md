# Verification

Verified on 2026-09-23 on macOS with GNU Make 3.81. The suite used Python 3.11.16;
preparation in a disposable project copy used
uv-selected Python 3.12.12.

- Plain `make` printed help without running preparation or tests.
- Dry runs of all action targets and a `UV` / `PYTEST_ARGS` override produced
  the expected commands.
- `make manual-prepare` succeeded twice in a temporary project copy, including
  first-run environment creation. Both adapters produced 8 customers, 10 products,
  10 orders, and 220 order items. Deleting order items between runs confirmed
  that the second preparation resets sample data.
- Generated databases preserved selected column order, NULLs, and empty strings.
  Real stdio RPC connections using absolute paths worked for both adapters and
  returned the expected 100-row cap and truncation warning. Profile listings
  stayed empty in isolated configuration.
- Hashes confirmed the repository's pre-existing sample databases were unchanged
  by verification. Temporary data and server subprocesses were cleaned up.
- `make test`: 187 passed.
- `make test-cov`: 187 passed, 99.20% coverage (85% minimum).
- `openspec validate --all --strict --no-interactive`: passed. Existing long
  requirement text notices in the test-coverage spec are informational.
- `git diff --check`: passed. Independent read-only review found no issues.
- All 53 local link targets across the manual/development/architecture guides and
  README exist; the embedded walkthrough and its anchor were removed. The final
  documentation-only revision required no repeated runtime tests.

uv required permission to access its cache outside the workspace; verification
passed after that access was approved. No runtime changes or additional tests
were necessary for these wrappers. Lint and type checking were not run.

Documentation ownership review: manual/development guides, roadmap progress, and
sample rebuild references were updated. The embedded Python walkthrough was
removed in favor of the existing sample generator and automated suite. README and
architecture descriptions of the guide were updated accordingly.
Runtime architecture, glossary, ADRs, dependencies, DSP contracts, and accepted
coverage requirements are unchanged; no backlog resolution or spec sync applies.
