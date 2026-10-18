# Frontend integration — 18 October 2026

The reviewed source import is followed by compatibility fixes on
`feat/frontend-portal`. The frontend runs under `frontend/portal/`; backend
application files and the original backend workspace are not changed by this work.

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

## Verification

`npm run lint`, `npm test` and `npm run build` run from `frontend/portal/`.
All passed after the final changes: **37 tests across 7 files**, clean lint,
and a production build with all four referenced local image assets present.
Regression coverage includes raw versus JSON/multipart bodies, CSRF rotation,
late session responses, permission denial versus expired sessions, server-derived
roles, real sign-out, reset links and validation, attendance pagination, late
class responses, reviewed upload/retry and the preserved guardian workflow.

Real HTTP verification used a loopback-only synthetic Django process with an
in-memory SQLite database. It combined the current backend workspace's attendance
code and this branch's existing document app **only for the isolated test**; this
does not merge or commit the pending backend changes. Through the actual Vite
proxy, the frontend API client passed session/CSRF login, student reads, class
records, JSONL preview/import/exact retry with the same receipt, unchanged
attendance-record count, multipart document upload and logout. No guardian
messages were sent, and no development/shared database was migrated.

In-app browser checks verified HOD and student login, rejection of a student's
HOD URL, live student profiles and upload entry point, embedded guardian catalog,
class selection/records and real logout followed by private-route rejection.
Synthetic data only was used. This does not validate production providers,
PostgreSQL concurrency, physical devices or institutional operation.

## Dependencies before release

1. Reconcile and review the pending attendance/current-session backend additions
   with `main` while preserving the document app. The frontend branch by itself
   does not contain those backend changes.
2. Configure the real backend origin, hosts/CSRF, HTTPS, reset email URL and SMTP;
   deploy the guardian worker/provider separately when delivery is intended.
3. Implement the remaining academic editing/administration, messaging and other
   prototype workflows as dedicated live screens. Their demo routes are not
   evidence of completed backend integration.
4. Apply normal project review/check requirements before merging the branch.

The original prototype and standalone guardian-results folders in the backend
workspace remain intact. Local synthetic verification scripts and screenshots
are stored in its ignored `tmp/frontend-compatibility-20261018/` folder.
