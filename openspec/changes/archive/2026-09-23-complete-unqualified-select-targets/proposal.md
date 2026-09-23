## Why

Unqualified completion after a SELECT comma returns keywords even when the FROM
clause identifies available columns (backlog 018), while a bare SELECT returns
nothing (backlog 053). These gaps interrupt normal SQL editing after the recent
qualified-column fix and are a bounded part of roadmap milestone 4.

## What Changes

- Complete unqualified column positions throughout the current SELECT target
  expressions, including commas, typed prefixes, and explicit cursor positions.
- Restrict physical table discovery for those positions to the cursor's SELECT.
- Use dialect keywords when no physical source can be resolved, including bare
  SELECT, without scanning all tables for columns.
- Preserve the existing DSP request/result shape and qualified completion.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sql-completion`: Add unqualified SELECT target and source-free fallback contracts.

## Impact

The dbridge server owns implementation and DSP behavior. The companion
[replace-unqualified-column-completions](https://github.com/realEbi/dbridge.nvim/tree/dbridge-2.0/openspec/changes/archive/2026-09-23-replace-unqualified-column-completions)
change in dbridge.nvim owns safe whole-identifier acceptance for the newly offered
columns. The DSP completion item shape is unchanged; existing clients remain
compatible, while the updated Neovim source avoids duplicated unqualified suffixes. Core completion, tests,
README, architecture, manual guide, roadmap, and backlog 018/053 change. Cross-repo
verification exercises the updated Neovim source and actual nvim-cmp against this server.
CTE/derived projection inference and outer references (055), ranking and duplicate
label policy (017), and the legacy unqualified WHERE path remain out of scope.
