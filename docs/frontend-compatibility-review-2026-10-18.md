# Frontend compatibility review — 18 October 2026

**Decision:** suitable as the React frontend foundation, with integration work required. It is not yet the working frontend for the whole project. Import it in a dedicated frontend branch; do not merge its repository root over this project's root or describe its prototype screens as connected features.

## Versions reviewed

- Frontend: [9iceguy/EEE-project](https://github.com/9iceguy/EEE-project), `main`, commit [`d3a4d4c190c3402dcfdebc7a867e676a41e7b769`](https://github.com/9iceguy/EEE-project/tree/d3a4d4c190c3402dcfdebc7a867e676a41e7b769), “updated api workflow”.
- Local backend: `codex/backend-academics-result-sharing`, HEAD `89ebfba`, **including the existing uncommitted workspace changes**. Attendance and database current-session selection are among those changes.
- Our GitHub `main`: `2395e56cb1768fcd069efd3d7dee483e3c03d663`, confirmed through GitHub. It includes academic/account/guardian APIs and document upload, but not the local attendance/current-session additions.
- Separate frontend review checkout: `C:\Users\Ot\Downloads\EEE-frontend-review-20261018`. No frontend source changes were made there.

## What fits

| Area | Assessment |
| --- | --- |
| Application stack | React 19, Vite 8 and JavaScript can run alongside Django/DRF. Tailwind and animation dependencies remain in the frontend package. No backend framework replacement is needed. |
| Authentication transport | The API client uses `/api/`, same-origin session cookies, CSRF headers, and refreshes the CSRF token after login. It does not persist session tokens or passwords in browser storage. |
| Identity | Login consumes `username` and `password`; the returned `hod`, `staff`, and `student` roles match our serializer. Adviser capabilities must be derived from `adviser_levels` and permissions, since `adviser` is not a separate backend role. |
| API route coverage | Exercised 77 exported endpoint helpers with an instrumented fetch implementation. Their 80 captured requests covered 78 distinct route/method pairs; every pair resolves to a matching handler in the **local workspace**. This checks routing and methods, not every payload, permission, or response mapping. |
| Existing frontend work | A separate package can coexist with `frontend/prototypes/` and `frontend/guardian-results/`. The latter is already a live HOD guardian-results workflow and needs to be retained. |

## Findings to address

### 1. Portal screens still use demo identity, data, and logout (high priority)

[Portal.jsx](https://github.com/9iceguy/EEE-project/blob/d3a4d4c190c3402dcfdebc7a867e676a41e7b769/src/pages/Portal.jsx#L712) selects its role from the URL and a public role switcher, without consulting `useAuth`. A real login sends the user straight to this demo portal. Student records, results, approvals, messages, courses, and reports mostly use hard-coded data or local state. The file visibly labels itself as a prototype.

The portal's “Log out” button only displays a toast and navigates home; it does not call the logout API. The shared header has a real sign-out action, but that does not fix the portal button. Someone using the portal button remains authenticated.

Before connecting sensitive records, use the authenticated identity and effective permissions, handle session loading/expiry, and call `signOut` from every logout control. Keep role previews in a clearly separate demo flow. Visiting an HOD demo URL currently exposes illustrative UI; it does not bypass Django's API permissions.

### 2. Staff attendance reads the student's own-history API and masks failures (high priority)

[AttendanceDashboard.jsx](https://github.com/9iceguy/EEE-project/blob/d3a4d4c190c3402dcfdebc7a867e676a41e7b769/src/pages/AttendanceDashboard.jsx#L59) allows staff/HOD accounts, but loads records through `getMyAttendance()`. Our `/api/me/attendance/` requires a linked student profile and returns that student's own history; an ordinary HOD account receives **404**, reproduced in an isolated backend test.

The dashboard catches individual API failures and substitutes empty arrays, then falls back to synthetic staff records. It can still display “Connected” and “Live”. When classes exist, its description can claim those synthetic records came from the API. It also labels the table as staff attendance, while our model records student attendance in course classes. Its “Open sessions” count counts the first page of all visible classes without filtering status.

Use `listAttendanceSessions()` and `listAttendanceRecords(sessionId)` for staff/HOD; reserve `getMyAttendance()` for a student page. Map the actual response fields, handle pagination, and distinguish errors, empty results, and explicit demo mode. Add real class selection, roster confirmation, manual marking/corrections and pending-capture preview/import screens as required. The latest dashboard has no upload control despite having API helper functions.

### 3. Pending-capture upload helpers alter the required file transport (high priority for attendance uploads)

The upload helpers in [api.js](https://github.com/9iceguy/EEE-project/blob/d3a4d4c190c3402dcfdebc7a867e676a41e7b769/src/api.js#L533) supply `application/x-ndjson`, but the common request function overwrites that header with `application/json` and applies `JSON.stringify(body)` whenever a body is supplied.

An instrumented request confirmed this for both preview and import. Our backend rejects that content type with **415** and requires the unchanged JSONL file bytes. Sending JSON-wrapped text also changes the hash. Add an explicit raw-body transport that preserves the selected file bytes and content type; import must use the whole-file `file_sha256` returned by preview. Keep the preview/confirmation/receipt workflow described in [attendance-pending-batches.md](attendance-pending-batches.md).

### 4. Password recovery has a request form but no completion screen (medium priority)

`/recover-password` requests email successfully when backend recovery is configured. Although `confirmPasswordReset()` exists, no route or page consumes `uid` and `token` and submits a new password. The backend email link appends these parameters to `PASSWORD_RESET_FRONTEND_URL`; pointing it at the current recovery page cannot finish the reset. Add the completion form and configure the frontend URL and email delivery.

### 5. Production build omits images referenced by source-directory URLs (medium priority)

[Header.jsx](https://github.com/9iceguy/EEE-project/blob/d3a4d4c190c3402dcfdebc7a867e676a41e7b769/src/components/Header.jsx#L52) references `/src/assets/logo1.jpg`; [Hero.jsx](https://github.com/9iceguy/EEE-project/blob/d3a4d4c190c3402dcfdebc7a867e676a41e7b769/src/components/Hero.jsx#L5) uses `./src/assets/...` image strings. These strings remain in the built JavaScript, while those paths do not exist in `dist/`. Import the images as modules or place them in `public/` and reference their public paths. A successful build alone does not establish correct image rendering.

## Configuration and merge dependencies

- Vite defaults to port 5173, which is also the existing guardian-results app's port. Choose distinct development ports or integrate the routes deliberately. For example, keep guardian-results at 5173 and run the new portal at a fixed 5175.
- The frontend proxy uses `changeOrigin: true`. With our default empty `DJANGO_CSRF_TRUSTED_ORIGINS`, a browser-origin login is rejected. A Django test reproduced **403** for `Origin: http://localhost:5173` and **200** after that exact origin was trusted. Configure the actual frontend scheme/host/port explicitly; use consistent localhost/127.0.0.1 addresses. Repeat for a chosen alternative port. Production needs equivalent same-origin `/api/` forwarding and SPA deep-link fallback.
- Sixteen route/method pairs used by these helpers belong to attendance or current-session selection and are absent from GitHub `main`. Commit and review the backend additions before enabling those frontend features there. Passing local routing checks does not imply the same coverage on `main`.
- Our current backend branch predates the document-upload changes on `main`. Reconcile that work while preserving both `documents.urls` and the new attendance routes. The external frontend has no document-upload/OCR page or helper coverage for that existing feature.
- Guardian result-sharing helpers exist in the external API module, but there is no corresponding live screen. Retain/integrate `frontend/guardian-results/` and its tests instead of losing that functionality.
- Registration is correctly informational rather than public account creation. Timetables, appointments, learning resources, requests and registration approvals remain prototype features and are not evidence of implemented backend workflows.

## Recommended branch/import sequence

1. Checkpoint the existing backend work in focused commits and reconcile it with current `main`, preserving the document feature. Do this separately from the frontend import.
2. From the reconciled base in a clean checkout, create `feat/frontend-portal` in **our repository**, following `CONTRIBUTING.md`.
3. Import the pinned external source under `frontend/portal/`, with its own `package.json`, lockfile, Vite configuration and README. A subtree import or a focused copy commit works. Preserve existing frontend subdirectories and backend files.
4. Resolve the findings above and connect the required user journeys. Add frontend CI for `npm ci`, lint and production build, plus meaningful tests for authentication, role/permission handling, raw uploads and attendance error states.
5. Review the pull request with the team's applicable checks and approvals before merging. A frontend foundation can be reviewed incrementally, but do not mark the whole project's interface complete while its main pages are demos.

The repositories have **no common Git ancestor**, verified with `git merge-base` against both the local backend HEAD and our `main`. A root-level unrelated-history merge would mix their separate README, package and source layouts. Import the app under its intended directory instead.

## Validation evidence and limits

- `npm ci --ignore-scripts --no-audit --no-fund`: passed after a registry connection retry; lockfile unchanged.
- `npm run lint`: passed.
- `npm run build`: passed using Node `v24.22.0` and npm `11.19.1`; image-path defect identified by inspecting the output.
- Instrumented frontend helpers and Django route/method resolution: **77 helpers, 80 requests, zero route/method mismatches** against the active local backend; raw-upload mismatch reproduced.
- Isolated Django requests: trusted-origin login succeeds, untrusted-origin login is rejected, and HOD own-student attendance returns 404.
- Existing backend checks passed: **141 tests discovered, 126 passed, 15 skipped**, using `.venv\Scripts\python.exe manage.py test accounts.tests accounts.test_security accounts.test_lifecycle attendance --settings=config.test_settings --verbosity=1`. These use isolated in-memory SQLite; PostgreSQL concurrency and process-restart checks are skipped. The successful run included loopback HTTP tests.
- This review did not run a real browser end-to-end session or validate a deployed production server. Most UI workflows are visibly unwired; route matches and passing builds do not validate them.

Reproduction scripts and captured synthetic request metadata are in the ignored local folder `tmp/frontend-compatibility-20261018/`. Existing project source, branches, development databases and the external GitHub repository were not modified.
