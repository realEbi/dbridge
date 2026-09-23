# 028 - Show which Session will execute SQL

- Repo: dbridge.nvim
- Status: done
- Change: [client preserve-and-display-active-session](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-preserve-and-display-active-session/)
- Origin: Legacy backlog 6; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly tracks the last-touched Session but does not display the target of its execution command.

## Desired outcome

Make the active Session visible and keep the indicator consistent with execution targeting and disconnects.

## Notes and references

Recheck get_active_session and the explorer/results UI in the client repository.

## Resolution

The query editor now displays the Profile name, live Adapter, and Session ID from the same selector used by execution and completion. Selection, deletion, failed requests, and known server stops keep the display consistent; real multi-Profile client tests verify the flow.
