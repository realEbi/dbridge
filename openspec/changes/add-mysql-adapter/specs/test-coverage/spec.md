## MODIFIED Requirements

### Requirement: Coverage measures the shipped server only

Coverage measurement SHALL cover the `src/dbridge` package and nothing else.
Test modules MUST NOT contribute to the measured totals, because a test file
scores near 100% by construction and inflates the result without saying anything
about the server.

Adapter modules that are parked — present in the tree but absent from the
adapter registry, and depending on drivers outside the default install — SHALL
be excluded from measurement while they remain parked. Exclusion is a statement
about their registration status, not an assertion that they are tested.

Adapter modules that are optional SHALL also be excluded from measurement.
An optional Adapter is registered, but its driver is installed only through a
package extra and its behavior can be verified only against an external database
server. The registry code that loads an optional Adapter and reports a missing
extra SHALL stay measured. Each optional Adapter SHALL have a real-server test
suite that is skipped unless a server is configured, with a documented command to
run it locally. Exclusion does not assert that the Adapter is tested in CI.

#### Scenario: Test modules are outside the measurement

- **WHEN** the coverage report is generated
- **THEN** no file under `tests/` appears as a measured file in the report
- **AND** the reported total is computed only from `src/dbridge` modules

#### Scenario: Parked adapters are outside the measurement

- **WHEN** the coverage report is generated and the PostgreSQL and Snowflake
  adapters are still absent from the adapter registry
- **THEN** those adapter modules do not appear in the report
- **AND** their absence does not change the reported total

#### Scenario: A registered adapter is measured

- **WHEN** a previously parked adapter is registered so `dbridge/connect`
  accepts its name, and its driver is part of the default install
- **THEN** that adapter's module is included in the measurement from that point
  on and counts toward the enforced minimum

#### Scenario: An optional adapter is outside the measurement

- **WHEN** the coverage report is generated
- **THEN** the MySQL Adapter module does not appear in the report
- **AND** the registry's handling of a missing `mysql` extra is measured

#### Scenario: Optional adapter suite without a server

- **WHEN** the suite runs with no MySQL server configured
- **THEN** the MySQL real-server tests are reported as skipped, not failed
- **AND** the coverage gate result is unaffected
