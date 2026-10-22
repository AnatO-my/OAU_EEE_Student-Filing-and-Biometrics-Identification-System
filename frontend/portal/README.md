# OAU EEE departmental portal

The React shell was imported from [9iceguy/EEE-project](https://github.com/9iceguy/EEE-project)
at reviewed commit `d3a4d4c190c3402dcfdebc7a867e676a41e7b769` (`updated api workflow`).
This is an integrated copy, without merging the repositories' Git histories.

The production router uses `src/live/LivePortal.jsx`. Imported
`src/pages/Portal.jsx` and `src/pages/AttendanceDashboard.jsx` remain unmounted
prototype references; their sample records and role switcher are not live routes.
`/admin/` belongs to Django. `/student` and `/portal` resolve from the authenticated
identity, rather than selecting a public role.

## Run locally

Tested with Node **24.22.0** and npm **11.19.1**. From this directory:

```powershell
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd run dev
```

Open `http://127.0.0.1:5175`. The fixed development server proxies `/api`,
`/admin` and `/static` to Django at `http://127.0.0.1:8000`, retaining the browser
host/origin. Django must trust `http://127.0.0.1:5175` for CSRF. Use the same
hostname for both services. The root laptop launcher starts services with the
configured Aiven terminal environment when available.

`VITE_API_PROXY_TARGET` optionally changes the development proxy target.
Production always uses relative `/api/` requests with same-origin session cookies.
No frontend `.env` file, database password or sending-account secret is required.

## Live workflows

- Student: own profile, verified results, GPA/CGPA, adviser/HOD messages and own attendance.
- Authorized staff: scoped student directory, guardian contacts and permitted result entry/corrections/verification.
- Attendance staff: accessible classes, fixed-roster selection, stable-ID manual marks, audited corrections, and permitted class opening/closing.
- HOD: current-session selection, revision-bound roster confirmation, course staff assignment and reviewed guardian email sharing.
- Capture importers: original JSONL bytes, explicit preview review, whole-file digest import and durable receipt/replay recovery. These imports create no attendance marks.
- Account settings under the username/avatar: password change, HOD staff accounts/permissions, part-adviser assignment and explicit password-confirmed HOD transfer. Real logout, reset request and `/reset-password?uid={uid}&token={token}` completion remain available.
- Registration: scoped lookup, student registration, profile completion and HOD UTME-to-matriculation promotion.
- Upload results: master-sheet PDF to CSV and matched-score preview in one action, with correction approvals and receipt/history recovery. Student registration stays under Students; unknown matric numbers hold the result batch until registered separately.

The integrated guardian page imports the established `Workspace` component from
`../guardian-results/src/App.jsx`, with a shared-session adapter and scoped CSS.
Its consent, stable preview IDs, reviewed digest, uncertainty handling and
email-only restrictions remain intact. Build contexts must include both
`frontend/portal` and `frontend/guardian-results/src`. A second guardian npm
installation is unnecessary for the portal build; its standalone app is preserved.

Django authorizes every request. Access failures are visible and do not fall
back to sample data. A confirmed lost session removes private content. Responses
from earlier sessions are discarded, and writes are never retried automatically.
Passwords, contacts and reports are not stored in localStorage or analytics.

## Build and verify

```powershell
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

Mount `dist/` at `/`, with an SPA fallback for client routes. Preserve Django
`/api/`, `/admin/` and `/static/` routing and serve hashed `dist/assets/` directly.
Keep HTML private/no-store. `vite preview` alone does not proxy the Django API.
The separate guardian suite runs with `npm.cmd test` in `../guardian-results`.

## Explicit limits

Timetables, appointments, resource requests, document-upload pages, fingerprint
identity matching and automatic attendance metrics are not working features in
this integration. Account provisioning, catalogue/grading setup
and some lifecycle operations remain in authorized Django administration.

Catalogue endpoints are currently HOD-only. Other roles see accurately labelled
offering and student record IDs where responses lack names. Guardian sending
still requires backend transport configuration and the worker. Frontend tests
do not send real guardian emails or change the Aiven database.

See [the integration checkpoint](../../docs/frontend-integration-checkpoint.md)
and the root [API contract](../../api.md) for runtime hooks and validation.
