# 045 - Support persistent server settings

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 13; retained from revision `80d71d4`.

## Problem / opportunity

The original design proposed settings.toml and startup selection of transport, cache, and Session settings. Current settings are environment-based.

## Desired outcome

Decide whether a settings file or additional startup options are needed and define precedence with environment variables.

## Notes and references

Inspect [Settings](../../src/dbridge/config/settings.py). Coordinate [transport selection](022-transport-selection.md) and future cache/Session settings.
