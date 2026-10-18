# Frontend integration — 18 October 2026

The reviewed source import is followed by compatibility fixes on
`feat/frontend-portal`. The frontend runs under `frontend/portal/`. Reconciled
attendance/calendar backend changes from `feat/attendance-backend` (`15ff6db`)
are included in local merge `5742524`. The original backend working checkout
and its unrelated pending changes remain intact. See the
[backend reconciliation report](attendance-reconciliation-2026-10-18.md).

## Completed

- Protected live account routes and server-derived roles/permissions; adviser
  navigation derives from staff adviser levels. Demo previews moved to `/demo/`.
- Real logout in the live portal and attendance workspace; private UI disappears
  after logout, confirmed expiry, identity changes and relevant permission loss.
  A denied resource triggers identity verification without replaying the denied
  operation or mistaking every 403 for logout.
- Live own-student profile/results and scoped staff student list/detail.
- Staff attendance selects a real class and reads that class's paginated records.
  Student-only own-history calls and synthetic staff fallback were removed.
- Raw JSONL transport preserves file bytes, content type and the reviewed
  whole-file hash. The UI requires preview/review before import and retains the
  same bytes/hash for uncertain-response recovery. Import never marks attendance.
- Reset completion form, mismatch/server-error handling and compatible redirects
  for older email links. Successful completion removes the token query string.
- Imported image assets included in production output; fixed development port
  5175, Host-preserving API proxy and explicit backend/reset configuration notes.
- The existing guardian email workspace and its tests are preserved inside the
  portal. The embedded component uses the shared API transport; styles are scoped.
  Its asynchronous catalog/preference/history loaders discard obsolete data.
- Permission-gated document upload uses the existing multipart endpoint and its
  quality decision. Replacement requires an explicit user review checkbox.
- Frontend CI installs the lockfile and runs lint, regression tests and build.
- Attendance and database current-session selection are reconciled with the main
  backend, retaining the document app. Account identity, student records,
  results, guardians, export, messaging and document uploads share the selected
  academic-session scope. Backend CI covers attendance and documents together.

## Verification

`npm run lint`, `npm test` and `npm run build` run from `frontend/portal/`.
All passed after the final changes: **37 tests across 7 files**, clean lint,
and a production build with all four referenced local image assets present.
Regression coverage includes raw versus JSON/multipart bodies, CSRF rotation,
late session responses, permission denial versus expired sessions, server-derived
roles, real sign-out, reset links and validation, attendance pagination, late
class responses, reviewed upload/retry and the preserved guardian workflow.

Real HTTP verification used a loopback-only synthetic Django process with an
in-memory SQLite database. After reconciliation, these checks passed against the
actual merged checkout using its normal app registration and URL configuration.
Through the actual Vite proxy, the frontend API client passed session/CSRF login,
student reads, class records, JSONL preview/import/exact retry with the same
receipt, unchanged attendance-record count, multipart document upload and
logout. No guardian messages were sent, and no development/shared database was
migrated.

The reconciled backend passed **360 tests on isolated PostgreSQL 16.15 with no
skips**, including concurrency, real HTTP/restart and document regression cases.
The frontend code is unchanged from its validated revision; both backend and
frontend were checked against their tested commits after the merge.

In-app browser checks verified HOD and student login, rejection of a student's
HOD URL, live student profiles and upload entry point, embedded guardian catalog,
class selection/records and real logout followed by private-route rejection.
Synthetic data only was used. These browser and HTTP checks do not validate
production providers, physical devices or institutional operation.

## Dependencies before release

1. Review the reconciled backend and frontend branch together. Approve the
   schema/data reconciliation for the target database before applying academic
   migration `0006` and attendance migrations `0001`–`0003` there.
2. Configure the real backend origin, hosts/CSRF, HTTPS, reset email URL and SMTP;
   deploy the guardian worker/provider separately when delivery is intended.
3. Implement the remaining academic editing/administration, messaging and other
   prototype workflows as dedicated live screens. Their demo routes are not
   evidence of completed backend integration.
4. Apply normal project review/check requirements before merging the branch.

The original prototype and standalone guardian-results folders in the backend
workspace remain intact. Local synthetic verification scripts and screenshots
are stored in its ignored `tmp/frontend-compatibility-20261018/` folder.
