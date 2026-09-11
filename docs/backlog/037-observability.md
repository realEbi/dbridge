# 037 - Trace and observe server operations

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 19; retained from revision `80d71d4`.

## Problem / opportunity

The original vision proposed query execution tracing and OpenTelemetry integration.

## Desired outcome

Define useful timings, spans, diagnostics, configuration, and redaction while preserving stdout for protocol traffic.

## Notes and references

Coordinate [server notifications](010-server-notifications.md). OpenTelemetry is a candidate to evaluate in the change design.
