# Guardian result sharing - React integration page

A separate live page for the HOD, beside the disposable frontend/prototypes demo.
It uses existing Django session/CSRF APIs and contains no demo login or seeded data.
Only the authenticated HOD loads the private workspace. Backend permissions still
enforce every read/write. Gmail secrets remain exclusively on the server.

## Run locally

Use Node 24 or a compatible version supported by the pinned Vite dependencies.
From this folder:

```powershell
npm.cmd ci
npm.cmd run dev
```

The page is http://127.0.0.1:5173/guardian-results/ . It proxies /api to Django
at http://127.0.0.1:8000, retaining cookie-based authentication. Before starting
Django in its configured terminal, trust that exact development origin:

```powershell
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1:5173'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Use the same hostname throughout; do not mix localhost and 127.0.0.1 cookies.
Use an existing HOD account and an already prepared development database. This
page does not initialize/migrate databases or create accounts. The Gmail setup
script affects only its terminal's child processes; API and worker must both
receive the actual deployment configuration.

## HOD workflow

1. Sign in with the departmental HOD account (not the Gmail credentials).
2. Select academic session/semester and up to 100 students. Selection survives
   paging/search; all selected names remain visible and can be removed.
3. Under Guardian email sharing, choose a selected student, inspect guardians
   and record email-sharing permission with its actual basis. Existing WhatsApp
   preferences are preserved. Missing guardian/contact details are managed in
   student administration, not guessed by this screen.
4. Preview emails. Review report contents, destinations and skipped diagnostics.
   No send happens until the HOD checks the review confirmation and clicks Send.
5. Follow the batch and individual statuses. Accepted by provider never means
   delivered/read. Known failures can be retried; uncertain submissions require
   review and are not retried. History reopens saved batches.

New batches use email only. Existing mixed-channel/WhatsApp batches can be
inspected, but this page cannot send or retry them. It never starts WhatsApp jobs.
Provider settings and the backend RESULT_SHARING_ENABLED gate must be ready
before real queuing. Preview remains usable before transport is enabled.

## Worker

From the same configured deployment environment and repository root:

```powershell
.\.venv\Scripts\python.exe manage.py process_result_shares --channel email --watch --interval 5 --limit 25
```

This is the administrator's process, not an HOD action. It polls only queued
email jobs. Stop requests finish the current submission before exiting; a hard
crash can leave processing outcomes requiring manual investigation. The limit
is per processing pass, not a Gmail daily quota or an automatic retry policy.
The existing reviewed-data checks and uncertain-submission behavior remain.

For Linux deployment, adapt deploy/result-email-worker.service and supply the
private environment described by deploy/result-email-worker.env.example.
Create a restricted service user, install Python dependencies and prepare the
same PostgreSQL schema the API uses. Store the real environment outside Git with
access limited to the service administrator. Only then install/enable the service.
No service or scheduled task is installed on this development laptop by this work.
Windows deployment needs an equivalent supervised process running the command
with privately supplied settings; a scheduled task cannot inherit a closed
interactive terminal's Gmail settings.

## Production frontend and later merge

```powershell
npm.cmd test
npm.cmd run build
```

Serve dist at /guardian-results/ on the same HTTPS origin as /api. Keep HTML
responses private/no-store, and proxy /api to Django. Do not expose the Vite
development server publicly. Apply the normal Django HTTPS/cookie settings and
host/origin configuration. Static JS/CSS bundles contain no reports or secrets.

src/api.js is the portable API adapter; src/App.jsx contains the workflow
components. Merge those into the finished React router/layout later, then remove
the temporary demo navigation. Keep session cookies, post-login CSRF refresh,
no-store requests, in-memory report state and stable preview request IDs.
Do not add reports, recipient contacts or passwords to localStorage, analytics or
logs. Repeated Send requests use the same batch ID/digest; network errors do not
create a new batch automatically. Changing selection or permissions invalidates
the old preview. Inactive/expired sessions clear the private workspace.

Tests cover API token rotation, auth loss, late responses, no write retries,
HOD-only data loading, preview retry IDs, review gating, uncertain outcomes,
non-email send blocking and logout cleanup. Backend tests cover worker channel
isolation, bounds and graceful stop. Live PostgreSQL concurrency and a real bulk
deployment remain separate from the successful single Gmail receipt test.
