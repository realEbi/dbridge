# Verification

- Baseline reproduced: mypy 21 errors across five files; Ruff two unused imports.
- `uv run --group test pytest tests/test_logging.py -q`: 8 passed. Tests verify one
  named logger/handler, one stderr record after repeated Adapter construction,
  empty stdout, changed logger level, fallback level, and preserved custom handler.
- `make check`: mypy zero findings in 46 files and Ruff source/tests clean.
- `uv run ruff check .`: repository-wide lint clean.
- A temporary source probe containing an incompatible assignment and unused
  import caused both documented checks to fail as expected. It was removed in a
  finally block, after which both checks passed again.
- `make test-cov`: 260 tests passed on Python 3.12.12, total statement/branch
  coverage 98.97%; logging 100%. The existing 85% floor is unchanged.
- Compared the workflow against Git HEAD: triggers, matrix/job identity, and the
  coverage step are byte-for-byte unchanged; only two static-check steps were added.
- `make help` lists the new `check` option and existing commands correctly.

Final `openspec validate --all --strict`: 4 specs passed. All 106 local links
resolved; Markdown whitespace and `git diff --check` passed.
No actual GitHub Actions run or Python 3.11 runtime test was performed locally;
publishing is outside this task. The existing CI matrix will exercise both Python
versions after integration/publication. No client behavior, parked adapter ports,
coverage exclusions, or optional runtime dependencies were changed.

## Final combined server gate

After integrating identifiers, SELECT completion, and quality checks on
2026-09-23, `make check` passed (mypy: 48 files; Ruff: no findings), and
`make test-cov` passed all 350 tests on Python 3.12.12 with 98.71% total coverage.
This includes the structured-identity completion collision regressions. The 85%
coverage floor, synchronous execution, and supported Adapter set are unchanged.
Earlier counts above describe the isolated feature runs.
