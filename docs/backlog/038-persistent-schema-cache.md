# 038 - Persist reusable schema metadata

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 9; explicitly deferred in Phase 1; retained from revision `80d71d4`.

## Problem / opportunity

The current cache is in memory and per Session. The original design proposed a shared warm cache using SQLite or diskcache with a longer TTL.

## Desired outcome

Decide whether persistence is justified, then define identity, freshness, invalidation, isolation, and storage cleanup.

## Notes and references

Related: [remote cache policy](024-remote-cache-policy.md). The original ten-minute TTL is a proposal, not a current setting.
