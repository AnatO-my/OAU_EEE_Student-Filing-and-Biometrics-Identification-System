# Staff and student API foundation

## Checkpoint: 4 October 2026

Added the JSON authentication endpoints the React client needs before it can read any
staff data: /api/auth/csrf/, /api/auth/login/, /api/auth/logout/, and /api/auth/me/.
Session authentication is used; no token authentication was added. Account tests cover
the token and cookie, login success and failure, identical rejection of non staff and
unknown accounts, staff-only current-user access, session teardown on logout, and csrf
enforcement on unsafe requests. No model or migration changes were needed. The React
integration itself is still untested in a browser. See "Authentication endpoints" for
the contract and the frontend origin setup.

## Checkpoint: 4 October 2026

Python 3.13, Django 5.2, Django REST Framework; exact development versions are in requirements.txt. pyproject.toml defines project metadata, Python compatibility, and packaging for the implemented Django apps; it reads dependencies from requirements.txt to avoid maintaining two dependency lists. Backend stays in app/. A separate React application will live in frontend/ when its developer creates it.

Implemented: custom accounts.User extending AbstractUser and registered with UserAdmin; Student and Guardian models, serializers, migrations; staff-only student list/detail GET endpoints, search, validated filters, and pagination. No migrations have been applied to the development database as part of this checkpoint.

## Setup (PowerShell, repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
.\.venv\Scripts\python.exe app/manage.py check
.\.venv\Scripts\python.exe app/manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe app/manage.py test students accounts --settings=config.test_settings
```

.env.example documents settings but is not automatically loaded. With DEBUG enabled, an unset secret gets a random process-local fallback: sessions will not survive a restart. Set a stable local secret for login development. Never commit real secrets. These settings are a development baseline, not production deployment settings.

Database setup remains paused. Current development settings still select SQLite. Local tests use an isolated in-memory SQLite database and synthetic records; PostgreSQL validation runs separately in GitHub Actions. Before creating real development tables/accounts, configure local PostgreSQL and then apply migrations. Do not change AUTH_USER_MODEL after applying initial account migrations.

## Student data

student_id is the permanent UUID. identifier_type is matriculation or utme; identifier_value is required, unique across all students, and remains text to preserve leading zeros. Identifier-format and case-normalization rules remain pending. full_name, phone_number, admission_year, mode_of_admission, and current_level are required. Admission modes: utme, direct_entry, transfer. Current level is explicitly recorded to accommodate leaves of absence and other progression exceptions; do not infer it from admission year. is_active defaults to true and does not encode an academic status.

A student may have multiple Guardian records. Name, relationship, and phone are required; email and address are optional. Student deletion is protected while guardian records reference it. Guardian serializer exists but no guardian API route exists yet.

GPA/CGPA will be calculated from results after academic rules are agreed; they are not Student columns. Academic score and fingerprint_score are separate concepts. Fingerprint matching is planned on the backend/separate biometric subsystem, not currently on the device; no biometric endpoint or matching implementation exists in this checkpoint.

## API contract

- GET /api/students/: paginated list.
- GET /api/students/{student_id}/: single student, or 404.
- search: case-insensitive name/identifier search using DRF SearchFilter.
- Optional exact filters: admission_year, current_level, mode_of_admission, identifier_type, is_active. Multiple filters are ANDed. Invalid recognized filter values return 400.
- page: page number, 20 records per page.
- List shape: count, next, previous, results.
- Serializers expose the model fields and mark UUIDs read-only. Create/edit API routes are not implemented.

Example: /api/students/?search=example&current_level=300&is_active=true&page=1

## Authentication endpoints

Session authentication is explicit and is what these endpoints use. They exist so the
React client can start and end a staff session before it reads any staff data. A
separate React app does not require JWT for this, and no token authentication has been
added.

- GET /api/auth/csrf/: issues the csrftoken cookie and returns {"csrfToken": ...}. Responses are not cached.
- POST /api/auth/login/: accepts username and password, returns the staff identity, and starts the session.
- POST /api/auth/logout/: ends the session. Returns 204.
- GET /api/auth/me/: returns the current staff identity, used by the frontend to gate its interface.

Login accepts staff accounts only. An inactive account, a non staff account, a wrong
password, and an unknown username all return the same error so the endpoint cannot be
used to discover which staff accounts exist. The password is never returned in a
response.

React must send the sessionid cookie and return the csrf token in the X-CSRFToken header
on every unsafe request. The token is rotated when the session changes, so the client
must call GET /api/auth/csrf/ before login and again after logging in. Anonymous clients can obtain a token before authentication. Login explicitly enforces CSRF; logout and authenticated writes use session authentication CSRF enforcement.

Set DJANGO_CSRF_TRUSTED_ORIGINS to the frontend origin before developing against the
React client, for example http://localhost:5173. It is read from the environment and
defaults to empty. No cross origin package is installed yet: the React development
server should proxy /api to Django, or django-cors-headers must be agreed and added
before the client is served from a different origin. Do not add "*" to the trusted
origins.

## Accounts and authorization decisions

The HOD will use Django admin (/admin/) with a superuser account to create/disable staff accounts, manage details/passwords, and assign groups/permissions. Django admin is its own interface; React does not automatically display it. Staff use React to interact with the JSON API. Passwords use Django hashing and password APIs, never direct raw assignment to the password field. The HOD account has not yet been created.

Student staff reads require is_staff, view_student permission, and an active level assignment in CURRENT_ACADEMIC_SESSION. Active superusers can read all students. Empty session configuration, revoked assignments, and previous-session assignments grant no ordinary staff access. Detail requests outside scope return 404. HOD-only admin screens prevent staff bypassing API scope. Guardians have no API routes yet. Export will need an explicit permission; field-level restrictions remain pending.

Session authentication is explicit. A separate React app does not automatically require JWT. Login/logout/current-user JSON endpoints and CSRF bootstrap are implemented; see "Authentication endpoints". Frontend origin/proxy settings and password-change/recovery flows are pending. React must never be the sole permission enforcement layer. Production CORS/CSRF/cookie settings depend on the chosen deployment addresses.

## Remaining work

1. Configure PostgreSQL locally and verify migrations there.
2. Create the HOD superuser and verify staff account/group management.
3. Extend tested read permissions/scope enforcement to future write/export/guardian endpoints.
4. JSON login/logout/current-user and CSRF bootstrap are implemented; see
   "Authentication endpoints". Coordinate React integration and agree the deployment
   origins; password-change and recovery flows are still pending.
5. Add student create/edit, guardian endpoints, audit history, and permission-controlled export.
6. Add academic records and GPA/CGPA calculation rules later.

Tests cover denied anonymous/nonstaff reads, search/filter/detail responses, invalid filters, pagination, unsupported writes, multiple guardians/deletion protection, and password hashing. Account tests cover the CSRF token and cookie, login success and failure, identical rejection of non staff and unknown accounts, staff-only current-user access, session teardown on logout, and that logout and other unsafe requests are refused without a CSRF token. They do not prove browser login against the React client, cross origin behaviour in the browser, or production readiness.

## Checkpoint: 5 October 2026 — advisers and student profiles

Custom User is shared by staff and students. Student.user is an optional one-to-one link, excluded from the general student serializer. Student accounts are nonstaff. GET /api/me/student/ retrieves only the profile linked to the authenticated account; it is read-only and returns 404 if no profile is linked. Existing JSON auth endpoints still accept staff only, so student session login integration remains pending. Endpoint tests use forced authentication and do not prove student browser login.

AdviserAssignment stores staff, academic_session (YYYY/YYYY with consecutive years), level and active status; unique per staff/session/level. Model clean validates session and staff status; direct save does not invoke clean automatically. HOD-only admin screens allow creation/edit/deactivation, not deletion. Current scope uses current_level, not historical academic enrollment.

Run setup_staff_groups only after migrations. It sets Student Readers to student/guardian view permissions and Student Editors to view/add/change permissions. Reruns replace permissions on these named groups but retain membership. Standard auth Group admin is controlled by Django permissions; group management should remain reserved for the HOD.

Set CURRENT_ACADEMIC_SESSION in the environment. It defaults to empty, which denies ordinary staff record access. Advisers need both the action permission and a current active assignment. This policy currently gives all ordinary staff access only through adviser assignments; broader staff scopes are not implemented.

AdviserMessage stores audience (individual/level), assignment, subject/body, timestamp, and explicit recipients. Recipient links survive level changes. Sending, recipient selection, permissions, read endpoints, receipts, and message administration are not implemented. Both individual messages and level announcements are required. Do not treat the model alone as a secure sending workflow.

Local development/shared PostgreSQL setup is still paused. Migrations are applied only to isolated test databases in validation. Before connecting to the teammate's database, reconcile schema/account/identifier differences; do not apply our migrations to their existing schema blindly.

## Reconciliation checkpoint: 5 October 2026

The canonical command is now `python manage.py ...` from the repository root. It adds app/ to the import path before loading config.settings; the old app/manage.py delegates to it. Active configuration is app/config/, with accounts.User, students and accounts. Imported portal/config source is preserved under legacy/teammate_portal/ and excluded from the active runtime, migration graph and package discovery. It is reference material for academic integration, not a second deployed backend. CI now runs root management commands. WSGI/ASGI deployments must put app/ on their Python import path (for example gunicorn --chdir app config.wsgi).

Student-auth work from origin/feat/student-auth is integrated: active staff and accounts linked to Student may sign in, inspect their own current-user identity and log out. Nonstaff accounts without a linked profile cannot sign in. CSRF protection remains explicit on login and on authenticated session writes. No surname-first-login backend was adopted.

Messaging routes:

- POST /api/adviser-messages/: send individual or level message using assignment_id, audience, subject, body, and recipient_id for individual messages. Requires send_adviser_message plus the caller's own active assignment in CURRENT_ACADEMIC_SESSION. Recipient links are selected/saved transactionally from active students in that level.
- GET /api/me/messages/: linked student's adviser messages, paginated 20 per page. Account without a Student link gets 404. Read-only; excludes other recipients.
- POST /api/hod-messages/: active staff superuser only. Audience individual requires student UUID recipient_id; level requires positive integer level; adviser requires integer adviser_id referencing active staff with a current active adviser assignment. Omit target fields for other audience types. Subject/body required. Current session is server-derived and required. No duplicate HODAssignment model is used; HOD does not need an adviser assignment. Targets are snapshotted in a separate HODMessage model with distinct student/adviser recipient relationships.
- GET /api/me/hod-messages/: current account's received HOD messages, paginated and read-only; other recipients are never exposed. Staff see messages targeting their account; student messages resolve through the Student.user link.

HOD send responses use message_id, audience, subject, recipient_count, created_at. Inbox responses use id, audience, subject, body, sender_name, created_at within the standard pagination envelope. UUIDs remain strings. Adviser message audience fields and HOD message audience fields are different contracts; adviser_id is a user integer, not a student UUID. Students moving levels retain previously addressed messages.

HOD messaging explicitly targets one assigned adviser per adviser request; all-adviser broadcasts are not included. Message editing/deletion, read receipts and external notifications are not implemented. Message records are not registered for unscoped admin editing.

Migration accounts/0004_hodmessage creates the new HOD message schema; accounts/0003 records adviser send permission. Development/shared database migrations have not been applied. Before running migrate, agree whether the shared database already has portal/auth tables and plan migration to accounts.User without losing records.

Verification: 62 synthetic tests pass locally on isolated SQLite, system checks pass from root and compatibility entry points, and no missing migrations are reported. PostgreSQL CI must validate the uploaded repair. SQLite does not prove PostgreSQL row-lock behavior or concurrent delivery; the service uses atomic transactions/select_for_update but contention behavior is not stress-tested. React browser integration remains unverified.
