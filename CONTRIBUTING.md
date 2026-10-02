# Contributing

## Access and data

Use individual GitHub accounts. Repository collaboration does not grant access to live student records, the running filing system, or production credentials. Use synthetic data in development, tests, examples, issues, and pull requests. Do not attach real student files, screenshots, biometric material, secrets, or database backups.

Keep private working data in ignored directories. Review staged files before committing: .gitignore does not inspect content or remove already tracked files. Report accidental credential disclosure privately to the repository owner immediately; rotate the credential before addressing Git history.

## Branches and pull requests

Create short-lived branches from main: feat/<topic>, fix/<topic>, docs/<topic>, or chore/<topic>. Link an issue or explain the purpose in the pull request. Keep changes focused, describe validation, and update related documentation and API contracts.

The team policy is two approvals from reviewers other than the author, passing applicable checks, and resolved review conversations before merging. Reviewers should re-review changed code after additional pushes. Permissions, data imports, academic rules, identity, and deployment changes need a reviewer familiar with that area. Record stakeholder approval separately when a change alters agreed departmental rules.

Do not push directly to main, force-push main, or delete it. Use squash merging and remove merged feature branches. Emergency exceptions require a recorded reason, named responsible maintainer, validation, and subsequent review.

## Current enforcement status

As of 2 October 2026, GitHub reports that the private repository must upgrade to GitHub Pro to enable branch protection. The review and main-branch rules above are team policy and are not enforced by GitHub yet. Squash-only merging and automatic deletion of merged branches are configured; auto-merge is disabled.

After protection becomes available, configure main to require pull requests, two approvals, dismissal of stale approvals, resolved conversations, passing CI checks, and enforcement for administrators. Disable force pushes and deletion. Select required check names only after a working workflow has produced them.

Named module owners and CODEOWNERS will be added once reviewer usernames and responsibilities are agreed. Only the repository owner is currently listed as a collaborator; invitations require the intended contributors' GitHub usernames.

## Validation

Before committing, inspect git diff and git diff --cached, run git diff --check, and run relevant checks that exist for the change. Once Python tooling is established, add formatting, linting, secret detection, and quick tests to local pre-commit hooks. Hooks can be bypassed; repeat necessary checks in CI.

Before merging, reviewers must inspect behaviour, data boundaries, documentation, and validation evidence. Do not label checks as passing if they were not run. Documentation-only changes need spelling, link, and diff review; they do not need invented application tests.

The current scaffold has no runnable application, dependencies, or test commands. Once Django is bootstrapped, add GitHub Actions for formatting/linting, secret detection, application tests against PostgreSQL, and missing-migration checks. Test denied access, authorised downloads, file validation and revision history, safe re-import, period-specific exports, and identity expiry/replay. Add regression tests for substantive bug fixes.

Review schema migrations for data preservation and rollback implications. Commit migration files and agreed dependency lockfiles. Never use live data or production credentials in CI. Restrict workflow permissions and review workflow changes carefully.

## Development and releases

Use separate development, CI, staging, and production databases and credentials. Development, CI, and initial staging use synthetic data. Production requires the agreed institutional authorisation, an operational owner, tested backups and recovery, and a rollback plan.

No GitHub deployment environments or Codespaces configuration are created yet: the scaffold is not runnable and no deployment target is selected. Add a reproducible local setup first. Codespaces is optional and must use synthetic data and an agreed spending limit.

Before the live filing-system pilot, agree file categories, reference numbering, upload limits and allowed formats, server-side access controls, malware scanning, correction/version history, retention/archive rules, and backup restore procedures. Document accepted choices in docs/.
