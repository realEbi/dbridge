# 027 - Remove known unused imports

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 6; retained from revision `80d71d4`.

## Problem / opportunity

The previous backlog recorded Ruff F401 findings for operator.mul in parked MySQL code and ForeignKey in the DuckDB adapter.

## Desired outcome

Recheck the findings and remove genuinely unused imports in a scoped maintenance change.

## Notes and references

Inspect [MySQL](../../src/dbridge/adapters/_parked/mysql.py) and [DuckDB](../../src/dbridge/adapters/duckdb.py); verify with Ruff. This migration does not run or repair the linter.
