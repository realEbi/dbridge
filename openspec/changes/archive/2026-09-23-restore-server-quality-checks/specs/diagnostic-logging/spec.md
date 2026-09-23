## Purpose

Keep server diagnostic output useful across repeated Session and Adapter creation without corrupting framed protocol output.

## ADDED Requirements

### Requirement: Repeated logger setup does not duplicate diagnostics

For a named logger without preconfigured handlers, repeated setup and Adapter construction SHALL retain one console handler and emit an enabled diagnostic record once to stderr. It MUST NOT emit that record to stdout.

#### Scenario: Several Adapters share the server logger
- **WHEN** several Adapters are constructed and one enabled diagnostic is logged
- **THEN** the server logger has one console handler and the message appears once on stderr and never on stdout

#### Scenario: Logging level changes
- **WHEN** the same named logger is requested again with a different supported level
- **THEN** its existing console handler observes the new logger level without adding another handler

### Requirement: Explicit handler configuration is preserved

Logger setup SHALL preserve handlers already installed directly on a named logger and SHALL NOT add a duplicate console handler alongside them.

#### Scenario: Embedding application supplies a handler
- **WHEN** an application installs a handler before requesting the named logger
- **THEN** setup retains that handler and adds none
