# Staff and student API foundation

## Checkpoint: 4 October 2026

Python 3.13, Django 5.2, Django REST Framework; exact development versions are in requirements.txt. Backend stays in app/. A separate React application will live in frontend/ when its developer creates it.

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

## Accounts and authorization decisions

The HOD will use Django admin (/admin/) with a superuser account to create/disable staff accounts, manage details/passwords, and assign groups/permissions. Django admin is its own interface; React does not automatically display it. Staff use React to interact with the JSON API. Passwords use Django hashing and password APIs, never direct raw assignment to the password field. The HOD account has not yet been created.

IMPORTANT: Current student GET views only check is_staff. Assigning Django model permissions in admin does not yet limit these API views. Fine-grained authorization must be implemented and tested before live use. Django's default view/add/change/delete model permissions are available; export will need an explicit permission when implemented. Cohort and field restrictions remain undefined.

Session authentication is explicit. A separate React app does not automatically require JWT. Login/logout/current-user JSON endpoints, CSRF bootstrap, frontend origin/proxy settings, and password-change/recovery flows are pending. React must never be the sole permission enforcement layer. Production CORS/CSRF/cookie settings depend on the chosen deployment addresses.

## Remaining work

1. Configure PostgreSQL locally and verify migrations there.
2. Create the HOD superuser and verify staff account/group management.
3. Enforce assigned permissions on direct API requests; add denied-access tests.
4. Implement JSON login/logout/current-user and coordinate React integration.
5. Add student create/edit, guardian endpoints, audit history, and permission-controlled export.
6. Add academic records and GPA/CGPA calculation rules later.

Tests cover denied anonymous/nonstaff reads, search/filter/detail responses, invalid filters, pagination, unsupported writes, multiple guardians/deletion protection, and password hashing. They do not prove browser login, CSRF integration, or production readiness.
