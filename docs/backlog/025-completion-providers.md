# 025 - Support custom completion providers

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design question 6 (low priority in the legacy backlog); retained from revision `80d71d4`.

## Problem / opportunity

The design raised a provider/plugin system for project-aware completion without committing to an extension API.

## Desired outcome

Decide whether a provider interface is needed and define composition, failure isolation, context, and ranking responsibilities.

## Notes and references

Related: [dbt completion](030-dbt-completion.md). Derive an extension boundary from real use cases before standardizing it.
