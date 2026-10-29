# Vercel demonstration deployment

Prepared on 29 October 2026. **Not deployed or verified on Vercel yet.**
The connected Vercel account and team report an active **Hobby** plan, with no
trial. Project `oau-eee-demo` was created using the default free build resources;
no payment method, upgrade, paid integration or domain purchase was requested.
The authenticated Vercel plugin is available. The separately installed CLI
65.7.0 remains logged out; plugin deployment does not depend on CLI login.

The project belongs to team `agunotanamayokun-8763`. Its local ignored link records
project `prj_35esrceLjCFrcVa8Pg76dPHbOMsY` and team
`team_VGJQbjcF1OQlI79kBLNpke69`. Default deployment protection remains enabled.
The user has connected GitHub after Vercel initially rejected repository import.
The Git build, isolated database setup, environment provisioning and live checks
remain pending. Do not interpret project creation as a working deployment.

## Payment check

- [Vercel pricing](https://vercel.com/pricing) lists Hobby at $0/month.
- [Hobby documentation](https://vercel.com/docs/plans/hobby) restricts the plan
  to personal, non-commercial use. Exceeding its included limits generally pauses
  the affected feature rather than purchasing additional usage. Use this for the
  synthetic academic demonstration, not as approval for institutional production.
- [Services](https://vercel.com/docs/services) are available on all plans.
  [Services pricing](https://vercel.com/docs/services/pricing) applies the normal
  function allowances. The prepared configuration has a Vite frontend and Django
  API, with no paid integrations, custom domain purchase or background daemon.
- [Daemons](https://vercel.com/docs/daemons) are also available on Hobby, but consume
  provisioned memory while idle. No daemon is configured. If email is demonstrated
  later, use the explicitly started laptop worker with the isolated demo database.
- The public pages establish the free tier, **not this account's signup outcome**.
  Confirm that the actual project belongs to a Hobby account and that signup does
  not require a payment method. Stop before any card request, Pro trial, paid
  upgrade, paid integration or domain purchase. No such action is authorized.
- Reuse capacity in the existing Aiven free service. Do not provision a paid
  database. Use a new database and dedicated role for the demonstration.

## Prepared architecture

`vercel.json` uses Vercel Services. The frontend service builds `frontend/portal`
and retains access to the sibling `frontend/guardian-results/src` dependency.
The repository is the project root. The Python service loads
`vercel_wsgi.py`, which selects `config.vercel_settings`. The entrypoint lives at
the repository root so dependency discovery uses the main requirements rather
than the separate Docker deployment requirements.

`/api`, `/admin`, `/static` and `/health` reach Django; other paths reach the SPA.
The browser keeps same-origin session cookies and CSRF checks. API/admin responses
and frontend HTML are not cached. Django static files are collected by Vercel.
The WSGI entrypoint never migrates databases or starts workers.

The optional `demo_hosting` app is enabled only by the demo settings:

- Authentication throttles use a shared database cache, not a function's local memory.
- Small private student documents and teaching materials are stored as database
  bytes. Downloads still go through the existing authorized views; the storage
  backend cannot generate a public URL. Restarting a function cannot lose an upload.
- Files are limited to 3 MiB, total stored file contents to 50 MiB, and incoming
  requests to 4 MiB. The total excludes database/index overhead, so leave room in
  Aiven for academic data, sessions and caches. The database is a bounded demo
  storage choice, not the long-term institutional file archive.
- The storage quota uses a database row lock and participates in the caller's
  transaction. Historical versions also count toward the cap.
- [Vercel Functions](https://vercel.com/docs/functions/limitations) allow a maximum
  4.5 MB request/response payload. Larger imports/exports need a different transfer
  design; use small synthetic demo fixtures.
- Email delivery defaults to disabled and fails explicitly if called. It never
  silently logs credentials or reports fake delivery success.
- Settings reject the normal integration database: the demo database name must
  start with `eee_demo_`, and `DEMO_SYNTHETIC_ONLY=true` is required.
- Aiven TLS stays at `verify-full`. `AIVEN_CA_PEM` supplies the multiline CA through
  environment settings; only the certificate is materialized into temporary space.

Existing laptop settings retain filesystem storage and their current behavior.
The deployment excludes local secrets, databases, private media, backups, hardware
captures, report sources and generated output through `.vercelignore`. Prefer a
Git-connected deployment from the reviewed feature branch, not a directory upload.

## Resume deployment

1. Connect the Vercel plugin or authenticate the official CLI. Verify the Hobby
   plan and the absence of any card/payment requirement in the actual account.
2. Import the existing GitHub repository and select the reviewed feature branch
   `codex/backend-academics-result-sharing`. Use repository root `.` and the
   committed service configuration; do not select only the frontend folder.
   Check that the frontend service can build its sibling guardian component.
3. Create a separate `eee_demo_...` database and dedicated application role on
   the existing free Aiven service. Do not copy real student data or the existing
   integration database. Do not run the application with the Aiven administrator.
   On this Windows workstation, after checking the local Vercel project link,
   run this in a separate PowerShell process from the repository root:

   ```powershell
   powershell -NoProfile -File .\scripts\prepare-vercel-demo.ps1
   ```

   It uses the ignored Aiven service profile and either inherits the configured
   password or requests it at a hidden prompt. It creates a randomly named empty
   database and a dedicated role limited to five connections, then checks TLS
   and role privileges. It never migrates or copies the integration database.
   Only the new demo credentials are retained, encrypted with Windows DPAPI in
   ignored `private-data/vercel-demo/environment.dpapi`; the administrator password
   is never saved. An existing bundle is not overwritten. If creation fails,
   inspect its stage before retrying because database creation is not transactional.
4. Set the private environment values from
   [the variable template](../deployment/vercel.env.example). Set the exact public
   hostname after Vercel assigns it. Use a stable generated Django secret.
   Do not put any database or mail secret into a `VITE_*` variable.
5. In an explicitly configured terminal for **that new database**, run the
   following commands. `config.vercel_settings` refuses an unprefixed target.
   No migration runs during a build or an HTTP request.

   ```powershell
   .\.venv\Scripts\python.exe manage.py check --deploy --settings=config.vercel_settings
   .\.venv\Scripts\python.exe manage.py migrate --plan --settings=config.vercel_settings
   .\.venv\Scripts\python.exe manage.py migrate --settings=config.vercel_settings
   ```

   Initialize roles and synthetic students/courses deliberately, and create demo
   accounts with private passwords. Do not commit passwords or seed a public
   default administrator password. `demo_hosting` migrations also create the shared
   cache table; no separate `createcachetable` step is needed.
6. Deploy with production configuration and verify `/health/live/`, `/health/ready/`, admin CSS,
   direct SPA routes, login/CSRF/logout, staff and student permission boundaries,
   result/attendance flows, and document/material upload and authorized download.
   Prove that uploads remain readable from a subsequent function invocation.
   Prefer staging without assigning domains, then promote the tested build.
   Preview and production should not silently share databases or queue consumers.
7. Promote only the verified synthetic demonstration. Record the exact URL,
   source revision, plan, test outcome and demo database identifier here.

## Local verification

The preceding checkpoint passed 603 backend tests (29 expected skips), 163 portal
tests, 14 guardian tests, portal lint/build, and the terminal C++ host suites and
86 Python tests. Sandbox restrictions initially blocked loopback tests; their
reruns outside the sandbox passed.

Demo deployment checks use isolated SQLite, never the existing Aiven database:
51 deployment/document/teaching tests passed (one PostgreSQL-specific skip),
and the optional demo migrations match the models.

```powershell
.\.venv\Scripts\python.exe manage.py test demo_hosting documents teaching --settings=config.demo_test_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.demo_test_settings
```

Vercel's actual build, Linux/Aiven connectivity, concurrent PostgreSQL upload quota
behavior and live browser smoke checks remain required before claiming deployment.
