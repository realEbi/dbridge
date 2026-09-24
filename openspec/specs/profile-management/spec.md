# profile-management Specification

## Purpose

Define how clients create, update, and rename persisted Profiles through
`dbridge/saveProfile`, so that edits never leave duplicate or silently overwritten
Profiles in the server-owned Profile file.

## Requirements

### Requirement: Save a Profile by name

`dbridge/saveProfile` SHALL take `name`, `adapter`, an optional `config` defaulting
to an empty object, and an optional `previous_name`. When `previous_name` is absent
or equals `name`, the server SHALL store the Profile under `name`, replacing any
Profile already stored under that name and leaving other Profiles unchanged, and
SHALL reply `{ok: true}`. Saving a Profile SHALL NOT create, change, or close a
Session.

#### Scenario: Create a Profile
- **WHEN** a client saves Profile `a` and no Profile `a` exists
- **THEN** `dbridge/listProfiles` includes `a` with the saved adapter and config

#### Scenario: Update a Profile in place
- **WHEN** a client saves Profile `a` with a new config and no `previous_name`
- **THEN** `a` has the new config and every other Profile is unchanged

#### Scenario: Live Session keeps its configuration
- **WHEN** a Session was connected from Profile `a` and a client then saves `a` with
  a different config
- **THEN** the Session remains usable with the configuration it connected with

### Requirement: Rename a Profile atomically

When `previous_name` is present and differs from `name`, the server SHALL remove the
Profile stored under `previous_name` and store the saved definition under `name` in
a single update of the Profile file, then reply `{ok: true}`. After a successful
rename, `dbridge/listProfiles` SHALL contain `name` and SHALL NOT contain
`previous_name`. `previous_name`, when present, SHALL be a nonempty string;
otherwise the request SHALL fail with `INVALID_REQUEST`.

#### Scenario: Rename and edit together
- **WHEN** Profile `old` exists, no Profile `new` exists, and a client saves `new`
  with a changed config and `previous_name` `old`
- **THEN** `listProfiles` contains `new` with the changed config and does not
  contain `old`

#### Scenario: Other Profiles are untouched
- **WHEN** Profiles `old` and `other` exist and a client renames `old` to `new`
- **THEN** `other` is unchanged

### Requirement: Reject a rename that would lose a Profile

A rename SHALL fail without changing the Profile file when `name` is already used by
another Profile, replying with `PROFILE_ALREADY_EXISTS` (-32007) and a message that
names the Profile. A rename SHALL fail without changing the Profile file when no
Profile is stored under `previous_name`, replying with `PROFILE_NOT_FOUND` (-32006).

#### Scenario: Rename onto an existing Profile
- **WHEN** Profiles `old` and `taken` exist and a client saves `taken` with
  `previous_name` `old`
- **THEN** the request fails with `PROFILE_ALREADY_EXISTS` and both Profiles keep
  their previous definitions

#### Scenario: Rename from a missing Profile
- **WHEN** no Profile `ghost` exists and a client saves `new` with `previous_name`
  `ghost`
- **THEN** the request fails with `PROFILE_NOT_FOUND` and no Profile `new` is created

#### Scenario: Empty previous name
- **WHEN** a client saves a Profile with `previous_name` set to an empty string
- **THEN** the request fails with `INVALID_REQUEST` and the Profile file is unchanged
