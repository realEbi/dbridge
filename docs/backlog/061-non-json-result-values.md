# 061 - Reply to queries that return non-JSON values

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: observed during `add-mysql-adapter` planning, 2026-09-25

## Problem / opportunity

`dbridge/execute` sent no reply when a result contained values that JSON cannot
encode. A probe connected a DuckDB `:memory:` Session and executed
`SELECT 1.50::DECIMAL(5,2) d, DATE '2020-01-01' dt, 'ab'::BLOB b`; no reply
arrived within 120 seconds. The stdio writer serializes replies with plain
`json.dumps` (`protocol/transport/stdio.py`), and no layer converts `Decimal`,
date/time, or `bytes` values. The failure path after the serialization error
was not traced: it is not yet known whether the request task dies or the error is
only logged. Any common DuckDB type is affected, and MySQL will return
`Decimal`, `datetime`, and `bytes` constantly.

## Desired outcome

Every `execute` reply is delivered. Decide one protocol representation for
non-JSON values, for example decimals as strings, temporal values as ISO 8601,
and binary as base64 or hex. Specify it in the query-results contract, apply it
for every Adapter, and make a serialization failure reply with an error instead
of leaving the request unanswered.

## Notes and references

Should land before or alongside the MySQL Adapter
([add-mysql-adapter](../../openspec/changes/add-mysql-adapter/design.md), Risks).
Clients currently render values as received, so the chosen representation is a
protocol change clients may need to follow.
