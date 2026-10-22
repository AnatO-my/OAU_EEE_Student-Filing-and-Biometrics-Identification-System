# Aiven Free PostgreSQL integration

21 October 2026. Selected for the first synthetic integration environment.
The application already uses Django's PostgreSQL backend and psycopg 3.
MySQL is not needed. Application hosting remains a separate choice.

## Create the free service

1. Sign in at <https://console.aiven.io/> and select or create your project.
2. Create a **PostgreSQL** service with the **Free** tier; use `eee-integration`
   as the service name. Check that the service summary says **$0/month**.
   A paid trial, Developer plan or payment method is not needed.
3. Use a new service for this backend, separate from any legacy student database.
   Leave it empty: use Django migrations rather than importing legacy tables.
4. When the service is **Running**, copy its host, port, database name and user
   from Overview/Quick connect. Aiven's port may differ from `5432`.
5. Download the service's CA certificate as `ca.pem`. Save it at
   `private-data/aiven/ca.pem` in this repository, or another private local path.
   Create that directory first if necessary. `private-data/` is ignored by Git.
   Keep the service password out of chat, Git, terminal command arguments and
   screenshots.

The new service's `defaultdb` is suitable for initial integration. If you use a
different database or user, pass the exact names to the setup script.

## Configure the local terminal

Open PowerShell at the repository root. With the CA certificate in place, run:

```powershell
. .\scripts\configure-aiven.ps1
```

The script asks for the hostname, port and password. Password input is hidden.
It configures only this process and programs started from it; it does not save
credentials, connect to Aiven, migrate a database or import data. Use the service
password from Aiven, not your Aiven account password.

On this machine, the ignored `private-data/aiven/configure.ps1` profile supplies
the service details and selects the compatible Windows client described below.
If this terminal already holds the service password, it can be reused privately:

```powershell
. .\private-data\aiven\configure.ps1 -UseExistingPassword
```

In a new terminal, omit `-UseExistingPassword` to enter the password at a hidden
prompt. The switch fails if no password is present; it does not save or print it.

You can supply non-secret values explicitly:

```powershell
. .\scripts\configure-aiven.ps1 `
  -DatabaseHost 'YOUR-SERVICE.aivencloud.com' `
  -DatabasePort 21543 `
  -DatabaseName 'defaultdb' `
  -DatabaseUser 'avnadmin' `
  -RootCertificate 'C:\path\to\ca.pem'
```

Replace the sample host and port with the actual service values. The script
always sets `POSTGRES_SSLMODE=verify-full`, checks the CA certificate exists,
sets a 10-second connection timeout, and selects `config.postgres_settings`.
Django does not automatically load `.env` files. Existing running servers do
not inherit new environment variables; restart them from this terminal later.

## Windows certificate compatibility

The installed psycopg 3.3.6 binary wheel's Windows libpq 18.4 rejected this
service's certificate with `certificate contains IP address with invalid length
16`. The failure occurs before password authentication. The official Windows
18.6 client exhibited the same failure on this machine.

The supported PostgreSQL **16.15** Windows client was verified to reach password
authentication with the same CA and `verify-full`. Negative live checks also
confirmed rejection of an incorrect hostname and an untrusted CA. Psycopg remains
at version 3.3.6 and uses its documented Python implementation to load this client.
The PostgreSQL server remains at version 18.6.

To reproduce this Windows setup on a fresh checkout:

```powershell
.\.venv\Scripts\python.exe scripts/install-postgres-client.py
. .\scripts\configure-aiven.ps1 -ClientLibraryDirectory .\private-data\aiven\pg-client16\bin
```

The download helper fetches seven client DLLs using bounded HTTP ranges from
EDB's official PostgreSQL 16.15 archive, checks ZIP CRCs, and records their source
URL and SHA-256 hashes in `private-data/aiven/pg-client16/manifest.json`. It does
not install a server or Windows service. Downloaded libraries remain ignored.

`ClientLibraryDirectory` sets `PSYCOPG_IMPL=python`, prepends the client directory
to this terminal's `PATH`, and disables Kerberos negotiation with
`PGGSSENCMODE=disable`; Aiven password authentication still uses verified TLS.
Restart the API and worker from this terminal to use the same compatible client.
Other platforms can continue using the pinned binary wheel. The Python
implementation has lower performance than the compiled implementation; use it
for this Windows integration environment rather than assuming production load
capacity from these connection checks.

References: [Psycopg Python installation](https://www.psycopg.org/psycopg3/docs/basic/install.html#pure-python-installation),
[official Windows distributions](https://www.postgresql.org/download/windows/),
[EDB binary archives](https://www.enterprisedb.com/download-postgresql-binaries).

## Verify first, then migrate the fresh target

These commands read the target without changing schema or application records:

```powershell
.\.venv\Scripts\python.exe manage.py check_database_connection
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

The connection diagnostic separates connection/TLS/authentication from its
read-only diagnostic query, and reports PostgreSQL version, TLS state, database size,
connection limit and whether a Django migration table exists. It suppresses raw
provider failures to avoid printing credentials. Errors without SQLSTATE are
classified into fixed certificate, authentication, DNS, timeout and network
messages without echoing provider text. A successful connection does
not establish that migrations are current, the target is empty or the whole
application works. Inspect the selected service and the migration plan.

On the **new, empty integration service**, apply the reviewed migrations and
create the staff groups and initial administrator:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_staff_groups
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py check_database_connection
```

No legacy data conversion or cutover is implied. Use synthetic records first.
Keep real imports separate until source mapping and recovery are validated.

If every migration reports `OK` but the command subsequently loses its
connection inside `emit_post_migrate_signal` / `create_contenttypes` /
`create_permissions`, start a fresh management-command connection and rerun:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput --verbosity 2
```

Django skips recorded migrations and creates only missing content types and
permissions. The active apps have no additional post-migration handlers. Once
the command exits successfully, continue with `setup_staff_groups` and the
read-only connection check. A post-migration traceback still needs recovery
even when all schema operations were recorded successfully.

For local browsing, configure the exact React development origin and run the API
from this terminal. Keep the existing development settings for plain HTTP:

```powershell
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1:5173'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Use the frontend's actual origin if different. Verify login/logout, staff and
student permissions, academic records, attendance roster/session/import flows,
and the guardian preview/queue workflow. Configure and start the existing email
worker separately, from an environment with the same PostgreSQL variables.
Do not enable bulk sharing merely to test database connectivity.

## Tests and recovery

Run ordinary local tests without contacting Aiven:

```powershell
.\.venv\Scripts\python.exe manage.py test accounts students academics attendance --settings=config.test_settings
```

The PostgreSQL-specific concurrency and fresh-process tests are skipped by
SQLite. CI uses a separate PostgreSQL 16 service and synthetic credentials.
To validate those locally or against a disposable integration service:

```powershell
.\.venv\Scripts\python.exe manage.py test accounts students academics attendance --settings=config.postgres_test_settings --noinput
```

That command preserves the app's verified TLS settings, uses the configured
`POSTGRES_*` host/port, and creates and destroys a separate `test_<POSTGRES_DB>`
database. Use only a dedicated synthetic service and a role allowed to create
test databases. `postgres_test_settings` is for isolated tests; use
`postgres_settings` for the application and worker. Do not use `--keepdb` to
reuse an unidentified existing test database. Capacity and available database
permissions on a free service must be checked before hosted test execution.

Before any real-data cutover, create a private `pg_dump` backup, restore it into
a separate disposable database, and verify counts and important relationships.
Backups and dumps belong outside Git. Provider backup availability alone is not
evidence that restoration has been tested.

## Capacity and hosting

As checked on 21 October 2026, the Free PostgreSQL tier has one CPU, 1 GB RAM,
1 GB disk, backups and a maximum of 20 database connections. Aiven also uses
connections for administration. There is no connection pooling, high availability
or availability SLA; inactive services may be powered off after notice. Free
cloud/region selection is restricted. Monitor disk use and keep worker and API
process counts small. `CONN_MAX_AGE=0` closes request connections when finished;
it does not cap simultaneous connections. Stop unused clients.

Aiven hosts the database. It does not deploy this Django application, the React
frontend or the email worker. Render's free web tier sleeps after 15 idle minutes,
blocks SMTP ports `25`, `465`, `587`, and has no free background-worker service;
the existing Gmail SMTP worker therefore needs a separate hosting decision.
Render's free PostgreSQL database expires after 30 days, so it is not our target.

Sources:

- Aiven free-tier limits: <https://aiven.io/docs/products/postgresql/concepts/pg-free-tier>
- Aiven service creation: <https://aiven.io/docs/products/postgresql/get-started>
- Render free-tier limitations: <https://render.com/docs/free>

## Current verification status

Local validation completed on 21 October 2026:

- All 10 new database setup and diagnostic tests passed.
- The full SQLite run discovered 370 tests: 349 passed, 15 PostgreSQL-specific
  tests were skipped, and six localhost HTTP tests initially hit the sandbox's
  Windows socket restriction (`WinError 10013`). Those six passed when rerun
  with localhost socket access; the rerun also skipped its PostgreSQL-only test.
- Django system checks and migration drift checks passed.
- PowerShell syntax and synthetic-input checks passed for hidden password input,
  secret-free output, TLS/CA settings, invalid host/port, and missing certificate.

The user's new service endpoint was reached on 21 October 2026. A TLS-only probe
using `private-data/aiven/ca.pem` completed PostgreSQL SSL negotiation with
TLS 1.3 and verified both the CA chain and hostname. It did not send a password,
log in or query the database. An initial connection reset cleared on the next
probe. An ignored local `private-data/aiven/configure.ps1` profile now contains
the supplied hostname, port, database name and user; it prompts privately for
the password through the shared setup helper.

Follow-up validation on 21 October 2026:

- All 12 database setup/diagnostic tests passed, including connection failures
  without SQLSTATE, private-error redaction, and separation of login/query failures.
- Live password-free checks with the compatible 16.15 client reached
  authentication for the correct CA/hostname and rejected both an incorrect
  hostname and an untrusted CA. Django also reached the missing-password stage.
- PowerShell checks passed for hidden entry, password reuse without another
  prompt, secret-free output, rejection of a missing existing password, and
  loading the selected 16.15 client.
- The user then ran `check_database_connection` with the password kept in their
  terminal. It confirmed authenticated access to PostgreSQL 18.6, TLS active
  with `verify-full`, a 20-connection server limit, a 7.72 MiB database, and no
  Django migration table. That command made no database changes.

The user's first migration run reported all 38 migrations as `OK`, then lost
the connection during Django's post-migration content-type creation. A fresh
`migrate --noinput --verbosity 2` run was requested to finish that idempotent
setup. The user subsequently confirmed successful creation of both `Student
Readers` and `Student Editors`. The next read-only connection check confirmed
the Django migration table was present, database size was 10.38 MiB, and verified
TLS/authentication still passed.

The user confirmed final `migrate --check` and database system checks passed,
and that the initial administrator was created privately. A later development
server startup hit an intermittent DNS failure; the user reported likely Avast
firewall interference and then confirmed the server was active.

Read-only local HTTP checks against that running server passed:

- `/api/auth/csrf/`: HTTP 200.
- `/api/auth/me/` and `/api/students/`: HTTP 403 for a fresh anonymous session.
- `/admin/`: redirected to the administrator login page, HTTP 200.

The user then confirmed successful administrator login and dashboard loading.
The database integration and initial local backend/admin smoke test are complete.
Subsequent integration passed all **380 backend tests on isolated PostgreSQL 18.6**,
including contention and process-restart checks. The user then created a real
Aiven backup and verified restoration of **41 tables**, with matching row hashes,
constraints and sequences, into a disposable local cluster. No live database was
overwritten. See [the PostgreSQL checkpoint](postgres-validation-checkpoint.md)
and [backup/restore instructions](backup-restore.md).

The React portal is integrated at `frontend/portal`; its build/lint, 18 portal
tests and 13 guardian tests pass. HOD/student browser checks used a separate
synthetic PostgreSQL database. [The laptop guide](local-laptop.md) starts Django,
React and an optional email worker against Aiven. Application/worker hosting is
deferred at the user's request. This checkpoint does not establish production
readiness or import live student records.
