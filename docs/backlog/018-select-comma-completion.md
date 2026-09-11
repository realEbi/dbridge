# 018 - Offer columns after a SELECT comma

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Legacy backlog 4.3; retained from revision `80d71d4`.

## Problem / opportunity

A trailing comma in a SELECT list, such as SELECT id, followed by a cursor, falls through to keyword suggestions.

## Desired outcome

Keep column completion active at subsequent SELECT targets, including multiline SQL and explicit cursor offsets.

## Notes and references

Inspect [completion](../../src/dbridge/core/completion.py) and [completion tests](../../tests/core/test_completion.py).
