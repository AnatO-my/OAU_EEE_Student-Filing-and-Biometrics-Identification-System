# Run the integrated application on this laptop

The React portal, Django API/admin and optional email worker run on this laptop.
The selected application database remains **Aiven PostgreSQL**, so database use
requires internet access. Hosting is deferred. The disposable local PostgreSQL
runtime is for isolated tests and restore verification, not an automatic switch
away from Aiven or an offline copy of its records.

## Start the application

From `C:\Users\Ot\Downloads\EEE-Project`, stop any existing Django/Vite servers
in their terminals with **Ctrl+C**. The launcher refuses occupied ports and never
kills unrelated processes.

In the PowerShell terminal already configured for Aiven:

```powershell
. .\private-data\aiven\configure.ps1 -UseExistingPassword
.\scripts\start-local.ps1
```

For a new terminal, omit `-UseExistingPassword` and enter the Aiven password at
the hidden prompt. Nothing saves the password to disk. The private profile uses
the service CA and the tested Windows libpq 16.15 client with hostname checking.

Open **http://127.0.0.1:5175/login** and sign in with the administrator already
created on Aiven. Django administration is available at
**http://127.0.0.1:8000/admin/** and through **http://127.0.0.1:5175/admin/**.
Use `127.0.0.1` consistently. Database/provider secrets belong only in the backend
process environment; the frontend needs no database credentials.

The launcher checks the database connection and pending migrations without
applying migrations or importing data. It supplies the exact frontend CSRF
origin, starts Django without its autoreloader and starts Vite. All listeners
bind to loopback. Keep the terminal open; **Ctrl+C** stops only those child
processes. The launcher never starts another worker implicitly.

Read-only prerequisites can be checked separately:

```powershell
.\scripts\start-local.ps1 -CheckOnly
```

Optional alternate ports are `-BackendPort 8002 -FrontendPort 5177`; the launcher
updates the frontend proxy and trusted origin together.

## Apply the student registration/import update

Stop the local startup terminal with Ctrl+C. In the configured Aiven terminal,
run `./scripts/update-local.ps1`. This checks the connection, shows the migration
plan, creates a timestamped private backup, proves its restoration in a new local
cluster, applies the two registration/import migrations, verifies the database
and starts the application. It imports no student records or results. Credentials
stay in the terminal environment. See [student registration](student-registration.md)
and [reviewed imports](student-result-imports.md).

If the identity migration finds ambiguous old identifiers it stops atomically
without merging/deleting students. Keep the backup and resolve the flagged data
explicitly before retrying. Never reset migrations to bypass that check.

For normal subsequent startups, continue using `scripts/start-local.ps1`.
The update helper's optional `-EmailWorker` forwards the existing explicit
delivery option; normal schema updates do not enable it.

## Refresh the converter integration

The source-preparation update needs no additional database migration. Stop the
local startup terminal with Ctrl+C and run `./scripts/start-local.ps1` again from
the same configured terminal, then refresh the browser. The backend runs without
an autoreloader, so a browser refresh alone cannot load a changed API endpoint.
The existing laptop environment already has the PDF converter dependency;
fresh installations install it with the application's `requirements.txt`.

Under **Upload results**, select the master-sheet PDF, enter its reviewed attempt
number and choose **Convert and preview scores**. The portal fills the source
session/semester/course/mark fields and matches existing students. Unknown matric
numbers wait for separate registration in **Students**; return to the saved
preview and refresh it afterward. Ordinary result CSV templates still use their
existing per-row context. See [PDF conversion](pdf-student-extraction.md).

## Apply account administration

The account/staff-management update adds the audit-table migration
`accounts.0005_accountadministrationaudit`. Stop the launcher with Ctrl+C, then
run `./scripts/update-local.ps1` in the configured Aiven terminal. It backs up,
verifies restoration, applies pending migrations and starts the app. This does
not transfer HOD status or create staff accounts. Open **Account settings** below
the username/avatar for password, staff, part-adviser and HOD-transfer controls.
See [account administration](account-administration.md).

## Student sign-in

The HOD opens a record under **Students** and uses **Student login** to create
its account and a private password setup link. The exact matriculation/UTME
identifier is used for new logins, including `/` and leading zeros. Existing
usernames change only through the HOD's explicit reviewed action on the record.
The student chooses the password and signs in on the same login page.

Apply the username-validator update with `./scripts/update-local.ps1` after
stopping the app. Manual setup links need no SMTP. To enable email access links,
first run `. ./scripts/configure-gmail.ps1` privately in the same Aiven-configured
terminal. This action is separate from the guardian worker; do not add
`-EmailWorker` or enable result sharing just to send student access links.
Email submission requires a reviewed saved student email and an explicit HOD
action. Links using `127.0.0.1` work on this laptop only. See
[student accounts](student-accounts.md).

## Enable email delivery when needed

To send reviewed queued guardian emails, configure the same terminal privately
before starting both the application and worker:

```powershell
. .\private-data\aiven\configure.ps1 -UseExistingPassword
. .\scripts\configure-gmail.ps1
$env:RESULT_SHARING_ENABLED = 'true'
.\scripts\start-local.ps1 -EmailWorker
```

The Gmail helper prompts for the sender and Google App Password without saving
the password. If SMTP is already configured in that terminal, skip its helper.
The explicit worker flag processes existing queued email reports; review the
queue before enabling it. It does not process WhatsApp. Normal startup leaves
the worker off. Restart the application after changing provider settings.

Stopping uses a supervisor marker so an in-flight email submission can finish
before another is claimed. If shutdown exceeds 30 seconds, the launcher reports
that the worker was stopped and any processing delivery needs review. Uncertain
submissions must not be resent automatically.

Password reset links work locally only while these services are running on the
same laptop. The reset frontend URL is left disabled until email is configured.
With configured SMTP, the laptop launcher supplies the reset page URL unless an
explicit one is already set, and sets the student-access origin to its actual
frontend port. It does not send a test message or activate delivery on startup.

## Dependencies and checks

The current workspace has Python 3.13, project `.venv`, Node 24.22.0, npm 11.19.1
and installed portal dependencies. To recreate the frontend installation:

```powershell
Push-Location .\frontend\portal
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd test
npm.cmd run lint
npm.cmd run build
Pop-Location
```

The portal imports the existing guardian workspace directly. Its standalone
server on port 5173 is not needed for the integrated portal.

Observed on 21 October 2026:

- **380 backend tests passed on PostgreSQL 18.6**, with concurrency and fresh
  process checks; no skips. System checks and migration drift passed.
- **18 portal and 13 standalone guardian tests passed**; portal lint/build passed.
- Browser HOD and student login, role-specific workspaces, database records,
  attendance, guardian workspace and real logout were checked using synthetic
  records in an isolated database.
- The local supervisor started Django/Vite/email worker with synthetic data and
  disabled email delivery, then stopped its children and released both ports.
- The user backed up actual Aiven and verified restoration of **41 tables** with
  matching row hashes, constraints and sequences; the temporary restore was removed.
- After the laptop startup instructions, anonymous checks returned HTTP 200 for
  the portal login page, backend liveness and database readiness. The user then
  confirmed successful administrator sign-in and HOD portal loading against
  the configured Aiven database. The password remained private.

See [frontend integration](frontend-integration-checkpoint.md),
[PostgreSQL validation](postgres-validation-checkpoint.md) and
[backup/restore](backup-restore.md) for scope and reproduction details.

## Troubleshooting

- **Port already in use:** stop the old server in its own terminal, or choose
  alternate ports. Do not run both the old Django server and launcher on 8000.
- **Database startup check fails:** reuse the configured Aiven terminal, verify
  the service/network and CA path, then run `manage.py check_database_connection`.
  Keep Avast protection enabled and permit the specific trusted application if
  its firewall rules block the connection.
- **Login CSRF error:** use the launcher and the exact `127.0.0.1` URL above.
  Standalone Vite requires the matching Django trusted origin before startup.
- **No records:** a newly initialized Aiven database has no imported students or
  results. Empty screens are expected until authorized records are added.
- **Limited menus:** accounts see their effective backend permissions. Course,
  grading, profile/account administration and some lifecycle operations remain
  in Django admin. Timetables, appointments, document-upload pages and biometric
  identity matching are outside this frontend integration.
