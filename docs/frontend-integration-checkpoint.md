# Frontend integration checkpoint — 21 October 2026

## Source and routing

Imported the reviewed React source into `frontend/portal/` from the local checkout
verified at commit `d3a4d4c190c3402dcfdebc7a867e676a41e7b769` of
`9iceguy/EEE-project`. No unrelated-history merge, Git commit or remote push was
performed. The existing `frontend/guardian-results` application is preserved.

Production routes use `frontend/portal/src/live/LivePortal.jsx`. The public role
picker and synthetic dashboard records are not mounted. Imported prototype files
remain references only. Identity, staff/superuser flags, effective permissions and
adviser levels come from `/api/auth/me/`; an incorrect role URL returns to the
signed-in user's overview. Logout calls the backend. A confirmed lost session
unmounts private content, and responses from an earlier session are discarded.

## Integrated journeys

| Audience | Working frontend journey |
| --- | --- |
| Student | Own profile, verified results, GPA/CGPA, adviser/HOD messages, own attendance |
| Authorized staff | Scoped student search/detail, guardian contact create/edit, result entry/score correction/verification |
| Attendance staff | Complete accessible class list, class details and record pagination, stable-ID manual marks, audited corrections, open/close class |
| HOD | Guarded current academic session, complete roster-candidate review and revision-bound confirmation, course staff assignment |
| Capture importers | Original JSONL bytes, metadata/count preview, explicit review, whole-file digest import, durable receipt/replay recovery |
| HOD guardian sharing | Existing consent/preferences, student selection, stable preview request, reviewed digest/send gate, batch status/history, known-failure retries and uncertain-outcome handling |
| Accounts | Password change, privacy-preserving reset request, emailed uid/token completion |

Attendance errors and empty results have separate states. Staff use class-session
and class-record endpoints; students use only `/api/me/attendance/`. The class
count loads every accessible page and counts `status=open`. Missing marks are not
labelled absent. Pending imports remain unidentified evidence and do not claim
fingerprint identity, authenticated hardware or successful attendance marks.

The API adapter preserves `File`/`Blob` bodies with `application/x-ndjson` and
sends the preview's whole-file `file_sha256` on import. It does not wrap or stringify
file bytes. Writes are never retried automatically. An action 403 is checked
against `/api/auth/me/` before removing a still-valid identity. CSRF is fetched
again after login; tokens remain in memory.

## Runtime hooks

- Main development URL: `http://127.0.0.1:5175`, fixed host and strict port.
  Vite proxies `/api`, `/admin` and `/static` to Django port 8000 without rewriting
  the original host/origin. Django must trust this exact frontend origin.
- Production: `npm ci --ignore-scripts --no-audit --no-fund`, then
  `npm run build` in `frontend/portal`; mount `dist/` at `/`, preserve Django's
  `/api/`, `/admin/` and `/static/`, and supply an SPA fallback for client routes.
  No production frontend environment variable or external API origin is required.
- `VITE_API_PROXY_TARGET` changes the development proxy target only.
- Password reset frontend template:
  `http://127.0.0.1:5175/reset-password?uid={uid}&token={token}` locally; use the
  eventual application origin when hosting.
- Integrated guardian route: `/portal/hod/guardian-results`. Its established
  `Workspace` component is imported from `frontend/guardian-results/src/App.jsx`.
  Build contexts must include that sibling source. Vite deduplicates React.
  The standalone guardian app and its `/guardian-results/` base remain intact.
- Sending remains a backend/worker concern. The frontend contains no Aiven,
  SMTP or worker credentials and no personal-data browser persistence.

## Validation

Tested with Node 24.22.0 and npm 11.19.1 on this laptop:

- Portal production build passes. Logo and carousel images are emitted as
  hashed assets rather than broken `/src/assets` strings.
- Portal ESLint passes.
- Portal tests cover CSRF rotation, byte preservation, action-denial versus
  session expiry, stale responses, no automatic write retries, role guards,
  real logout, staff/student attendance endpoints, all-page counts, visible
  failures, preview invalidation, exact-file receipt retry and reset completion.
  All **18 tests pass**.
- Existing standalone guardian suite passes: **13 tests**. An initial run while
  four validation processes ran concurrently had one 1-second UI lookup timeout;
  the unchanged suite passed sequentially.
- The parent integration task confirmed HOD and student login/CSRF rotation,
  student directory loading, selected-class attendance, guardian workspace,
  student verified results and server-side logout in a browser against an
  isolated PostgreSQL/backend fixture. A student visiting the HOD URL returned
  to the student workspace. No Aiven records or real contacts were used.
- After starting `scripts/start-local.ps1` from the configured Aiven terminal,
  the user confirmed successful administrator sign-in and HOD portal loading
  at `http://127.0.0.1:5175`. Credentials remained private.

These tests do not constitute a production deployment, an Aiven data import,
a real guardian email send or biometric reconciliation.

## Explicit limits

Current catalogue endpoints are HOD-only; other roles see accurately labelled
offering/student record IDs where responses lack names. Account provisioning,
student-profile edits, catalogue/grading setup and some lifecycle workflows
remain in authorized Django administration. Timetables, appointments, resource
requests, document uploads, biometric identity resolution and attendance
percentages/warnings are not represented as working features.
