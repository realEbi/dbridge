# 051 - Stop get_logger from stacking duplicate handlers

- Repo: dbridge
- Status: done
- Change: [restore-server-quality-checks](../../openspec/changes/archive/2026-09-23-restore-server-quality-checks/)
- Origin: Observed while raising test coverage ([archived change](../../openspec/changes/archive/2026-09-12-raise-test-coverage/proposal.md)).

## Resolution

Removed the unused cache and reused each named logger's direct handlers. The
default server logger receives one stderr console handler across repeated Adapter
construction; explicit embedding handlers are preserved. Tests assert one emitted
message, no stdout output, and effective level updates without stacking handlers.

## Original problem / opportunity

[logging/__init__.py](../../src/dbridge/logging/__init__.py) declares a module
cache, reads it, and never writes to it:

```python
_loggers = {}

def get_logger(name=APP_NAME, level_name=""):
    if logger := _loggers.get(name):   # never true — nothing assigns to _loggers
        return logger
    logger = getLogger(name)
    ...
    logger.addHandler(ch)              # so a new StreamHandler is added every call
    return logger
```

`logging.getLogger(name)` returns the same Logger each time, so every call adds
another `StreamHandler` to it. `DBAdapter.__init__` calls `get_logger()`, which
means each Session created adds a handler and every subsequent log line is
emitted one more time. After five connects, a single log call prints five times.

Evidence, measured on revision `e16c443`:

```console
$ python -c "
import logging
from dbridge.adapters.sqlite import SqliteAdapter
for i in range(1, 6):
    SqliteAdapter({'uri': ':memory:'})
    print(i, len(logging.getLogger('dbridge').handlers))"
1 1
2 2
3 3
4 4
5 5
```

The unreachable early return is also the only uncovered line in that module.

## Desired outcome

`get_logger` returns a configured Logger with exactly one console handler
regardless of how many times it is called. Populating `_loggers`, or guarding on
`logger.handlers`, both achieve it; pick one and drop the unused mechanism.

Note the interaction with the stdout rule: handlers write to stderr via
`StreamHandler()`'s default, which is correct — stdout is reserved for protocol
frames — and any fix must preserve that.

## Notes and references

[logging/__init__.py](../../src/dbridge/logging/__init__.py),
[adapters/base.py](../../src/dbridge/adapters/base.py) (`DBAdapter.__init__`).
The former `test_repeated_get_logger_stacks_handlers` regression record has
been replaced by tests asserting idempotent setup and single stderr output. Related: [037 - observability](037-observability.md).
