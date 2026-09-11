# 028 - Show which Session will execute SQL

- Repo: dbridge.nvim
- Status: deferred
- Change: none
- Origin: Legacy backlog 6; retained from revision `80d71d4`.

## Problem / opportunity

The client reportedly tracks the last-touched Session but does not display the target of its execution command.

## Desired outcome

Make the active Session visible and keep the indicator consistent with execution targeting and disconnects.

## Notes and references

Recheck get_active_session and the explorer/results UI in the client repository.
