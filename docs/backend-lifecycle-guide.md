# Graduation, guardians, export and account lifecycle

Current backend contract: 7 October 2026. All paths start with /api/.
HOD means an active staff superuser. Django remains the authentication authority;
React displays the API and never decides authorization. These additions retain
our custom User, Student identifiers and multiple-guardian models.

## HOD-reviewed graduation

The initial approach is explicit HOD review, not inferred department rules. For
each student the HOD records the complete required course-offering list, checks
all other official graduation requirements and approves the current history.
The system cannot discover a required course that the HOD omitted from this list.
Warnings and automatic curriculum/credit/pass requirements await agreed rules.

1. Record each required offering with POST
   students/<uuid>/course-requirements/:

```json
{"offering":1,"resolution":"result","reason":""}
```

GET lists requirements; GET/PATCH course-requirements/<id>/ retrieves or edits
one. The student and recorded_by fields are read-only. An offering can occur
only once per student. A result resolution requires a recorded result for that
offering. For a reviewed transfer or exemption, use resolution transfer or
exemption and a nonempty explanation. These resolutions explain an absent local
result; they create neither invented grades nor CGPA credit units. The HOD checks
whether actual course passes and all other requirements are satisfied.

2. Ensure every saved result has a score and is verified. All saved attempts,
   including failed and repeated attempts, count with their saved units/scale.
   At least one result is required; the unrounded CGPA must be >=1.00.
3. GET students/<uuid>/graduation-review/ for the CGPA and history_digest.
   An incomplete or numerically ineligible history returns 400. It also returns
   review_current and the last review, if present.
4. POST the approval to the same path, copying the preview digest:

```json
{"expected_digest":"COPY_THE_64_CHARACTER_PREVIEW_DIGEST","history_complete":true,"other_requirements_satisfied":true,"notes":"Reviewed complete history and official graduation requirements."}
```

Both attestations must be true. The review records HOD, time, notes, CGPA and the
history fingerprint. A stale preview is rejected. This stores the latest review;
it is not an immutable audit log. Approval alone does not change academic status.

5. PATCH students/<uuid>/ with {"academic_status":"graduated"}, or POST
   students/bulk-status-change/:

```json
{"student_ids":["STUDENT_UUID_1","STUDENT_UUID_2"],"expected_status":"undergraduate","academic_status":"graduated"}
```

Both operations are HOD-only. Bulk selection allows 1..1000 distinct UUIDs and
is all-or-nothing: any invalid selection, changed status, stale/missing review,
unverified history or CGPA below 1.00 prevents every transition. 1.00 qualifies.
Contact updates do not invalidate a review; changes to results, requirements,
level, admission year or admission mode do. Save academic profile changes before
reviewing; they cannot be combined with graduation in the same request.

Graduated students' result/requirement history and academic profile are protected
from these editing routes. The HOD must explicitly reopen academic_status to
undergraduate before corrections. Changed history then requires a fresh review
before regraduation. Bulk level changes cannot move graduated students.
Django Student admin keeps academic_status and user read-only to avoid bypassing
the graduation and account services. CGPA history_completeness is not_confirmed
before review, hod_reviewed for a current review, or review_required for a stale
review. This is a manual completeness certification, not automatic curriculum
validation or an academic warning system.

## Guardian API and staff permissions

| Path | Methods |
|---|---|
| students/<uuid>/guardians/ | GET, POST |
| students/<uuid>/guardians/<guardian_uuid>/ | GET, PATCH |

Writes accept full_name, phone_number, relationship, optional email and address.
Example POST:

```json
{"full_name":"Example Guardian","phone_number":"+2340000000000","relationship":"Parent","email":"","address":""}
```

The URL chooses the student; guardian_id and student are read-only. Guardians
cannot be relinked through PATCH. Lists are paginated at 20 records. There is no
DELETE endpoint. These are staff endpoints, not student self-service.

Ordinary staff need students.view_student and students.view_guardian plus an
active AdviserAssignment for CURRENT_ACADEMIC_SESSION and the student's level.
POST additionally requires students.add_guardian; PATCH requires
students.change_guardian. Out-of-scope records return 404. Write services repeat
permission/scope checks while holding transaction locks. HOD has department-wide
access. Existing Student Readers/Editors groups do not automatically receive
these guardian permissions; the HOD grants them deliberately.

GET students/export/ streams all students matching the same search/filter/scope
as students/, without pagination. It requires students.view_student and the
separate students.export_student permission, plus the adviser's active scope.
Read or edit permission alone cannot export. The initial fixed columns are:
student_id, identifier_type, identifier_value, full_name, phone_number,
admission_year, mode_of_admission, current_level, is_active, academic_status.
Guardian details, accounts/passwords, results and biometrics are excluded.

The CSV is UTF-8 and marked no-store. Cells that could trigger spreadsheet
formulas receive a leading apostrophe (including + phone prefixes). Import
identifier/phone columns as text to retain leading zeros. This is a profile
report; it is separate from the teammate's results CSV extraction/import format.

## Accounts and password lifecycle

| Path | Method | Input / behavior |
|---|---|---|
| auth/password/change/ | POST | current_password, new_password; signed-in account |
| auth/password/reset/ | POST | email; public CSRF-protected request |
| auth/password/reset/confirm/ | POST | uid, token, new_password; public CSRF-protected confirmation |
| students/<uuid>/account/ | POST | username, email, password; HOD creates and links student account |
| students/<uuid>/account/ | PUT | account_id; HOD links an existing eligible account |

Django hashes and validates passwords. Change preserves the requesting session
and invalidates other sessions through Django's password session hash. Reset
links expire after one hour and cannot be reused after a successful reset.
Confirmation does not sign the user in. Reset requests return the same generic
message for eligible and unknown emails and never expose a reset token in JSON.
Delivery failures are logged generically, without addresses or reset tokens.
Default per-client request limits are 20/hour for requests and 60/hour for
confirmation. These are basic rate limits; configure a shared Django cache for
consistent enforcement across production workers.

An empty PASSWORD_RESET_FRONTEND_URL disables recovery requests with 503. Set it
to the frontend reset page; HTTPS is required outside development. Configure
DJANGO_EMAIL_BACKEND and SMTP host/port/credentials/TLS/from-address from
.env.example. The console backend is for local development only: it does not
send mail. This project does not automatically load .env.example or a .env file.
No real email delivery was exercised by the tests.

New student accounts always have is_staff=false and is_superuser=false; supplied
privilege fields cannot elevate them. Link accepts an active, usable-password,
nonstaff account not already linked to another student. Existing student links
cannot be silently replaced. HOD must deliver an initial credential securely;
the student can then use password/change/. Staff creation, deactivation, groups,
assignment and password administration remain in HOD-only Django admin.

GET auth/me/ and login responses include role (hod/staff/student), permissions
(sorted Django permission codenames), adviser_levels for the current configured
session, groups and identity. Treat these as UI hints; server checks remain
mandatory. Permission alone does not supply an adviser scope. Refresh identity
when permissions change and handle 403/404 if authorization changes mid-session.

## React teammate checklist

Use relative /api URLs and a same-origin development/production proxy to Django.
Session cookies are HttpOnly and SameSite=Lax; session and CSRF cookies are Secure
when DEBUG=false, so production must use HTTPS. No cross-origin CORS solution is
introduced here. Set trusted origins to the actual frontend origin when needed.

1. GET auth/csrf/ and retain csrfToken before login or recovery requests.
2. Send credentials with requests and X-CSRFToken for POST/PATCH/PUT/DELETE.
3. After login, fetch auth/csrf/ again because Django rotates the token, then
   auth/me/ and the role-specific data. After logout refresh the bootstrap before
   the next sign-in. Do not store passwords in browser storage.
4. Build password change, reset request and reset confirmation pages. The reset
   page reads uid/token query parameters and posts them with new_password; remove
   them from the visible URL after reading and exclude them from analytics/logs.
5. Build scoped guardian screens, profile CSV download, HOD account linking and
   the preview/attestation/graduation workflow. Show server errors; a successful
   review and a successful status change are distinct operations.
6. Exercise actual browser login/CSRF/logout, password recovery via delivered
   email, revoked permissions and adviser/student isolation against a staging
   database. Backend tests do not prove these frontend/mail integrations.

## Schema and validation

New migrations: students/0005_alter_student_options (export permission) and
academics/0004_graduationreview_courserequirement (review and requirements).
Earlier uncommitted academic/status migrations must accompany them. They were
applied only in isolated test databases. Reconcile the shared database first;
review manage.py migrate --plan before deliberately applying migrations.

```powershell
.\.venv\Scripts\python.exe manage.py test students accounts academics --settings=config.test_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Latest local validation: all 204 tests passed on isolated SQLite; Django system
checks and makemigrations --check --dry-run passed. No development/shared
database migrations were applied.

The tests cover minimum CGPA, missing/unverified history, stale reviews, atomic
bulk operations, graduated-history protection/admin bypasses, guardian scope,
export permission/filter/formula handling, account privilege constraints,
password validation/session invalidation, CSRF, token reuse/expiry and reset
throttling. PostgreSQL and live browser/mail checks remain separate requirements.
