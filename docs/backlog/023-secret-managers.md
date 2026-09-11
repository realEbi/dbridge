# 023 - Reference secrets from Profiles

- Repo: dbridge
- Status: deferred
- Change: none
- Origin: Original design question 3 (medium priority in the legacy backlog); retained from revision `80d71d4`.

## Problem / opportunity

Profiles currently hold plain configuration data. The original design raised secret-manager integration as an option.

## Desired outcome

Decide whether and how Profiles reference 1Password, AWS Secrets Manager, or other providers, including resolution failures and redaction.

## Notes and references

Inspect [Profiles](../../src/dbridge/config/profiles.py). Keep saved configuration distinct from live Sessions.
