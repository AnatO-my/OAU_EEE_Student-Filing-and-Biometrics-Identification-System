# Continuation handoff — 5 October 2026

Workspace: C:/Users/Ot/Downloads/EEE-Project. User is learning Django and prefers one small code step at a time, with setup versus core-tool work explicitly labelled. Verify actual files rather than assuming every pasted step was applied. User wants documentation and periodic GitHub checkpoints. No proactive subagents. Do not apply migrations to the development/shared database until its schema is reconciled.

## Decisions

Backend Django/PostgreSQL, separate React frontend maintained by teammate. Keep app/ as backend. accounts.User extends AbstractUser for staff AND students. HOD is the active superuser and manages accounts/permissions/assignments in Django admin. Ordinary staff use React. Student accounts are nonstaff and link one-to-one to Student. Students can view their own details and receive both individual adviser messages and announcements to their level.

Student UUID remains stable; identifier_type is matriculation or utme and identifier_value is unique text. Format/case rules pending. Required phone, admission year, UTME/direct-entry/transfer admission mode, explicitly maintained current level. Guardian model supports multiple contacts with required name/relationship/phone and optional email/address. GPA/CGPA derived from academic results, not profile inputs. Fingerprint matching will be server-side/separate subsystem; academic score and fingerprint_score separate.

## Implemented

GET /api/students/ with search, validated filters, 20-row pages; GET /api/students/{UUID}/; GET /api/me/student/ read-only linked profile. Staff reads require view_student plus active AdviserAssignment for CURRENT_ACADEMIC_SESSION and student's current_level; HOD bypasses scope. Absent session grants no ordinary staff records. Revocation, past sessions and out-of-scope detail are tested. Guardian serializer exists, no guardian API yet.

AdviserAssignment unique staff/session/level; validates consecutive YYYY/YYYY, staff account and positive level in clean. Direct save does not invoke clean. AdviserMessage stores audience/assignment/subject/body/timestamp/explicit recipient links. No sending or recipient-reading endpoints yet. Recipients persist when level changes. Preserve recipient snapshot when sending level announcements.

setup_staff_groups command sets Student Readers view and Student Editors view/add/change for student/guardian. Run only after migrations. HOD-only User/Student/Guardian admin screens close the API-scope bypass; assignment admin allows HOD create/edit/deactivate, no deletion. Default auth Group admin uses Django permission controls.

Newer main work has been merged into this checkpoint: staff-only JSON auth endpoints /api/auth/csrf/, login/, logout/, me/. Explicit session-login CSRF protection was added during review: obtain token before login and refresh after login. Student credentials still rejected by LoginSerializer; adapt auth for student accounts in a deliberate next step, with end-to-end session/CSRF tests. Current user response has groups but not explicit permission/action list. React browser integration, password change/recovery, CORS/proxy deployment configuration pending.

Migrations: accounts 0001 custom user, 0002 assignment/message/constraint; students 0001 profile, 0002 guardian, 0003 user link. Development migrations have not been applied by this work. Test settings use isolated in-memory SQLite; CI uses PostgreSQL 16.

## Verification

Run .venv/Scripts/python.exe app/manage.py check
Run .venv/Scripts/python.exe app/manage.py makemigrations --check --dry-run
Run .venv/Scripts/python.exe app/manage.py test students accounts --settings=config.test_settings
Do not rely on the historical test count; inspect actual current results. GitHub workflow runs the same suite on PostgreSQL.

## Teammate repository and pending integration

https://github.com/Futurescholar/department inspected read-only via gh. Django portal contains Student/Course/Result/SemesterGPA/Guardian/StudentFile/CourseRegistration/AcademicCalendar, migrations, default auth users and Django template views. Repository does not prove deployed database state. It tracks .env; do not read or expose credentials. Preserve our custom user, identifiers, guardian details, JSON API, and permission/scope design. Reconcile existing schema/data before any database migration.

services.recalculate_gpa_and_cgpa uses Decimal weighted points/credit units by session/semester and overall, rounded HALF_UP to two decimals. models.grade_point_for assumes 70/60/50/45/40 boundaries on five-point scale; verify institutional rules. Adapt rather than copy blindly: no-results should be null, repeats/exemptions/incomplete results need policy, credit-unit history needs preservation, all correction/deletion paths must recalculate, stale semester summaries must be removed. Existing surname-first-login backend should not be adopted.

## Next steps

1. Review current checkpoint PR and actual code; merge only per repository review policy.
2. Decide shared PostgreSQL integration after teammate confirms deployed schema/data and authority for migrations.
3. Implement secure message sending service with both audience modes, action permission, active current assignment, recipient scope, and atomic persistence; add tests before API exposure.
4. Add student message list/detail bound to logged-in profile, with isolation tests.
5. Adapt session auth/current-user/logout for student accounts; test CSRF and browser integration.
6. Add student/guardian writes, scoped exports, audit, account recovery, and academic models/rules.

Unrelated untracked docs, fonts, handbook and output artifacts were intentionally excluded from checkpoint commits. Check status before staging. Keep real secrets/data out of Git. See CONTRIBUTING.md and docs/backend-foundation.md.


## Latest reconciliation update

Read docs/backend-foundation.md, final reconciliation section, before continuing. Root manage.py is canonical; app/manage.py delegates. Teammate portal preserved in legacy/teammate_portal and not active. Student session auth integrated from student-auth branch. Adviser sending, student inbox, HOD sending (adviser/individual/level), and isolated HOD inbox are implemented with 62 local tests. HODAssignment was replaced by sender-based HODMessage; HOD needs no adviser assignment. Do not repeat the obsolete pending-work statements above for implemented endpoints. Shared database reconciliation/migration, account recovery, student/guardian writes, audit, exports and academic integration remain pending. Check current CI/PR status and Git state before changing files. No development database migration was applied.
