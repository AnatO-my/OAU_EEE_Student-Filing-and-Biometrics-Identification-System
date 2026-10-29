# Website startup commands — PowerShell

Checked against the startup scripts on **23 October 2026**.

Choose the scenario you need. Do not run every section in sequence.
Run commands from the project root unless a block changes the directory.
Activation of `.venv` is optional: these commands call its Python directly.
Keep the startup terminal open. Use **Ctrl+C in that terminal** to stop its servers.

| Scenario | Section |
| --- | --- |
| Normal daily startup, fresh terminal or after reboot | 1 |
| Restart after code changes | 2 |
| Pending migrations or application update | 3 |
| Start with Gmail / enable guardian email worker | 4 |
| Use different ports | 5 |
| Run Django and React in separate terminals | 6 |
| Open the standalone guardian page | 7 |
| Offline synthetic preview without Aiven | 8 |
| Reinstall dependencies on this laptop | 9 |
| Checks, tests and frontend build | 10 |
| Page inactive, login errors or occupied ports | 11 |

## 1. Normal daily startup

### New PowerShell terminal / after reboot

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
.\scripts\start-local.ps1
```

Enter the Aiven database password at its hidden prompt. This is the database
password, not the HOD website password or Google App Password.

### Terminal already has the Aiven password

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1 -UseExistingPassword
.\scripts\start-local.ps1
```

### Same configured terminal, no settings have changed

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\scripts\start-local.ps1
```

Open these addresses:

- Main login: **http://127.0.0.1:5175/login**
- HOD guardian sharing: **http://127.0.0.1:5175/portal/hod/guardian-results**
- Django administration: **http://127.0.0.1:5175/admin/**

Sign in with the account already created in the selected database. The earlier
`ui-hod` account belonged to a separate synthetic preview; it is not an Aiven login.
Use `127.0.0.1` consistently rather than switching between it and `localhost`.

Normal startup checks the connection and migrations but does not migrate, import
records or start an email worker. Aiven requires an internet connection.

If the private profile is absent on another checkout, configure a terminal using
the public helper instead. It prompts for the service details/CA configuration;
do not put passwords into command arguments or commit a private profile.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\scripts\configure-aiven.ps1
.\scripts\start-local.ps1
```

## 2. Restart after source or configuration changes

First press **Ctrl+C** in the running startup terminal. Then, in that same terminal:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\scripts\start-local.ps1
```

Refresh the browser. The launcher disables Django's autoreloader, so refreshing
the page alone does not load changed backend code. For changed dependencies use
section 9; for pending migrations use section 3. A closed terminal loses its
private settings: use the new-terminal instructions in section 1.

## 3. Application update / pending migrations

Stop **all local servers and workers** first, including any started manually or
on alternate ports. In a newly opened terminal:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
.\scripts\update-local.ps1
```

If the same terminal is already configured, run only:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\scripts\update-local.ps1
```

This command **changes the selected Aiven schema**: it checks the migration plan,
creates a timestamped private backup, verifies restoration in a new disposable
local PostgreSQL cluster, applies pending migrations, checks the database and
starts the website. It imports no students/results and creates no accounts.
It needs the existing private PostgreSQL backup/runtime utilities. If these are
missing, follow [backup setup](docs/backup-restore.md) before updating.

The latest source-reported GPA/CGPA change requires
`record_imports.0002_importbatch_source_context_sourceperformance`.
The helper applies **all pending migrations**, not just that one. A startup error
about unapplied migrations must be addressed through this update procedure;
do not delete migration files or use `--fake` to bypass it.

For an inspection that does not change the schema or start the website:

```powershell
.\.venv\Scripts\python.exe manage.py check_database_connection
.\.venv\Scripts\python.exe manage.py migrate --plan
```

## 4. Gmail and optional guardian email delivery

### Website with Gmail configured, but no guardian worker

Use this for password/access-link email actions without processing queued guardian
reports. The Gmail helper does not send a message itself.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
. .\scripts\configure-gmail.ps1
.\.venv\Scripts\python.exe manage.py check_email_connection --stages --auth-method LOGIN
if ($LASTEXITCODE -ne 0) { throw 'Resolve the SMTP check before starting.' }
.\scripts\start-local.ps1
```

Enter the sending address and a **Google App Password**, not the normal Google
password. These settings are inherited only by processes started from this
terminal. Restart an existing application to use new provider settings.

### Website AND guardian email worker

This can send **already queued real guardian reports**. Use it when reviewed
delivery is intended, not merely to test whether the website opens.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
. .\scripts\configure-gmail.ps1
.\.venv\Scripts\python.exe manage.py check_email_connection --stages --auth-method LOGIN
if ($LASTEXITCODE -ne 0) { throw 'Resolve the SMTP check before starting.' }
$env:RESULT_SHARING_ENABLED = 'true'
.\scripts\start-local.ps1 -EmailWorker
```

Only email jobs are processed. This does not enable WhatsApp. The supervisor
handles worker shutdown on Ctrl+C; review any uncertain/processing delivery if
shutdown is interrupted. Do not start a second worker unnecessarily.

For an update followed by intentional email delivery, replace the last command
above with:

```powershell
.\scripts\update-local.ps1 -EmailWorker
```

### Worker alone, separate configured terminal

Use only if the website is already running and a separate worker is intended.
Configure Aiven and Gmail in this worker terminal too; a second terminal does not
inherit changes made in the first.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
. .\scripts\configure-gmail.ps1
$env:RESULT_SHARING_ENABLED = 'true'
.\.venv\Scripts\python.exe manage.py process_result_shares --channel email --watch --interval 5 --limit 25
```

### Send just one fictional mock email

After configuring Gmail in the same terminal, the following explicitly sends to
the address you enter. It does not process the guardian queue.

```powershell
$mockRecipient = Read-Host 'Your agreed test recipient email address'
.\.venv\Scripts\python.exe manage.py send_mock_guardian_email --to $mockRecipient --send
```

If its outcome is uncertain, inspect the inbox/sender account before retrying.
Provider acceptance does not guarantee inbox delivery.

## 5. Alternate ports

Stop the old launcher first. In the Aiven-configured terminal:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\scripts\start-local.ps1 -BackendPort 8002 -FrontendPort 5177
```

Open **http://127.0.0.1:5177/login**. The launcher changes the API proxy and trusted
CSRF origin together. These parameters can also be combined with `-EmailWorker`
after the email setup in section 4. `update-local.ps1` starts the default ports;
it does not accept alternate-port arguments.

## 6. Django and React in separate terminals

Use this for development troubleshooting instead of the combined launcher.
Do not run the launcher simultaneously on the same ports.

### Terminal A — backend

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
. .\private-data\aiven\configure.ps1
$env:DJANGO_DEBUG = 'true'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost'
$env:DJANGO_SECURE_TRANSPORT = 'false'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1:5175'
$env:STUDENT_ACCOUNT_FRONTEND_ORIGIN = 'http://127.0.0.1:5175'
.\.venv\Scripts\python.exe manage.py migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Stop and use the backed-up update procedure in section 3.' }
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

### Terminal B — portal

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project\frontend\portal'
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8000'
npm.cmd run dev
```

Open **http://127.0.0.1:5175/login**. Ctrl+C each terminal to stop both services.
Gmail/reset configuration is not automatically supplied by these manual commands;
prefer the launcher for the normal application/email workflow.

## 7. Standalone guardian page / the old port 15173

The integrated portal already includes guardian sharing; a standalone server is
optional. This page still requires a working backend and a HOD in its database.

For standalone port **5173**, change Terminal A's trusted origin in section 6 to
`http://127.0.0.1:5173` **before** starting Django. In Terminal B:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project\frontend\guardian-results'
$env:GUARDIAN_API_TARGET = 'http://127.0.0.1:8000'
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open **http://127.0.0.1:5173/guardian-results/**.

To use the old **15173** address instead, set Terminal A's trusted origin to
`http://127.0.0.1:15173`, restart Django, then use this Terminal B block:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project\frontend\guardian-results'
$env:GUARDIAN_API_TARGET = 'http://127.0.0.1:8000'
npm.cmd run dev -- --host 127.0.0.1 --port 15173
```

Open **http://127.0.0.1:15173/guardian-results/**. This does not recreate the old
synthetic `ui-hod` database. It uses the backend you selected; if that backend is
Aiven, its actual records and HOD credentials apply. For fake/offline data, use
section 8's separate backend instead, adjusting its CSRF origin for this page.

## 8. Offline, isolated synthetic preview

Use a **separate terminal** and fake data only. This creates an explicitly named
local SQLite database and local HOD; it does not copy or fall back to Aiven data.
Dependencies must already be installed. Email stays in memory and guardian
delivery is disabled. SQLite is not a substitute for PostgreSQL concurrency tests.

### Terminal A — create isolated settings and database, then run Django

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
New-Item -ItemType Directory -Path .\private-data -Force | Out-Null
if (-not (Test-Path -LiteralPath .\private-data\website_preview_settings.py)) {
@'
from config.settings import *
import secrets
SECRET_KEY = secrets.token_urlsafe(50)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR.parent / "private-data" / "website-preview.sqlite3"}}
PRIVATE_MEDIA_ROOT = BASE_DIR.parent / "private-data" / "website-preview-media"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5175"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
RESULT_SHARING_ENABLED = False
PASSWORD_RESET_FRONTEND_URL = ""
'@ | Set-Content -LiteralPath .\private-data\website_preview_settings.py -Encoding utf8
}
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'private-data')
$env:DJANGO_SETTINGS_MODULE = 'website_preview_settings'
.\.venv\Scripts\python.exe manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Preview migration failed; do not start the preview.' }
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Choose a **test-only** username/password at the interactive prompt. On later
starts, reuse the same settings/environment block but **omit `createsuperuser`**;
the local account and records persist. The generated session key changes on
restart, so sign in again. If the settings file already exists, inspect/reuse it;
the block intentionally does not overwrite it.

### Terminal B — portal

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project\frontend\portal'
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8000'
npm.cmd run dev
```

Open **http://127.0.0.1:5175/login** with the test HOD account. Start with empty
screens and configure synthetic sessions/courses/students through authorised
controls/admin as needed; this does not seed result or attendance fixtures.
Stop both terminals before returning to normal Aiven startup in section 1.

## 9. Missing dependencies / fresh checkout

Use installed Python **3.13** and Node **24**. The commands below install project
dependencies; they do not create an application database or website account.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) {
    py -3.13 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Resolve Python dependency installation before continuing.' }
Push-Location .\frontend\portal
try {
    npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Resolve portal dependency installation before starting.' }
} finally { Pop-Location }
```

Only if using the standalone guardian application:

```powershell
Push-Location .\frontend\guardian-results
try { npm.cmd ci --ignore-scripts --no-audit --no-fund }
finally { Pop-Location }
```

Then configure the Aiven terminal and follow section 1 or 3, as appropriate.
Do not select a different database or create a replacement administrator merely
because the existing login fails. `.env.example` is a template; Django does not
load `.env` files automatically.

## 10. Checks, tests and build

### Read-only Aiven startup checks (configured terminal)

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\scripts\start-local.ps1 -CheckOnly
```

### Backend regression tests — isolated SQLite, not Aiven

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\.venv\Scripts\python.exe manage.py test students accounts academics attendance record_imports documents --settings=config.test_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.test_settings
```

PostgreSQL-only cases are skipped on SQLite. For the full disposable PostgreSQL
run, if the trusted local runtime is already installed:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
.\.venv\Scripts\python.exe tools\run_attendance_postgres_tests.py --pg-bin .\private-data\postgres18\bin --keep-cluster
```

This creates and stops its own temporary loopback database, leaving synthetic
cluster/log files for inspection. It does not test against or migrate Aiven.

### Portal checks and production bundle

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project\frontend\portal'
npm.cmd test
if ($LASTEXITCODE -ne 0) { throw 'Portal tests failed.' }
npm.cmd run lint
if ($LASTEXITCODE -ne 0) { throw 'Portal lint failed.' }
npm.cmd run build
```

The bundle is written to `frontend/portal/dist/`. Building does not start the
website or deploy it. Hosting is deferred; Django `runserver` and Vite `dev` are
local development commands, not public production hosting instructions.

## 11. Troubleshooting and shutdown

### Check whether the website and API are responding

In a separate terminal while the application is running:

```powershell
(Invoke-WebRequest 'http://127.0.0.1:5175/login' -UseBasicParsing).StatusCode
(Invoke-WebRequest 'http://127.0.0.1:8000/health/live/' -UseBasicParsing).StatusCode
Invoke-RestMethod 'http://127.0.0.1:8000/health/ready/'
```

Expect HTTP `200` and readiness `status: ok`. Substitute alternate ports if used.
An open browser tab does not mean the servers are still running.

### Inspect occupied ports without killing processes

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000, 5175, 5173, 15173 } |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Stop your known server in its own terminal with Ctrl+C, or use alternate ports.
Do not kill every Python/Node process. The launcher stops only its own children.

- **Connection refused / page inactive:** start the relevant backend and frontend;
  refreshing cannot revive a stopped server.
- **Aiven unavailable:** confirm internet/service/CA settings, then reconfigure
  the terminal and run `check_database_connection`. Do not disable TLS checking.
- **`getaddrinfo failed` / `failed to resolve host`:** this is a DNS failure,
  before password authentication or migration inspection. Check resolution with
  `Resolve-DnsName $env:POSTGRES_HOST -DnsOnly`, then rerun
  `start-local.ps1 -CheckOnly` from the configured terminal. A connection check
  that passed earlier does not guarantee DNS will work on the next connection.
  Do not replace the hostname with an IP address or change TLS verification.
- **Startup check failed:** the updated launcher prints `PostgreSQL connection`
  and `Migration readiness` separately and forwards their output with configured
  secrets redacted. A failed migration-readiness check can also be caused by a
  connection outage; inspect its diagnostic/plan before assuming migrations
  are pending. Checks never apply migrations automatically.
- **CSRF/login 403:** use the exact host/port trusted by Django; restart the backend
  after changing its origin. Log in with credentials from the selected database.
- **Old UI/API behavior:** stop/restart the launcher, then refresh the browser.
- **Unapplied migrations:** use section 3's backed-up update process.
- **Email settings changed:** restart both API and worker from the configured
  terminal. Check uncertain submissions before retrying any send.
- **PowerShell blocks a script:** inspect the exact policy/error and use your
  approved workstation policy. This guide does not disable execution policy or
  endpoint protection.

Related details: [laptop startup](docs/local-laptop.md),
[source averages/migration](docs/student-result-imports.md),
[email setup](docs/guardian-email-setup.md),
[standalone guardian app](frontend/guardian-results/README.md).

## Announcement notification worker (26 October update)

Announcement emails use a separate explicit option from guardian result emails. In the configured database/SMTP terminal:

```powershell
.\scripts\start-local.ps1 -TeachingNotifications
```

This starts sending pending announcement notifications. Use normal `start-local.ps1` when that is not intended. To run both configured queues, add `-EmailWorker`. Set `TEACHING_PORTAL_URL` to the intended externally reachable portal URL for forwarded access; an unset value follows the local frontend port. See `docs/teaching-workflows.md` for scope and unknown-delivery handling. Restart existing servers with Ctrl+C in their own startup terminal before launching again.
