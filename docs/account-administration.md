# Account settings and department administration

Open **Account settings** beneath the username/avatar. It is separate from the
workspace navigation. Every signed-in user can change their own password there;
the HOD also has staff accounts, part-adviser assignments and HOD transfer.
Student logins are issued from the individual record under **Students**, where
the HOD creates a private link for the student to choose a password; see
[student first-login setup](student-accounts.md).

## Staff accounts

The HOD can create staff accounts and edit ordinary staff names, email, active
status and the direct permissions shown in the permission catalogue. Initial
passwords are entered privately and checked by Django's password validators.
They are never returned, stored in browser storage or recorded in the audit.
Creation does not send an email or force a password change at first sign-in.

The permission catalogue is limited to student/guardian access, result viewing,
creation/correction/verification, existing attendance tasks and adviser messages.
These forms cannot grant HOD status, arbitrary authentication permissions or
change student accounts. Group-derived permissions and grants outside this
catalogue remain intact; inherited permissions are displayed separately.

The current HOD and other HOD accounts cannot be deactivated or edited through
the ordinary staff form. HOD status changes use the transfer workflow below.
Deactivation keeps the account and its history while preventing sign-in.

## Part-adviser assignments

Select a staff member, a recorded academic session and an academic level. The HOD
can assign, reassign or deactivate the assignment. Staff permissions and adviser
scope are separate: give the staff member the required task permissions as well
as the assignment. Duplicate staff/session/level assignments are rejected.

Unknown students from a master-sheet result upload are still registered
separately in **Students**. These administration controls do not change the
results-only import workflow.

## Transfer HOD responsibility

Choose another existing, active ordinary staff account with a usable password.
The reviewer sees who will gain HOD access and who will lose it, types the new
HOD's exact username, enters their own current password and acknowledges the
handover before submitting. The target cannot be the caller, an existing HOD or
an account linked to a student.

The server rechecks current HOD authorization and both accounts under row locks.
It promotes the selected staff member and demotes the current HOD atomically;
the former HOD remains active as staff. Existing accounts, assignments and
academic history retain their identities. Other existing HOD accounts are not
changed. The portal refreshes the caller's current role and removes HOD controls.

If the response is uncertain, department controls lock and the portal reads the
current account status. It does not resend the transfer. Confirm the resulting
HOD status before making any further ownership change.

Staff changes, assignment changes and HOD transfers have credential-free audit
records with the actor, target, before/after values and time. These endpoints use
the existing session authentication and CSRF checks and are HOD-only.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/accounts/administration-options/` | Grantable permissions and recorded/current sessions |
| GET / POST | `/api/accounts/staff/` | Paginated staff search or staff creation |
| PATCH | `/api/accounts/staff/{id}/` | Edit an ordinary staff account |
| GET / POST | `/api/accounts/adviser-assignments/` | Paginated assignments or a new assignment |
| PATCH | `/api/accounts/adviser-assignments/{id}/` | Reassign, edit or deactivate an assignment |
| POST | `/api/accounts/transfer-hod/` | Explicit, reauthenticated HOD transfer |

Staff input uses `permission_codes` for managed direct permissions. Assignment
input uses `staff_id`, `academic_session`, `level` and `is_active`. Transfer input
uses `target_staff_id`, `expected_target_username`, `current_password` and
`confirmation: "TRANSFER HOD"`. Credentials are write-only. Responses expose
safe staff identity and permission information only to the current HOD.

## Database update

Apply `accounts.0005_accountadministrationaudit` from the configured Aiven
terminal after stopping the local app. `scripts/update-local.ps1` creates a
private backup, verifies restoration in a disposable local database, applies
pending migrations and restarts the app. This migration adds an audit table;
it does not transfer HOD status, create staff or change existing assignments.
No real HOD transfer is part of implementation verification.

## Validation — 22 October 2026

The complete backend suite passed **447 tests on PostgreSQL 18.6** in 223.525
seconds, including competing HOD transfers and observed contention between
assignment editing and HOD messaging. System checks and migration drift passed.
The stopped synthetic cluster/logs remain in `tmp/attendance-postgres-xmfqict0`.

The portal passed **63 tests**, ESLint and the production build. Checks include
HOD-only controls, strict staff payloads, permission/group distinctions, adviser
assignment fields, exact transfer confirmation, uncertain-response recovery and
the former HOD remaining on their ordinary staff account page.

Browser checks used synthetic accounts: the profile link opens Account settings;
section shortcuts expose staff, adviser and transfer forms; target selection
shows the handover summary and requires username, password and acknowledgement.
No ownership or staff change was submitted. Mobile account controls fit within
the page; data tables scroll within their regions. Proof images are in
`output/local-integration/account-handover-preview.png` and
`output/local-integration/portal-account-mobile.png`.

On 22 October 2026 the user confirmed that, after the update/restart, Account
settings beneath the profile identity shows Staff accounts, Part-adviser
assignments and Transfer HOD responsibility. This records user-confirmed laptop
activation; the agent did not access the private Aiven terminal or perform a
real HOD transfer.
