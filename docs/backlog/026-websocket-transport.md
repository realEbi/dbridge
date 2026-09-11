# 026 - Add a WebSocket transport with authentication

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design 4 and question 7 (medium priority in the legacy backlog); retained from revision `80d71d4`.

## Problem / opportunity

Browser clients have no supported transport, and a network-accessible server needs an explicit authentication model.

## Desired outcome

Define authenticated WebSocket access, Session ownership, message handling, origin policy, and disconnect cleanup.

## Notes and references

Coordinate [transport selection](022-transport-selection.md), [concurrency](012-concurrent-execution.md), and the [web client](035-web-client.md). Authentication remains an open design decision.
