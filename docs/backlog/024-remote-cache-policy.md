# 024 - Choose a cache policy for slow remote introspection

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design question 4 (medium priority in the legacy backlog); retained from revision `80d71d4`.

## Problem / opportunity

A fixed 60-second in-memory TTL may be unsuitable for expensive metadata calls, particularly Snowflake.

## Desired outcome

Measure introspection costs and define configurable freshness, scope, invalidation, and failure behavior.

## Notes and references

Related: [cache coverage](004-introspection-cache-coverage.md), [Snowflake](021-snowflake-adapter.md), and [persistent cache](038-persistent-schema-cache.md).
