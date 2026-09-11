# test-coverage Specification

## Purpose

Defines how the project measures test coverage of the dbridge server: which code
counts toward the measurement, the minimum the suite must sustain, and where that
minimum is enforced. It exists so a reported coverage number describes the
shipped server rather than the test files, and so a regression fails a check
instead of passing quietly.

## Requirements

### Requirement: Coverage measures the shipped server only

Coverage measurement SHALL cover the `src/dbridge` package and nothing else.
Test modules MUST NOT contribute to the measured totals, because a test file
scores near 100% by construction and inflates the result without saying anything
about the server.

Adapter modules that are parked — present in the tree but absent from the
adapter registry, and depending on drivers outside the default install — SHALL
be excluded from measurement while they remain parked. Exclusion is a statement
about their registration status, not an assertion that they are tested.

#### Scenario: Test modules are outside the measurement

- **WHEN** the coverage report is generated
- **THEN** no file under `tests/` appears as a measured file in the report
- **AND** the reported total is computed only from `src/dbridge` modules

#### Scenario: Parked adapters are outside the measurement

- **WHEN** the coverage report is generated and the MySQL, PostgreSQL, and
  Snowflake adapters are still absent from the adapter registry
- **THEN** those adapter modules do not appear in the report
- **AND** their absence does not change the reported total

#### Scenario: A registered adapter is measured

- **WHEN** a previously parked adapter is registered so `dbridge/connect`
  accepts its name
- **THEN** that adapter's module is included in the measurement from that point
  on and counts toward the enforced minimum

### Requirement: The suite sustains a minimum coverage level

The server test suite SHALL sustain at least 85% statement-and-branch coverage
over the measured scope. The verification command MUST fail when measured
coverage falls below that minimum, so a drop is reported as a failure rather
than as a number a reader has to notice.

The minimum is a floor, not a target. A change that lands the suite exactly at
the floor leaves no room for the next change, so the suite SHALL be kept
meaningfully above it.

#### Scenario: Coverage at or above the minimum

- **WHEN** the suite is run with coverage enabled and measured coverage is 85%
  or higher
- **THEN** the command reports the coverage total and exits successfully

#### Scenario: Coverage below the minimum

- **WHEN** the suite is run with coverage enabled and measured coverage is below
  85%
- **THEN** the command exits with a failure
- **AND** the output identifies the measured total and the minimum it missed

#### Scenario: Every test passes but coverage regressed

- **WHEN** all tests pass and a change has removed tests or added unmeasured
  code such that coverage drops below the minimum
- **THEN** the run still fails, and the failure is attributed to coverage rather
  than to a failing test

### Requirement: Coverage is reportable on demand

A developer SHALL be able to generate a coverage report locally with a
documented command, in both a terminal summary form and a browsable form that
identifies the uncovered lines of each module. Generating a report MUST NOT
require network access, credentials, or a database server.

#### Scenario: Terminal report

- **WHEN** a developer runs the documented coverage command
- **THEN** a per-module summary is printed showing statements, misses, branch
  coverage, and the uncovered line numbers, followed by the overall total

#### Scenario: Browsable report

- **WHEN** a developer runs the documented command for a browsable report
- **THEN** a local report is written that shows each measured module's source
  with covered and uncovered lines distinguished
- **AND** the generated report files are ignored by version control

### Requirement: Coverage is enforced on pull requests

The minimum SHALL be enforced automatically on every pull request, regardless of
which branch it targets, not only when a developer runs the suite locally. The
check MUST run the server suite with coverage enabled on the Python versions the
project supports, and MUST report the coverage total in its output.

Enforcement MUST NOT be filtered by base branch. There is no branch where a
coverage regression is acceptable, and a base-branch filter means a pull request
into any unlisted branch skips the gate silently.

The check SHALL block the merge when it fails. A check that reports a failure a
reviewer is free to merge past is a notification, not a guard, so the check MUST
be registered as a required status check on whichever branch integrates work. A
pull request whose coverage falls below the minimum MUST NOT be mergeable until
coverage is restored.

#### Scenario: Pull request meeting the minimum

- **WHEN** a pull request is opened or updated and the suite passes with
  coverage at or above the minimum on every supported Python version
- **THEN** the check reports success and the coverage total is visible in its
  output
- **AND** the pull request is mergeable as far as this check is concerned

#### Scenario: Pull request below the minimum

- **WHEN** a pull request is opened or updated and coverage falls below the
  minimum on any supported Python version
- **THEN** the check fails for that version
- **AND** the pull request is reported as not mergeable while that failure stands

#### Scenario: Coverage regression cannot be merged past

- **WHEN** a pull request's coverage check has failed and a reviewer approves the
  pull request anyway
- **THEN** the merge is still refused, because the failing check is required
  rather than advisory

#### Scenario: Pull request into a non-default branch

- **WHEN** a pull request targets an integration branch other than the default
  branch
- **THEN** the coverage check still runs and still gates that pull request

#### Scenario: Direct push to an integration branch

- **WHEN** a commit is pushed directly to an integration branch
- **THEN** the same coverage check runs on that branch, so a change that bypasses
  the pull-request path is still measured

#### Scenario: Release workflow is unaffected

- **WHEN** a tag is pushed
- **THEN** the existing build-and-publish workflow runs as before, unchanged by
  the pull-request check

### Requirement: Behavior verified through a subprocess is measured in process

End-to-end tests that exercise the server by spawning it as a separate process
verify real behavior but contribute nothing to coverage, because the measured
run and the server run are different processes. Every behavior those tests
depend on SHALL also be exercised by an in-process test, so the measured total
reflects the behavior the suite actually verifies.

End-to-end subprocess tests SHALL be retained. They are the only checks that
prove the stdio entry point, framing, and process lifecycle work together for a
real client; in-process tests supplement them rather than replace them.

#### Scenario: Entry point and transport loop are measured

- **WHEN** the coverage report is generated
- **THEN** the server entry point and the stdio serve loop are reported as
  covered, having been driven in process over controlled streams rather than
  only through a spawned process

#### Scenario: End-to-end tests remain

- **WHEN** the suite runs
- **THEN** the end-to-end tests that spawn the server as a subprocess still run
  and still pass, and terminate the process they spawned
