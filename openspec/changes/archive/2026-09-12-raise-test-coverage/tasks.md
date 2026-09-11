Owning repository: **dbridge** (server). No client repository is affected and no
cross-repository integration check applies — see [proposal.md](proposal.md) —
Impact.

Gaps below cite the line numbers from the verified baseline in
[design.md](design.md) — Context. Re-measure rather than trusting them if the
source has moved.

## 1. Re-scope the measurement

- [x] 1.1 Replace `[tool.coverage.run]` in `pyproject.toml` per design decision 2:
      `source = ["src/dbridge"]` (dropping `source_pkgs` and its `tests` entry),
      keep `branch = true`, remove `parallel = true`, and set
      `omit = ["src/dbridge/__about__.py", "src/dbridge/adapters/_parked/*"]`.
      Drop the now-meaningless `tests` entry from `[tool.coverage.paths]`, keeping
      the `dbridge` entry. Verify `uv run --group test pytest --cov
      --cov-report=term-missing` lists no `tests/` file and no `_parked/` module,
      and emits no `module-not-measured` warning.
- [x] 1.2 Extend `exclude_lines` in `[tool.coverage.report]` with `"^\\s*\\.\\.\\.$"`
      and `"@(abc\\.)?abstractmethod"` per design decision 3. Verify
      `adapters/base.py` and `protocol/transport/base.py` both report 100% and
      the run total reads 87%.
- [x] 1.3 Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and
      `addopts = "-ra"`, deliberately leaving coverage flags out per design
      decision 5. Verify bare `uv run --group test pytest` collects the same 75
      tests from the repository root and runs without coverage.
- [x] 1.4 Record the re-scoped pre-work baseline (total, and per-module misses)
      in the change's verification notes, so the delta this change produces is
      attributable. Do **not** set `fail_under` yet — it goes in at task 5.1,
      after the suite can meet it.

## 2. Normalize the test layout

- [x] 2.1 Add empty `__init__.py` to `tests/adapters/`, `tests/config/`,
      `tests/core/`, and `tests/protocol/` per design decision 6. Verify the full
      suite still collects and passes, and that collection no longer depends on
      rootdir `sys.path` insertion.
- [x] 2.2 Create `tests/conftest.py` holding the `isolated_profiles` fixture
      currently duplicated verbatim in `tests/protocol/test_handlers.py` and
      `tests/config/test_profiles.py`, plus a shared in-memory SQLite Session
      fixture for the Engine tests added in section 3. Remove both duplicates and
      verify the suite passes unchanged.
- [x] 2.3 Rename `tests/logging_test.py` to `tests/test_logging.py` with
      `git mv`. Verify both logging tests still collect and pass.

## 3. Cover behavior the subprocess boundary hides

Per design decision 1, these are in-process tests; `tests/test_e2e_stdio.py` is
not modified and must keep passing throughout.

- [x] 3.1 Extend `tests/protocol/test_framing.py` for the stdio reader gaps
      (`stdio.py:27`, branch `24->17`): a header block carrying other headers
      before `Content-Length` returns the parsed body; a header block that ends
      without a `Content-Length` returns `None`; a truncated body is handled
      without raising. Verify each asserts the returned value, not just that the
      call completed.
- [x] 3.2 Add `tests/protocol/test_stdio_transport.py` driving
      `StdioTransport.serve` in process over `io.BytesIO` streams
      (`stdio.py:34-42`): a request frame gets a response frame written back;
      a notification (no `id`) produces no output; EOF ends the loop and returns.
      Verify by parsing the captured output bytes back with `read_message`.
- [x] 3.3 Add `tests/test_server_main.py` covering `server.main` (`server.py:1-9`)
      with `monkeypatch` on `sys.stdin`/`sys.stdout`, per the stream-safety
      mitigation in design — Risks. Verify a connect request driven through
      `main()` returns a `session_id`, and that nothing is written to the real
      stdout during the test.
- [x] 3.4 Add `tests/core/test_engine.py` calling the untested `Engine` methods
      directly against an in-memory SQLite Session (`engine.py:36-38, 46, 49,
      57-58, 71-73`): `disconnect` removes the Session and its registry,
      `list_databases` and `list_schemas` return `["main"]`, `get_table_schema`
      returns the column set of a created table, and `complete` returns table
      items in a FROM position. Verify each asserts the returned value.
- [x] 3.5 Add `tests/core/test_executor.py` for truncation (`executor.py:8-9`),
      currently proven only end-to-end: a result longer than `max_rows` is capped
      to `max_rows`, `row_count` matches the capped length, and a truncation
      warning is appended while pre-existing warnings are preserved. Verify a
      result at or under the cap is returned untouched with no added warning.

## 4. Cover the remaining error and branch paths

- [x] 4.1 Extend `tests/adapters/test_sqlite.py` (`sqlite.py:29, 40-41, 59-60,
      69, 72, 110, 113`, branch `44->exit`): constructing without a `uri` raises
      `AdapterConnectionError`; connecting to an unopenable path raises
      `AdapterConnectionError`; invalid SQL raises `AdapterQueryError`;
      `list_databases` and `list_schemas` return `["main"]`; `dialect_name` is
      `"sqlite"`; `get_keywords` returns a non-empty list and a fresh copy;
      `disconnect` on a never-connected adapter is a no-op.
- [x] 4.2 Extend `tests/adapters/test_duckdb.py` (`duckdb.py:34-35, 52-53,
      115-116, 138`, branch `38->exit`): a failing connect raises
      `AdapterConnectionError`; invalid SQL raises `AdapterQueryError`;
      `get_table_schema` with a three-part `catalog.schema.table` fqn filters on
      the catalog; `dialect_name` is `"duckdb"`; `disconnect` on a
      never-connected adapter is a no-op.
- [x] 4.3 Extend `tests/core/test_completion.py` (`completion.py:56-57, 73-74,
      120-121, 123-124`, branch `29->31`): a non-integer `position` falls back to
      the whole string; SQL that `sqlglot` cannot parse yields keywords rather
      than raising; a `get_columns_fn` that raises for one table still returns the
      other tables' columns; a `list_tables_fn` that raises falls back to
      keywords; a `CompletionItem` built with explicit `insert_text` and
      `sort_key` keeps them. Preserve the UTF-8 byte-offset semantics — add a
      multi-byte case asserting an offset splitting a code point is handled.
- [x] 4.4 Extend `tests/config/test_profiles.py` for `_config_dir`
      (`profiles.py:27-31, 35`): `XDG_CONFIG_HOME` set, unset (falling back to
      `~/.config`), and the `win32` branch, each via `monkeypatch` on the
      environment and `sys.platform`; and `_profiles_path` appending
      `connections.toml`. Verify no test reads or writes the real
      `~/.config/dbridge`.
- [x] 4.5 Extend `tests/protocol/test_handlers.py` (`handlers.py:47-48, 66, 68`):
      a malformed request that fails validation returns `INVALID_REQUEST`; an
      adapter connection failure maps to `CONNECTION_FAILED`; a query failure maps
      to `QUERY_ERROR`. Verify each asserts the error code from
      `dbridge.protocol.errors`.
- [x] 4.6 Extend `tests/core/test_schema_registry.py` (`schema_registry.py:30`)
      and `tests/test_logging.py` (`logging/__init__.py:13`): `get_table_schema`
      is served from cache on the second call and re-queries after `refresh`;
      `get_logger` called twice with the same name returns the identical object
      without adding a second handler. Extend `tests/core/test_session.py` for
      `session.py` branch `39->exit`: closing an unknown `session_id` is a no-op
      that does not raise.

## 5. Enforce the floor

- [x] 5.1 Confirm the measured total is **≥93%** before gating. If it is short,
      close the largest remaining real gap rather than lowering the target or
      adding a test that asserts nothing — see design decision 7.
- [x] 5.2 Add `fail_under = 85` to `[tool.coverage.report]` per design decision 4.
      Verify `uv run --group test pytest --cov` passes, then verify the gate
      actually bites by temporarily raising `fail_under` above the measured total
      and confirming a non-zero exit; restore it to 85.
- [x] 5.3 Add `.github/workflows/test.yml` per design decision 8: triggered on
      `pull_request` targeting `main` and on pushes to `main`, using
      `astral-sh/setup-uv` as `publish-pypi.yml` does, with a
      `python-version: ["3.11", "3.12"]` matrix running
      `uv run --group test pytest --cov --cov-report=term`. Leave
      `publish-pypi.yml` untouched and verify it is unmodified in the diff.
- [x] 5.4 Verify the workflow green on both matrix versions on a real pull
      request, with the coverage total visible in each job log. Record the
      **exact** check names GitHub reports (expected `test (3.11)` and
      `test (3.12)` — the matrix produces no bare `test` check); task 5.6 needs
      the observed names, not guessed ones.
- [x] 5.5 Verify the CI gate actually fails on a coverage drop, not just on a
      failing test: open a scratch pull request that deletes enough tests to push
      coverage below 85%, confirm both matrix jobs fail and the log attributes
      the failure to coverage rather than to a test error, then close it without
      merging.
- [x] 5.6 Apply the branch protection rule on `main` per design decision 9,
      requiring the check names observed in 5.4 and enabling *Require branches to
      be up to date before merging*. This is a repository-settings action against
      `realebi/dbridge` (`gh api` or the settings page) that needs repository
      admin rights — **confirm with the user before applying it**, and do not
      apply a rule whose check names were guessed rather than taken from 5.4.
      Verify by re-opening the scratch pull request from 5.5 and confirming the
      merge is refused while the check is red.
- [x] 5.7 Not applicable — 5.6 completed, so the contingency below did not
      apply. Original text: if 5.6 cannot be completed (no admin rights, or the user defers it),
      record in the change's verification summary that the workflow is in place
      but not yet binding, and what remains to make it so. Do not mark 5.6 done
      on the strength of the workflow existing — the spec requires the check to
      block the merge, and an advisory check does not satisfy it.

## 6. Record findings rather than absorbing them

- [x] 6.1 Add a backlog item for `DspError` in `protocol/errors.py` — defined but
      never raised or caught anywhere in the package, and the only reason that
      module is below 100%. Follow the template in
      [docs/backlog/README.md](../../../../docs/backlog/README.md), allocate the next
      unused ID, set Repo `dbridge` and Status `deferred`, and cite the evidence.
      Link it from the index next to
      [027](../../../../docs/backlog/027-unused-imports.md).
- [x] 6.2 Note on backlog items
      [019](../../../../docs/backlog/019-mysql-adapter.md),
      [020](../../../../docs/backlog/020-postgres-adapter.md), and
      [021](../../../../docs/backlog/021-snowflake-adapter.md) that porting an
      adapter out of `adapters/_parked/` brings it into the measured scope and
      must land with tests meeting the floor. Keep the item IDs and existing
      Status values unchanged.
- [x] 6.3 Resolve the unused `pytest-mock` in the `test` dependency group: either
      use it where it genuinely simplifies a test added above, or remove it from
      `pyproject.toml`. Verify `uv sync` and the suite both succeed afterwards.
- [x] 6.4 Record any behavioral defect surfaced by a new test as its own backlog
      item with evidence, and do not fix it here (AGENTS.md — OpenSpec workflow).
      If none was found, state that in the verification summary.

## 7. Documentation

Per the [AGENTS.md](../../../../AGENTS.md#documentation-ownership) ownership table.

- [x] 7.1 Update [docs/development.md](../../../../docs/development.md) — it owns
      workflow commands and verification: add the coverage commands (terminal and
      HTML report), state the measured scope and why parked adapters are
      excluded, and document the 85% floor and that a run below it fails. Rewrite
      the *CI and release* section: correct the "There is currently no
      pull-request test workflow" line, describe the new workflow and its Python
      matrix, and state that the coverage checks are required for merging into
      `main`, naming which checks are required.
- [x] 7.2 Update the *Engineering conventions* section of
      [AGENTS.md](../../../../AGENTS.md) where it names the suite command, so the
      coverage gate is discoverable from the routing document. Keep the *Custom
      Instructions* section byte-for-byte unchanged.
- [x] 7.3 Confirm no other owned document needs an edit and say so explicitly in
      the verification summary: `README.md` (no public usage change),
      `CONTEXT.md` (no new domain term), `docs/architecture.md` (no runtime
      change), `docs/roadmap.md` (no milestone outcome shipped), and
      `docs/manual-testing-guide.md` (no manual check changed).
- [x] 7.4 Run the repository's other checks and record results, distinguishing
      passed, not run, and known failures:
      `uv run --group types mypy src/dbridge tests`,
      `uv run ruff check src/dbridge tests`,
      `openspec validate --all --strict --no-interactive`, and
      `git diff --check`. Do not claim a checker is clean without running it.
