# OAU EEE portal

React/Vite frontend for the departmental Django API. Imported from
`9iceguy/EEE-project` at `d3a4d4c190c3402dcfdebc7a867e676a41e7b769`, then adapted
on `feat/frontend-portal`. See [integration status](../../docs/frontend-integration.md).

## Run locally

Use Node 24 and a configured, separate development backend/database. Start the
backend using the project's backend setup instructions. For PowerShell, set
these variables **in the backend terminal before launching Django**:

```powershell
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://127.0.0.1:5175'
$env:PASSWORD_RESET_FRONTEND_URL = 'http://127.0.0.1:5175/reset-password'
python manage.py runserver 127.0.0.1:8000
```

The backend does not automatically load `.env` files. Configure email delivery
on that process if password recovery is needed. It must have an existing staff
or linked student account; self-registration is not supported.

In another terminal, from this directory:

```powershell
npm ci --ignore-scripts
npm run dev
```

Open `http://127.0.0.1:5175`. The fixed port avoids the older standalone
guardian-results app's port 5173. Vite forwards `/api/` to
`http://127.0.0.1:8000`, preserving the browser's Host header. Use consistent
127.0.0.1 addresses. To use another backend, set `VITE_API_PROXY_TARGET` for
Vite or put it in a local `.env` file (see `.env.example`). Never put credentials
or secrets in `VITE_*` variables.

## Routes and data

- `/login`: Django session login; role selection comes from the server.
- `/portal/:role/dashboard`: authenticated account workspace.
- `/portal/student/profile` and `/portal/student/results`: own records only.
- `/portal/staff/students`, `/portal/adviser/students`, `/portal/hod/students`:
  permission-scoped student list/detail and permitted document uploads.
- `/portal/hod/guardian-results`: existing HOD email preview/consent/queue/history
  workflow, embedded in the portal using the shared session transport.
- `/attendance`: permitted staff/HOD class selection, paginated student records
  and capture-file preview/import when the backend and permissions support it.
- `/recover-password`: request a reset email.
- `/reset-password?uid=...&token=...`: complete the reset. Existing reset links
  using `/recover-password` with these parameters redirect here.
- `/demo/:role/:section`: isolated illustrative prototype. Switching a demo role
  grants no account access. Demo controls never call live write endpoints.

Adviser is a staff workspace enabled by the backend's `adviser_levels`, not a
separate API account role. Frontend controls improve usability; Django remains
the authority for permissions, course assignments and field access.

Portal logout calls the backend and clears private views. Session expiry is
verified through `/api/auth/me/`; an ordinary denied operation does not log out
an otherwise valid account or cause an automatic retry loop. Records, report
previews and raw capture files stay in memory rather than browser storage.

Captures remain pending review after import and do not create attendance marks.
After an uncertain import, retry the identical bytes and preview hash to recover
the durable receipt. Keep the original device file. Documents use multipart
uploads and display the backend's accepted/needs-review decision; there is no
invented document list/download endpoint.

## Backend requirements and remaining scope

The main base includes academic, account, guardian and document APIs. Attendance
and database current-session selection still require the separately reviewed
backend changes currently in the backend workspace. A missing or denied endpoint
is displayed as an error/empty state; it is never filled with sample records.

Academic editing, catalog administration, messages, course registration,
timetables, appointments and the other prototype workflows still need dedicated
live screens and, where absent, agreed backend endpoints. They remain in the
separate demo instead of being presented as connected features.

The guardian worker/provider must be configured separately before delivering
emails. The embedded workflow remains email-only, requires HOD review and never
automatically repeats an uncertain send.

## Checks and production

```powershell
npm run lint
npm test
npm run build
```

GitHub Actions repeats these checks with Node 24. Serve `dist/` over the intended
site origin; route `/api/` to Django before the SPA fallback, and route frontend
deep links to `index.html`. Development Vite settings do not configure a
production reverse proxy. Configure Django hosts, trusted origins, HTTPS,
secure cookies, SMTP and `PASSWORD_RESET_FRONTEND_URL` for the real deployment.

The imported backend contracts remain in [api.md](api.md). Browser and synthetic
HTTP verification are recorded in the integration status document.
