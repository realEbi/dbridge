## Purpose

Define clean and repeatable type and lint checks for the shipped server and its tests, with failures visible locally and in CI.

## ADDED Requirements

### Requirement: Static checks cover the supported code scope

The documented type check SHALL analyze `src/dbridge` and `tests` while excluding unregistered parked adapters from recursive discovery. Ruff SHALL check source and tests, including parked source, without requiring optional adapter drivers. Both commands SHALL exit successfully with no existing findings.

#### Scenario: Current server and tests are checked
- **WHEN** a developer runs the documented type and lint checks
- **THEN** supported server code and tests are checked with zero findings
- **AND** missing drivers and stale imports in unregistered parked adapters do not require installation or type-error suppression for shipped modules

### Requirement: CI reports static-check failures

Existing pull-request and integration-branch CI jobs SHALL run the type and lint checks alongside the coverage-gated suite, preserving the existing matrix job names and the 85% coverage floor. A finding from either static check SHALL fail the job.

#### Scenario: Pull request contains a static-check regression
- **WHEN** a pull request introduces a mypy or Ruff finding in checked code
- **THEN** the existing matrix job reports failure from the corresponding check

#### Scenario: Clean change retains coverage enforcement
- **WHEN** type and lint checks pass
- **THEN** the job still runs the server suite with the existing coverage threshold
