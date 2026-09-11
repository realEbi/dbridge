# 050 - Decide whether DspError has a purpose

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Problem / opportunity

`DspError` is defined in [protocol/errors.py](../../src/dbridge/protocol/errors.py)
but is never raised, caught, or imported anywhere in the package. `Dispatcher`
maps domain exceptions (`ProfileNotFoundError`, `InvalidRequestError`,
`SessionNotFoundError`, `AdapterConnectionError`, `AdapterQueryError`,
`AdapterError`, `KeyError`) straight to error codes without going through it.

Evidence: `grep -rn "DspError" src/ tests/` matches only the class definition.
It is the sole reason that module reports below 100% coverage; the coverage
change deliberately did not write a test for it, because a test asserting that
dead code constructs correctly proves nothing.

Two error codes are similarly unreferenced: `QUERY_CANCELLED` (-32004) has no
cancellation to report (see [009](009-query-cancellation.md)), and
`PARSE_ERROR` (-32700) is never emitted — a malformed frame currently crashes
the loop rather than producing it (see [052](052-truncated-frame-crashes-loop.md)).

## Desired outcome

Decide whether `DspError` is the intended base for adapter/protocol errors that
carry a code — in which case the dispatcher should use it and the exception
hierarchy should be reconciled with `exceptions/__init__.py` — or whether it is
leftover scaffolding to delete. Either way the module stops carrying code that
nothing reaches. Resolve the unreferenced error codes in the same pass.

## Notes and references

[protocol/errors.py](../../src/dbridge/protocol/errors.py),
[protocol/handlers.py](../../src/dbridge/protocol/handlers.py),
[exceptions/__init__.py](../../src/dbridge/exceptions/__init__.py). Related
cleanup: [027](027-unused-imports.md). Deleting it is a source-compatible change
for clients, since it never reached the wire.
