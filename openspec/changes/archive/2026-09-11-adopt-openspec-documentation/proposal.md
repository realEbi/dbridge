## Why

The documentation mixes the implemented synchronous server with a future async
design and obsolete phase plans. A single OpenSpec workflow and explicit document
ownership will keep current behavior, future direction, and deferred work distinct.

## What Changes

- Document the verified current architecture separately from the future roadmap.
- Replace the monolithic backlog with an index and one file per deferred item,
  preserving unresolved ideas from the backlog and original design.
- Delete the original design, Superpowers plans, completed phase PRDs/issues, and
  retired skill-routing documents after preserving their useful content.
- Update AGENTS.md, README, the glossary, ADR-0001, and the manual testing guide.
- Configure the standard OpenSpec workflow and document which files change during
  planning, implementation, verification, and completion.

## Capabilities

### New Capabilities

None. This change reorganizes project documentation and workflow configuration.

### Modified Capabilities

None. Set `skip_specs: true`; the server's public behavior remains unchanged.

## Impact

Documentation, OpenSpec configuration, and this change's artifacts only. No runtime
code, dependencies, CI behavior, or files in client repositories change. Git
history retains the deleted documents, whose pre-migration revision is `80d71d4`.
