## Why

The documented type check reports 21 existing errors and Ruff reports two unused imports, preventing either check from reliably flagging new regressions. Repeated Adapter construction also adds duplicate stderr handlers, multiplying each diagnostic line.

This selects backlog [054](https://github.com/realEbi/dbridge/blob/dbridge-2.0/docs/backlog/054-type-check-does-not-pass.md), [051](https://github.com/realEbi/dbridge/blob/dbridge-2.0/docs/backlog/051-logger-handler-stacking.md), and [027](https://github.com/realEbi/dbridge/blob/dbridge-2.0/docs/backlog/027-unused-imports.md) as a maintenance slice supporting roadmap milestone 1, reliable daily use.

## What Changes

- Make logger setup idempotent while retaining stderr diagnostics and respecting explicitly installed handlers.
- Define type-check scope around shipped code and tests; exclude unregistered parked adapters without porting them or installing their optional drivers.
- Narrow the validated SQLite URI type and remove two confirmed unused imports.
- Run clean mypy and Ruff checks in the existing CI matrix without renaming required jobs or weakening the coverage gate; document local checks.

## Capabilities

### New Capabilities
- `diagnostic-logging`: Repeated logger setup does not duplicate console diagnostics or write them to protocol stdout.
- `static-checks`: Local and CI static checks cover the intended source/test scope and fail on findings.

### Modified Capabilities
None. Existing test-coverage requirements and the 85% floor remain unchanged.

## Impact

Only dbridge owns this change. Logging setup, SQLite type narrowing, unused imports, project/check configuration, tests, and maintenance documentation are affected. DSP and clients remain compatible. Parked adapter ports, concurrency, structured observability, and dependency removal are outside scope.
