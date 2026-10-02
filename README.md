# OAU EEE Student Records & Identification System

A departmental student filing system for the Electrical and Electronic Engineering project at Obafemi Awolowo University (OAU). It will organise student files and academic records, with a controlled interface to a separate student identity terminal.

## Project status

This repository currently contains the initial directory scaffold and documentation. There is no runnable application, dependency configuration, database schema, or implemented terminal API yet. `pyproject.toml` and `.env.example` are placeholders.

The software design and delivery plan (SW-PLAN-01, version 0.1, 29 September 2026) informs this overview. Its architecture, stack, roles, assignments, schedule, and hosting choices are proposals pending review; this repository does not establish institutional approval.

## Intended first release

- Let authorised staff search for students and view permitted biodata and academic records by session and semester.
- Stage imports, validate identities and conflicts, preview changes, and review data before accepting it into the departmental dataset.
- Generate permission-controlled result exports with source and review information.
- Explain outstanding course requirements while preserving repeats, exemptions, substitutions, and unknown or incomplete inputs.
- Demonstrate an authenticated identity workflow using a simulated terminal before physical integration.
- Record sensitive changes, reviews, identity outcomes, and exports in an audit trail.

Public registration, student or guardian accounts, payments, attendance, SMS campaigns, mobile apps, smart cards, automated graduation decisions, and automated ePortal scraping are outside the proposed first release. A student record does not imply a login account.

## Proposed architecture

A modular Django application would serve staff pages and a small, versioned JSON API. PostgreSQL would store academic records, provenance, and minimal identity events. Larger imports and exports could later use durable background jobs.

| Component | Proposed technology |
| --- | --- |
| Backend | Python and Django |
| Database | PostgreSQL |
| Staff interface | Django templates, HTML/CSS, Bootstrap, limited JavaScript; optional HTMX |
| Terminal interface | Django REST Framework, REST/JSON |
| Collaboration | GitHub issues and pull requests; CI to be added |

Exact runtime and dependency versions will be selected and recorded when implementation begins.

Fingerprint capture, biometric templates, and matching belong to the separate biometric subsystem. A successful identity match must not automatically grant access to academic records. The terminal contract should exchange only the information required for the authorised identity workflow.

## Repository layout

The current scaffold places application and support folders at the repository root:

```text
app/
  config/           Application settings and routes
  accounts/         Staff accounts and access policies
  students/         Student records, guardians, and source ownership
  academics/        Periods, curricula, registrations, and results
  imports/          Staging, validation, reconciliation, and adapters
  reporting/        Permission-controlled reports and exports
  identity/         Device registry and terminal API
  audit/            Sensitive-action audit events
  templates/        Shared layouts and staff pages
  static/           Styles and browser scripts
contracts/
  identity-v1/      Proposed terminal schemas and examples
simulators/
  terminal/         Mock identity terminal
  receiver/         Mock integration receiver
fixtures/
  synthetic/        Non-personal development and test data
tests/             Contract, end-to-end, integration, performance,
                    permissions, and recovery checks
deployment/        Build and deployment configuration
docs/              Data dictionary, decisions, setup, and runbooks
software/          Reserved placeholder; purpose to be agreed
.env.example        Future environment-variable template
pyproject.toml      Future Python project/dependency configuration
```

The plan illustrates these software folders beneath `software/`; the existing scaffold uses root-level folders instead. Agree a canonical layout before implementation. Empty directories contain `.gitkeep` files so Git preserves them.

## Getting started

Clone this repository and open its root in your editor. Review the scope and module boundaries before adding code.

There are no install, migration, server, or test commands yet. Once the application is bootstrapped, document the supported Python version, dependency installation, local database setup, environment variables, synthetic fixtures, and test commands here. Do not treat the empty configuration files as a working setup.

## Data and access boundaries

- Use synthetic data for development, demonstrations, fixtures, and initial staging.
- Keep real student records, guardian contacts, biometric material, credentials, import/export files, and database backups out of Git.
- Keep secrets in local environment variables or an approved secret store. Commit only non-secret examples.
- Enforce staff role, cohort, and field restrictions on the server, including direct API requests and exports.
- Preserve source ownership, academic history, review state, and correction provenance. Missing results must not be interpreted as automatic failure.
- Confirm an authorised university data-access route and applicable operational decisions before live integration or use.

## Initial delivery priorities

1. Confirm staff workflows, the field dictionary, access rules, and reviewer authority.
2. Review the proposed stack and repository layout, then record accepted decisions in `docs/`.
3. Define synthetic student, curriculum, registration, and result fixtures.
4. Agree the terminal request/outcome contract and its failure semantics.
5. Build a login-to-student-record workflow with access and audit checks.
6. Add staged imports, safe re-import, and period-specific exports.
7. Verify expiry, replay protection, device revocation, recovery, and staff usability before a supervised pilot.

## Filing-system decisions

Before implementing document storage, agree file categories, reference numbers, permitted file types and sizes, upload/download permissions, revision and correction history, retention and archive rules, and backup recovery. Use private storage with server-side access checks; define validation and malware scanning before accepting uploaded documents.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for branch, review, validation, and data-handling rules. Use a branch for each focused change and submit a pull request describing the behaviour, validation performed, and any unresolved decisions. Keep documentation and contracts aligned with implementation. Changes to academic rules, access policies, and data-source assumptions require review by the appropriate project or departmental owner.

No software licence has been selected yet. Record the agreed licence and repository ownership before broader distribution.
