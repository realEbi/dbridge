## ADDED Requirements

### Requirement: Keep refresh authoritative under concurrent requests

When introspection requests on a Session run concurrently with
`dbridge/refreshSchema`, a result whose fetch from the Adapter began before the
refresh SHALL NOT be stored in the cache after the refresh. Such a result MAY still be
returned to the request that fetched it. The first introspection request for a Scope
Path that begins after the refresh reply SHALL fetch fresh data from the Adapter. A
cancelled introspection request SHALL NOT store a result in the cache.

#### Scenario: Slow listing overlaps a refresh
- **WHEN** a table listing for a Scope Path is being fetched, the client calls
  `dbridge/refreshSchema` before that fetch finishes, and a table is created in that
  Scope Path before the refresh
- **THEN** the next table listing for that Scope Path sent after the refresh reply
  includes the new table

#### Scenario: Cancelled listing leaves no cache entry
- **WHEN** a table listing is cancelled before it finishes
- **THEN** the next listing for that Scope Path fetches from the Adapter
