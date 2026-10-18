# Frontend-to-backend API reference

**Project:** OAU EEE Student Records & Identification System  
**Checked against the active workspace:** 18 October 2026  
**Frontend direction:** React  
**Backend:** Django and Django REST Framework, using session authentication

This document explains how React sends a user's instructions to the backend,
which methods currently exist, what each method accepts and returns, and what
still needs implementation. The active Python routes, serializers and services
are the authority for the contracts below. The legacy portal and browser
prototype contain additional workflows that are not active backend APIs.

**Implemented** means that an operation exists in the active backend. It does
not mean that its React screen, shared PostgreSQL integration or production
deployment has been completed. All JavaScript and JSX below are commented
integration examples. A separate live guardian-email React page now exists in
[frontend/guardian-results](frontend/guardian-results/README.md), linked from the
disposable demo. Other prototype workflows remain synthetic until integrated.

## Contents

1. [How instructions travel](#1-how-instructions-travel)
2. [HTTP methods and request conventions](#2-http-methods-and-request-conventions)
3. [Authentication, permissions and browser setup](#3-authentication-permissions-and-browser-setup)
4. [Shared commented React API client](#4-shared-commented-react-api-client)
5. [Implemented authentication and account methods](#5-implemented-authentication-and-account-methods)
6. [Implemented student and guardian methods](#6-implemented-student-and-guardian-methods)
7. [Implemented messaging methods](#7-implemented-messaging-methods)
8. [Implemented academic methods](#8-implemented-academic-methods)
   - [Current academic session and attendance](#86-current-academic-session-and-attendance)
9. [Implemented guardian result-sharing methods](#9-implemented-guardian-result-sharing-methods)
10. [Calling methods from React screens](#10-calling-methods-from-react-screens)
11. [Methods and integration work not completed yet](#11-methods-and-integration-work-not-completed-yet)
12. [Source files and maintenance](#12-source-files-and-maintenance)

## 1. How instructions travel

```text
User clicks a button, submits a form or changes a search filter
  -> React event handler or read effect
  -> Named JavaScript API method
  -> HTTP request to /api/... with query parameters or a JSON body
  -> Django URL route selects a view
  -> Authentication, CSRF, permissions and serializers check the request
  -> Backend services enforce scope and academic rules
  -> Django ORM reads or writes the configured database
  -> HTTP response returns data or validation errors
  -> React updates the screen
```

React sends an instruction such as "change this score to 68.50". The backend
chooses the authenticated actor, checks their permissions, saves the change and
returns the saved record. React must not send database queries or treat a hidden
button as authorization.

The current browser contract is REST over HTTP, with JSON for ordinary data and
a CSV response for student-profile export. Browser `fetch()` can call this
contract directly without an additional HTTP library. React does not provide a
separate network protocol. See the [Fetch API reference](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).

## 2. HTTP methods and request conventions

### 2.1 What each HTTP method does

| Method | Instruction it expresses | Current example | Important behavior |
| --- | --- | --- | --- |
| `GET` | Read records, search, fetch a preview or inspect status. | `GET /api/students/?current_level=200` | Put filters in the query string. Do not use GET to save changes. |
| `POST` | Create a record or request a named action. | `POST /api/results/` or `POST /api/results/7/verify/` | Usually send a JSON body and CSRF header. An action may return 200, 201 or 202. |
| `PATCH` | Change the supplied fields of an existing record. | `PATCH /api/students/{student_id}/` | Omitted fields retain their values. Each endpoint permits specific fields. |
| `PUT` | Submit the complete payload for the specific operation. | `PUT /api/students/{student_id}/account/` | Here it links an existing account. Guardian-sharing PUT supplies both channel flags and evidence. It is not a general student replacement method. |
| `DELETE` | Request removal of a resource. | No active application DELETE route. | Documented as unfinished below. Do not infer deletion support from the client helper. |
| `HEAD` | Inspect the headers/status of a readable route without its body. | Readable DRF views normally provide HEAD alongside GET. | Not a separate business operation; do not try to parse a JSON body. Access checks still apply. |
| `OPTIONS` | Ask a view for HTTP metadata. | DRF provides OPTIONS metadata, subject to view permissions. | Does not grant access or replace this API contract. Metadata can vary by view. |

### 2.2 Paths, IDs and values

- The base path is **`/api/`**. Authentication uses **`/api/auth/`**.
- Preserve the trailing slash on every route. Do not depend on a redirect for a
  request that contains a body.
- `{student_id}`, `{guardian_id}` and `{batch_id}` represent UUID strings.
- `{result_id}`, `{message_id}`, `{scale_id}`, `{offering_id}` and
  `{requirement_id}` represent integer IDs.
- Student `identifier_value` is a matriculation/UTME identifier, not the UUID
  used in paths. Preserve identifiers and phone numbers as strings.
- The GPA query and result filters use a session **name**, such as `2026/2027`.
  Offering creation and result-sharing preview use an academic-session **ID**.
- Semester values are exactly `harmattan` and `rain`.
- Scores accept decimal values from `0` to `100`, with at most two decimal
  places. Send strings such as `"68.50"` to preserve the entered value. Decimal
  responses, including GPA/CGPA, are strings; unavailable averages are `null`.
- Examples use synthetic values. Existing database IDs must come from real API
  responses in the configured development environment.
- Only send the documented write fields. Several serializers ignore unknown or
  read-only fields rather than rejecting them, so an ignored field does not mean
  that the backend saved it.

### 2.3 Pagination

All current paginated lists use **20 records per page** and accept `page`:

```json
{
  "count": 35,
  "next": "http://localhost:8000/api/students/?page=2",
  "previous": null,
  "results": []
}
```

`results` holds the actual records; this example omits them for readability.
There is no implemented client-selected `page_size`. Preserve active filters
when changing pages. Behind the frontend proxy, request the same relative API
path with the next page number; do not assume a returned absolute URL points at
the browser's frontend origin. Student export is not paginated.

### 2.4 Responses and errors

| Status | Meaning in this backend | React handling |
| --- | --- | --- |
| `200` | A read, update or synchronous action succeeded. | Use the returned record or detail message. |
| `201` | A record or persisted sharing preview was created. | Use its backend-generated ID; sharing preview itself sends no messages. |
| `202` | Guardian deliveries were queued or failed deliveries were requeued. | Show queue status and inspect the batch later. It does not mean delivered. |
| `204` | Logout succeeded and has no response body. | Clear signed-in UI state; do not call `response.json()` on an empty body. |
| `400` | Invalid input, missing required fields, stale expected values or a business rule failure. | Show field/non-field errors and refresh stale data before resubmitting. Invalid login credentials also return 400. |
| `403` | Missing authentication, denied permission or invalid/missing CSRF. | Check the current session and error detail. SessionAuthentication commonly returns 403 for anonymous requests; do not depend on 401 alone. |
| `404` | A resource does not exist or is outside the caller's visible scope. | Show an unavailable-record state. Do not reveal whether an inaccessible record exists. |
| `405` | The route does not support the requested method. | Correct the client method; for example, student detail supports PATCH rather than PUT. |
| `429` | Login or password-recovery throttling. | Respect `Retry-After`; do not immediately retry in a loop. |
| `503` | Password recovery is not configured. | Show temporary unavailability; configuration belongs on the server. |
| `5xx` / network failure | Backend, proxy, transport or unexpected service failure. | Preserve the form and display retry guidance. A lost response does not prove that a write failed. |

Typical serializer errors are an object of field arrays:

```json
{
  "score": ["Ensure this value is less than or equal to 100."],
  "non_field_errors": ["Refresh and review the current record."]
}
```

Other errors use `{"detail":"..."}`. Django CSRF/proxy failures can return HTML
instead of JSON. The client below detects that and uses a generic message rather
than displaying a server HTML page as application data. Fetch resolves normally
for HTTP errors, so the client must check `response.ok`. See [MDN's Fetch response handling](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).

## 3. Authentication, permissions and browser setup

### 3.1 Same-origin React setup

Use relative `/api/...` URLs. Configure the chosen React development server to
proxy `/api` to Django, commonly `http://127.0.0.1:8000`. The browser should see
one origin for the React page and its API requests. Production should likewise
route `/api` to Django under the frontend's HTTPS origin.

The repository has standalone frontend prototypes, not a configured React
development server. Proxy installation is still integration work. No permissive
CORS middleware or bearer/JWT authentication is currently configured. Calling
Django directly from a different browser origin requires a separately completed
deployment/authentication configuration; `credentials: "include"` by itself
does not solve CORS or cookie policy.

Backend origin/host settings come from `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS`. Configure them for the actual proxy arrangement.
The application does not automatically load `.env.example` or `.env`.

### 3.2 Cookie and CSRF sequence

1. `GET /api/auth/csrf/` obtains a CSRF cookie and returns `csrfToken`.
2. `POST /api/auth/login/` sends username/password and `X-CSRFToken`.
3. Django establishes the session and rotates the CSRF token. Fetch a **fresh**
   token after successful login.
4. Send the session cookie with all requests and the current CSRF header with
   every POST/PATCH/PUT operation, including public recovery requests.
5. `GET /api/auth/me/` restores the signed-in identity on a page reload.
6. `POST /api/auth/logout/` ends the session. Clear private data held by the UI.

The session cookie is HttpOnly and SameSite=Lax. React should not read it or
store a session token in localStorage. Session and CSRF cookies require HTTPS
when `DEBUG=false`. The default session lifetime is twelve hours unless
`DJANGO_SESSION_COOKIE_AGE_SECONDS` overrides it.

Retain the returned CSRF token in memory, refresh after login, and obtain it
again after a page reload. For AJAX writes Django expects the token in the
`X-CSRFToken` header; see [Django 5.2 CSRF guidance](https://docs.djangoproject.com/en/5.2/howto/csrf/).

### 3.3 Permission shorthand used below

| Label | Exact meaning |
| --- | --- |
| Public + CSRF | No signed-in account needed; a write still needs the CSRF token/cookie. |
| Signed in | An authenticated account. Own-student routes additionally need a linked student profile. |
| HOD | An authenticated, active user with both `is_staff=true` and `is_superuser=true`. A group or display label alone is insufficient. |
| Student reader | Staff with `students.view_student`; ordinary staff must have an active adviser assignment for the resolved current academic session and the student's current level. HOD has department scope. |
| Student creator | Staff with `students.add_student`; ordinary staff must have an active assignment for the new record's level in the current configured session. |
| Student editor | Staff with `students.change_student` and visibility of the record; ordinary staff cannot change level or academic status. |
| Guardian reader/writer | Student reader plus `students.view_guardian`; POST adds `students.add_guardian`, PATCH adds `students.change_guardian`. |
| Academic reader | Staff with `students.view_student` and `academics.view_result`, plus current adviser scope. Active HOD satisfies the academic permission check. |
| Academic creator/editor/verifier | Academic reader plus `academics.add_result`, `academics.change_result` or the independent `academics.verify_result`, respectively. |
| Adviser sender | Staff with `accounts.send_adviser_message` and ownership of the selected active assignment for the configured current session. |
| Student exporter | Student reader plus the independent `students.export_student` permission. |

For student creation, the view requires `add_student`; it does not separately
require `view_student` for POST. Reading the new record afterward still needs
reader permissions. For PATCH, the visible-record lookup means ordinary editors
also need reader visibility. An empty current-session setting gives ordinary
staff no adviser-scoped reads and prevents scoped writes/messaging.

Login and `auth/me/` return `role`, `permissions`, `groups` and `adviser_levels`
as UI hints. They do not expose adviser assignment IDs. Explicit course-staff
assignments now authorize attendance only, with independent attendance permissions;
they do not expand profile/result permissions or implement lecturer score batches.
The current session resolves from the database selection, with
CURRENT_ACADEMIC_SESSION as bootstrap fallback. The backend checks authorization
on every request.

## 4. Shared commented React API client

The blocks in sections 4–9 can be assembled, in order, into a future
`frontend/src/api.js`. They use browser APIs and contain no React-specific
dependency, so components can share them. This is a suggested module location;
the file is not created by this documentation change.

```javascript
// Keep the CSRF token only in this browser tab's module memory.
// The session cookie belongs to Django and is sent by the browser automatically.
let csrfToken = null;
let csrfRequest = null;

// Carry server status and structured validation errors to the React screen.
// Network failures and AbortError are left as their original browser errors.
export class ApiError extends Error {
  constructor(message, status, details = null, retryAfter = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

// Encode query values safely: a session such as 2026/2027 becomes URL-safe.
// Keep false and zero; omit only absent values and empty optional filters.
function buildApiUrl(path, query = {}) {
  if (!path.startsWith("/api/")) {
    throw new TypeError("Use a relative /api/ path for this client.");
  }
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url;
}

// Encode IDs before inserting them into paths. The backend still validates
// UUID/integer formats and permissions; encoding is not authorization.
function pathId(value) {
  return encodeURIComponent(String(value));
}

// This is the single transport method used by every named method below.
// It handles cookies, CSRF, JSON, empty responses, downloads and HTTP failures.
// It deliberately does not automatically retry writes: they may already exist.
export async function apiRequest(path, {
  method = "GET", query = {}, body, signal, responseType = "json",
} = {}) {
  const verb = method.toUpperCase();
  const headers = { Accept: responseType === "blob" ? "text/csv" : "application/json" };
  const isWrite = !["GET", "HEAD", "OPTIONS"].includes(verb);

  if (isWrite) {
    // Public login/recovery requests also need this token before submission.
    headers["X-CSRFToken"] = await getCsrfToken();
  }
  if (body !== undefined) {
    // All currently documented write endpoints use JSON, not file uploads.
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(buildApiUrl(path, query), {
    method: verb,
    credentials: "same-origin",
    cache: "no-store",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    // CSRF errors or proxy failures may be HTML. Do not render that HTML.
    const text = await response.text();
    let details = null;
    if ((response.headers.get("Content-Type") || "").includes("application/json")) {
      try { details = JSON.parse(text); } catch { /* Retain a generic error. */ }
    }
    const message = details?.detail || details?.non_field_errors?.[0]
      || `The request failed (${response.status}).`;
    throw new ApiError(message, response.status, details, response.headers.get("Retry-After"));
  }

  // Logout returns 204; HEAD also has no body even when its status is 200.
  if (response.status === 204 || verb === "HEAD") return null;
  if (responseType === "blob") return response.blob();

  // A successful HTML response usually indicates an incorrect proxy/route.
  // Detect it rather than pretending it is a valid backend JSON record.
  if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
    throw new ApiError("Expected a JSON API response. Check the API proxy.", response.status);
  }
  return response.json();
}

// GET reads data and supports query filters plus AbortController cancellation.
function apiGet(path, query = {}, signal) {
  return apiRequest(path, { query, signal });
}

// POST creates records or executes a named backend action.
function apiPost(path, body = {}) {
  return apiRequest(path, { method: "POST", body });
}

// PATCH changes only the fields supplied in this operation's payload.
function apiPatch(path, body) {
  return apiRequest(path, { method: "PATCH", body });
}

// PUT is used only for the two documented link/preference operations.
function apiPut(path, body) {
  return apiRequest(path, { method: "PUT", body });
}

// GET /api/auth/csrf/: obtain a token and ensure Django sets the CSRF cookie.
// Share an in-flight bootstrap so simultaneous first writes do not duplicate it.
// This GET does not require a token, so it cannot recurse into write bootstrap.
export async function getCsrfToken({ refresh = false } = {}) {
  if (refresh) {
    csrfToken = null;
    csrfRequest = null;
  }
  if (csrfToken) return csrfToken;
  if (!csrfRequest) {
    csrfRequest = apiGet("/api/auth/csrf/")
      .then(({ csrfToken: token }) => {
        csrfToken = token;
        return token;
      })
      .finally(() => { csrfRequest = null; });
  }
  return csrfRequest;
}
```

Serialize authentication transitions in the UI: complete login and its token
refresh before allowing other writes, and complete logout before starting a new
login. Do not change identities while requests from the previous identity are
still in flight. Clearing private React/query-cache state belongs to the
application's authentication boundary.

## 5. Implemented authentication and account methods

### 5.1 Route catalog

| Client method | HTTP route | Access | Input | Success |
| --- | --- | --- | --- | --- |
| `getCsrfToken` | `GET /api/auth/csrf/` | Public | None | 200 `{csrfToken}`; sets CSRF cookie. |
| `login` | `POST /api/auth/login/` | Public + CSRF | `username`, `password` | 200 identity; establishes session. |
| `logout` | `POST /api/auth/logout/` | Signed in + CSRF | Empty object | 204, no body. |
| `getCurrentUser` | `GET /api/auth/me/` | Signed in | None | 200 identity. |
| `changePassword` | `POST /api/auth/password/change/` | Signed in + CSRF | `current_password`, `new_password` | 200 `{detail:"Password changed."}`. |
| `requestPasswordReset` | `POST /api/auth/password/reset/` | Public + CSRF | `email` | 200 generic detail; 503 if recovery is unconfigured. |
| `confirmPasswordReset` | `POST /api/auth/password/reset/confirm/` | Public + CSRF | `uid`, `token`, `new_password` | 200 detail; does not sign in. |
| `createStudentAccount` | `POST /api/students/{student_id}/account/` | HOD | `username`, `email`, `password` | 201 identity of the newly linked student account. |
| `linkStudentAccount` | `PUT /api/students/{student_id}/account/` | HOD | `account_id` | 200 identity of the linked existing account. |

Identity fields are `id`, `username`, `first_name`, `last_name`, `email`,
`is_staff`, `is_superuser`, `groups`, `permissions`, `adviser_levels` and `role`.
`role` is `hod`, `staff` or `student`. There is no separate `lecturer` or
`part_adviser` role value in this response.

### 5.2 Commented methods

```javascript
// POST login: authenticate an existing staff account or linked student account.
// The API uses username/password; matriculation/surname login is not implemented.
// Return the signed-in identity, then refresh CSRF because Django rotated it.
export async function login(username, password) {
  const identity = await apiPost("/api/auth/login/", { username, password });
  await getCsrfToken({ refresh: true });
  return identity;
}

// POST logout: end the backend session; successful logout returns no JSON body.
// The component/auth provider must then discard identity and cached private data.
export async function logout() {
  await apiPost("/api/auth/logout/");
  csrfToken = null;
  csrfRequest = null;
}

// GET current identity: restore the session after reload and refresh UI permissions.
// A 403 can mean there is no active session; the backend remains the authority.
export function getCurrentUser(signal) {
  return apiGet("/api/auth/me/", {}, signal);
}

// POST password change: verify the current password and validate/hash the new one.
// Django preserves the requesting session; other sessions become invalid.
export function changePassword(currentPassword, newPassword) {
  return apiPost("/api/auth/password/change/", {
    current_password: currentPassword, new_password: newPassword,
  });
}

// POST recovery request: ask the server to email a reset link if eligible.
// The generic response does not reveal whether the email identifies an account.
export function requestPasswordReset(email) {
  return apiPost("/api/auth/password/reset/", { email });
}

// POST recovery confirmation: use uid/token from the frontend reset-link query.
// On success, navigate to sign-in; confirmation does not create a session.
export function confirmPasswordReset(uid, token, newPassword) {
  return apiPost("/api/auth/password/reset/confirm/", {
    uid, token, new_password: newPassword,
  });
}

// POST student account: HOD creates a nonstaff account and links it to this UUID.
// Payload is {username, email, password}; privilege fields cannot elevate it.
// This does not switch the HOD's session to the returned student account.
export function createStudentAccount(studentId, account) {
  return apiPost(`/api/students/${pathId(studentId)}/account/`, account);
}

// PUT student account: HOD links an existing eligible nonstaff account by integer ID.
// Neither account nor student may already have a conflicting student link.
export function linkStudentAccount(studentId, accountId) {
  return apiPut(`/api/students/${pathId(studentId)}/account/`, { account_id: accountId });
}
```

Login failures count against client address plus submitted username. After five
failures, subsequent attempts receive 429 until the fifteen-minute window from
the first failure expires; a successful login clears that counter. The default
cache is process-local, so shared production throttling needs configuration.

Recovery defaults are 20 requests/hour and 60 confirmations/hour per throttle
identity. `PASSWORD_RESET_FRONTEND_URL` must be configured; production requires
an HTTPS reset page. Links expire after one hour and cannot be reused after
success. SMTP delivery and the React recovery page still need integration.

New student accounts are active, nonstaff and nonsuperuser. Existing-account
linking requires an active nonstaff, nonsuperuser account with a usable password.
Neither operation replaces an existing student-account link. Staff account,
group and assignment administration currently belongs to HOD-only Django admin,
not a React administration endpoint.

## 6. Implemented student and guardian methods

### 6.1 Route catalog

| Client method | HTTP route | Access | Input | Success |
| --- | --- | --- | --- | --- |
| `listStudents` | `GET /api/students/` | Student reader | Search/filter query and `page` | 200 paginated students. |
| `createStudent` | `POST /api/students/` | Student creator | Student write fields | 201 student. |
| `getStudent` | `GET /api/students/{student_id}/` | Student reader | UUID in path | 200 student. |
| `updateStudent` | `PATCH /api/students/{student_id}/` | Student editor | Changed student fields | 200 student. |
| `getMyStudentProfile` | `GET /api/me/student/` | Signed in with linked profile | None | 200 own student. |
| `exportStudentProfiles` | `GET /api/students/export/` | Student exporter | Same search/filter query | 200 CSV download; all matching rows. |
| `bulkChangeStudentLevels` | `POST /api/students/bulk-level-change/` | HOD | `student_ids`, `expected_level`, `current_level` | 200 `{updated_count,current_level}`. |
| `bulkChangeStudentStatuses` | `POST /api/students/bulk-status-change/` | HOD | `student_ids`, `expected_status`, `academic_status` | 200 `{updated_count,academic_status}`. |
| `listGuardians` | `GET /api/students/{student_id}/guardians/` | Guardian reader | `page` | 200 paginated guardians. |
| `createGuardian` | `POST /api/students/{student_id}/guardians/` | Guardian writer: add | Guardian write fields | 201 guardian. |
| `getGuardian` | `GET /api/students/{student_id}/guardians/{guardian_id}/` | Guardian reader | UUIDs in path | 200 guardian. |
| `updateGuardian` | `PATCH /api/students/{student_id}/guardians/{guardian_id}/` | Guardian writer: change | Changed guardian fields | 200 guardian. |

The student-account operations in section 5 also use student paths.

### 6.2 Student fields and filters

| Field | Write behavior / response |
| --- | --- |
| `student_id` | Backend-generated UUID; read-only. |
| `identifier_type` | Required on create: `matriculation` or `utme`. |
| `identifier_value` | Required unique string, maximum 100 characters. |
| `full_name` | Required string, maximum 200 characters. |
| `phone_number` | Required nonblank string, maximum 30 characters. |
| `admission_year` | Required nonnegative small integer. |
| `mode_of_admission` | Required: `utme`, `direct_entry` or `transfer`. |
| `current_level` | Required nonnegative small integer in the profile serializer. HOD alone can change an existing level; bulk levels require 1–32767. Ordinary creation must match an assigned positive level. |
| `is_active` | Optional on create, defaults true. Profile flag; do not confuse it with the linked User's active flag. |
| `academic_status` | Optional on create, defaults `undergraduate`; choices are `undergraduate` and `graduated`. HOD alone can transition status and graduation requires current review. |

The Student model's `surname` and account link `user` are not exposed as student
serializer fields. Creating a student does not create a login account. A new
student cannot be created directly as graduated because no reviewed history
exists yet. There is no student self-edit route: `/api/me/student/` is GET-only.

Supported student-list/export query parameters:

| Query key | Meaning |
| --- | --- |
| `search` | DRF search across `full_name` and `identifier_value`. |
| `admission_year` | Exact admission-year filter. |
| `current_level` | Exact current-level filter. |
| `mode_of_admission` | One admission-mode value. |
| `identifier_type` | One identifier-type value. |
| `is_active` | Boolean filter, for example `true` or `false`. |
| `page` | Page number for the list; export ignores pagination. |

There is no implemented `academic_status`, `academic_session`, `semester` or
client-supplied ordering filter on this directory route. Unknown query keys do
not necessarily cause an error, so do not assume they filtered the results.

### 6.3 Guardian fields

Required create fields are `full_name` (maximum 200), `phone_number` (maximum 30)
and `relationship` (maximum 100). `email` and `address` are optional; email can
be blank or null. Responses also include read-only `guardian_id` and `student`.
The URL selects the parent student; PATCH cannot relink a guardian. A student can
have multiple guardians. There is no guardian login or student self-service
guardian-edit API.

### 6.4 Commented methods

```javascript
// GET directory: send supported filters/search as query parameters, never a body.
// The server restricts records to the caller's current adviser levels or HOD scope.
export function listStudents(filters = {}, signal) {
  return apiGet("/api/students/", filters, signal);
}

// POST student: create biodata using the required fields in section 6.2.
// The server generates student_id; account provisioning is a separate operation.
export function createStudent(student) {
  return apiPost("/api/students/", student);
}

// GET one student: use the stable UUID returned by the directory/create response.
// A hidden/out-of-scope record returns 404 even if the browser knows its UUID.
export function getStudent(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/`, {}, signal);
}

// PATCH biodata: submit only changed fields, e.g. {phone_number: "08000000000"}.
// Level/status edits need HOD; graduated academic-profile edits require reopening.
export function updateStudent(studentId, changes) {
  return apiPatch(`/api/students/${pathId(studentId)}/`, changes);
}

// GET own profile: Django derives the student from the signed-in account.
// Do not send a student_id or use this route for staff directory access.
export function getMyStudentProfile(signal) {
  return apiGet("/api/me/student/", {}, signal);
}

// GET export: fetch a CSV Blob using directory filters and independent export access.
// Every matching scoped record is exported; this is not an academic-result export.
export function exportStudentProfiles(filters = {}, signal) {
  return apiRequest("/api/students/export/", { query: filters, signal, responseType: "blob" });
}

// POST bulk level transition: submit 1–1000 distinct UUIDs and the displayed old level.
// expected_level rejects a stale selection. One invalid row aborts the whole change.
export function bulkChangeStudentLevels(studentIds, expectedLevel, currentLevel) {
  return apiPost("/api/students/bulk-level-change/", {
    student_ids: studentIds, expected_level: expectedLevel, current_level: currentLevel,
  });
}

// POST bulk status transition: include the expected old status for every selected row.
// Graduation requires a current HOD review for every student; changes are atomic.
export function bulkChangeStudentStatuses(studentIds, expectedStatus, academicStatus) {
  return apiPost("/api/students/bulk-status-change/", {
    student_ids: studentIds, expected_status: expectedStatus, academic_status: academicStatus,
  });
}

// GET guardians: list only guardians under a student visible to the staff caller.
// Guardian permissions are independent of permission to view ordinary biodata.
export function listGuardians(studentId, page = 1, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/guardians/`, { page }, signal);
}

// POST guardian: the path fixes the student; send name, phone, relationship and
// optional email/address. Do not submit student or guardian_id as write fields.
export function createGuardian(studentId, guardian) {
  return apiPost(`/api/students/${pathId(studentId)}/guardians/`, guardian);
}

// GET guardian detail: both parent scope and guardian-to-student relationship matter.
// A guardian belonging to a different student is unavailable through this path.
export function getGuardian(studentId, guardianId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/`, {}, signal);
}

// PATCH guardian contacts: submit only allowed changed fields; no relinking occurs.
// A contact change can invalidate a guardian result-sharing preview.
export function updateGuardian(studentId, guardianId, changes) {
  return apiPatch(`/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/`, changes);
}
```

Bulk lists require 1–1000 distinct UUIDs. Expected and destination values must
differ; all selected records must match the expected value. Graduated students
cannot undergo bulk level changes. Academic corrections need HOD reopening to
`undergraduate`, followed by a fresh review before regraduation.

Student export columns are fixed: `student_id`, `identifier_type`,
`identifier_value`, `full_name`, `phone_number`, `admission_year`,
`mode_of_admission`, `current_level`, `is_active`, `academic_status`. The backend
streams UTF-8 CSV with `Cache-Control: no-store` and filename
`student-profiles.csv`. Guardian contacts, accounts, scores and biometrics are
excluded. Potential spreadsheet-formula cells get a leading apostrophe;
import identifier and phone columns as text to preserve their formatting.

## 7. Implemented messaging methods

### 7.1 Route catalog

| Client method | HTTP route | Access | Input | Success |
| --- | --- | --- | --- | --- |
| `sendAdviserMessage` | `POST /api/adviser-messages/` | Adviser sender | Adviser message payload | 201 send summary. |
| `sendHodMessage` | `POST /api/hod-messages/` | HOD | HOD message payload | 201 send summary. |
| `listMyAdviserMessages` | `GET /api/me/messages/` | Signed in with linked profile | `page` | 200 paginated adviser messages addressed to own student. |
| `getMyAdviserMessage` | `GET /api/me/messages/{message_id}/` | Signed in with linked profile | Message ID | 200 own received adviser message. |
| `listMyHodMessages` | `GET /api/me/hod-messages/` | Signed in recipient | `page` | 200 paginated HOD messages addressed to this account/student. |

### 7.2 Payloads and responses

Both send payloads require nonblank `subject` (maximum 200 characters) and
`body`. Adviser sending also requires an integer `assignment_id` owned by the
caller for the current configured session:

```javascript
// A level announcement: omit recipient_id; Django selects the eligible students.
const adviserAnnouncement = {
  assignment_id: 3,
  audience: "level",
  subject: "Advising hours",
  body: "Please check the departmental advising schedule.",
};

// An individual message: recipient_id must be a student UUID in that assignment.
const adviserIndividual = {
  assignment_id: 3,
  audience: "individual",
  recipient_id: "11111111-1111-4111-8111-111111111111",
  subject: "Record review",
  body: "Please contact your assigned adviser about the record review.",
};

// HOD chooses exactly one audience-specific target, alongside subject and body.
const hodLevelMessage = {
  audience: "level", level: 200,
  subject: "Department notice", body: "Please review the department notice.",
};
// Other valid combinations are:
// {audience: "individual", recipient_id: STUDENT_UUID, subject, body}
// {audience: "adviser", adviser_id: STAFF_USER_INTEGER_ID, subject, body}
// Omit level/adviser_id/recipient_id when they do not match the chosen audience.
```

Adviser recipients must be active students at the assigned current level. HOD
individual/level targets must be active students; an adviser target must be an
active staff account with an active current-session adviser assignment. No
eligible recipients produces 400. Recipient membership is saved when the
message is created; it is not recomputed when the inbox is read.

Send summaries contain `message_id`, `audience`, `subject`, `recipient_count`
and `created_at`. Inbox records contain `id`, `audience`, `subject`, `body`,
`sender_name` and `created_at`. These are internal portal messages, not email or
WhatsApp submissions. Guardian result delivery is a separate service.

### 7.3 Commented methods

```javascript
// POST adviser message: submit assignment/audience/subject/body and, for an
// individual audience only, recipient_id. Django freezes eligible recipients.
export function sendAdviserMessage(message) {
  return apiPost("/api/adviser-messages/", message);
}

// POST HOD message: target an individual, level or assigned adviser using the
// exact audience field combination above. Course-cohort broadcasts do not exist.
export function sendHodMessage(message) {
  return apiPost("/api/hod-messages/", message);
}

// GET adviser inbox: the signed-in linked student sees only saved recipient rows.
// This is not a staff sent-message history or an inbox for arbitrary student IDs.
export function listMyAdviserMessages(page = 1, signal) {
  return apiGet("/api/me/messages/", { page }, signal);
}

// GET adviser message detail: the message must already belong to the caller's inbox.
// Knowing someone else's message ID cannot grant access to its body.
export function getMyAdviserMessage(messageId, signal) {
  return apiGet(`/api/me/messages/${pathId(messageId)}/`, {}, signal);
}

// GET HOD inbox: return messages where this account/student is a stored recipient.
// There is no separate HOD-message detail or mark-as-read API at present.
export function listMyHodMessages(page = 1, signal) {
  return apiGet("/api/me/hod-messages/", { page }, signal);
}
```

Assignment IDs and adviser account IDs currently come from HOD administration
or an agreed development fixture. `auth/me/` supplies adviser levels, not an
assignment selector. A React assignment-discovery API remains unfinished.

## 8. Implemented academic methods

### 8.1 Results, GPA and CGPA route catalog

| Client method | HTTP route | Access | Input | Success |
| --- | --- | --- | --- | --- |
| `listResults` | `GET /api/results/` | Academic reader | Result filters and `page` | 200 paginated scoped results. |
| `createResult` | `POST /api/results/` | Academic creator | `student_id`, `offering_id`, optional `attempt_number`, `score` | 201 result. |
| `getResult` | `GET /api/results/{result_id}/` | Academic reader | Integer ID | 200 result. |
| `updateResultScore` | `PATCH /api/results/{result_id}/` | Academic editor | `score` | 200 result. |
| `verifyResult` | `POST /api/results/{result_id}/verify/` | Academic verifier | `expected_score` | 200 verified result. |
| `getStudentGpa` | `GET /api/students/{student_id}/gpa/` | Academic reader | `academic_session` name, `semester` | 200 GPA summary. |
| `getStudentCgpa` | `GET /api/students/{student_id}/cgpa/` | Academic reader | None | 200 CGPA/completeness summary. |
| `getMyGpa` | `GET /api/me/gpa/` | Signed-in nonstaff linked student | Session name, semester | 200 own GPA summary. |
| `getMyCgpa` | `GET /api/me/cgpa/` | Signed-in nonstaff linked student | None | 200 own CGPA/completeness summary. |
| `listMyResults` | `GET /api/me/results/` | Signed-in nonstaff linked student | `page` | 200 paginated own verified results. |
| `getMyResult` | `GET /api/me/results/{result_id}/` | Signed-in nonstaff linked student | Integer ID | 200 own verified result. |

Staff result-list filters are `student_id`, `academic_session` (consecutive-year
name), `semester`, `is_verified` and `page`. No course/offering/level/search
filter is currently implemented on that endpoint. The own-results list has only
pagination; it does **not** apply the staff result filters.

### 8.2 Result fields and academic rules

| Field | Create / update / response behavior |
| --- | --- |
| `student_id` | Required UUID on create. Returned as read-only field `student`. |
| `offering_id` | Required integer on create. Returned as read-only field `offering`. |
| `attempt_number` | Optional on create, defaults 1; integer 1–32767. Included in response. |
| `score` | Optional on create, defaults null. The only PATCH field, where it is required; accepts null or a decimal 0–100. |
| `id` | Read-only integer result ID. |
| `credit_units` | Copied from the offering on create; read-only saved units. |
| `grading_scale` | Copied from the offering's published scale on create; read-only saved scale ID. |
| `is_verified` | False for a new result; controlled by score/verification services, not general PATCH. |

The combination of student, offering and attempt number is unique. Student,
offering, attempt number, units and grading version cannot be changed through
result PATCH. There is no result DELETE method.

A changed score clears verification; submitting the identical score preserves
the existing verification flag. Verification requires a non-null
`expected_score` equal to the current saved score. A changed score is rejected
as a stale review with 400; this backend does not use an ETag/409 contract here.
Verification permission is independent of editing permission.

GPA and CGPA use backend Decimal calculations and saved units/grading versions.
Every recorded attempt, including repeats and failures, participates. Any
unverified or missing-score row in the relevant history causes 400; the service
does not silently drop it. An empty history returns `null`, not a failed grade.
The own-results list hides unverified rows, but the own GPA/CGPA calculators
still require all relevant recorded rows to be verified.

GPA response fields are `student_id`, `academic_session` (name), `semester` and
`gpa`. CGPA response fields are `student_id`, `cgpa` and
`history_completeness`: `not_confirmed`, `hod_reviewed` or `review_required`.
These completeness values describe the manual HOD review; they do not assert
that automatic curriculum validation exists. Regular CGPA covers all saved
history; guardian report CGPA is limited through its selected period.

### 8.3 Commented result and summary methods

```javascript
// GET staff results: filter by permitted student/session/semester/verification.
// The backend scopes all rows; this method does not accept a staff role override.
export function listResults(filters = {}, signal) {
  return apiGet("/api/results/", filters, signal);
}

// POST result: use {student_id, offering_id, attempt_number?, score?}.
// The backend saves the offering's units/scale and creates an unverified row.
export function createResult(result) {
  return apiPost("/api/results/", result);
}

// GET result detail: retrieve one scoped result, including its verification flag.
// Responses use student/offering, whereas creation uses student_id/offering_id.
export function getResult(resultId, signal) {
  return apiGet(`/api/results/${pathId(resultId)}/`, {}, signal);
}

// PATCH score: a changed value invalidates verification; null records a missing score.
// Other result fields cannot be rewritten through this operation.
export function updateResultScore(resultId, score) {
  return apiPatch(`/api/results/${pathId(resultId)}/`, { score });
}

// POST verification: submit the exact score displayed and reviewed by the verifier.
// The server compares expected_score under a lock to reject stale approvals.
export function verifyResult(resultId, expectedScore) {
  return apiPost(`/api/results/${pathId(resultId)}/verify/`, { expected_score: expectedScore });
}

// GET student GPA: query by session NAME and semester, not catalog numeric ID.
// The backend calculates from verified saved attempts in that period.
export function getStudentGpa(studentId, academicSession, semester, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/gpa/`, {
    academic_session: academicSession, semester,
  }, signal);
}

// GET student CGPA: include all saved history and return manual-review completeness.
// React should display the server value instead of recreating academic rules.
export function getStudentCgpa(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/cgpa/`, {}, signal);
}

// GET own GPA: the server derives student identity from the linked nonstaff account.
// Accept only the selected session/semester, never an arbitrary student UUID.
export function getMyGpa(academicSession, semester, signal) {
  return apiGet("/api/me/gpa/", { academic_session: academicSession, semester }, signal);
}

// GET own CGPA: use the same backend calculation and completeness fields as staff.
// A missing/unverified history is handled by the API, not guessed in React.
export function getMyCgpa(signal) {
  return apiGet("/api/me/cgpa/", {}, signal);
}

// GET own results: return verified rows for this student, paginated at 20.
// Staff-list session/semester filters are not implemented on this own route.
export function listMyResults(page = 1, signal) {
  return apiGet("/api/me/results/", { page }, signal);
}

// GET own result detail: inaccessible or unverified rows return 404.
// The caller cannot use this endpoint to browse another student's result.
export function getMyResult(resultId, signal) {
  return apiGet(`/api/me/results/${pathId(resultId)}/`, {}, signal);
}
```

### 8.4 Academic catalog and grading route catalog

All methods in this table are **HOD-only**, including the reads.

| Client method | HTTP route | Input | Success |
| --- | --- | --- | --- |
| `listAcademicSessions` | `GET /api/academic-sessions/` | `page` | 200 paginated sessions. |
| `createAcademicSession` | `POST /api/academic-sessions/` | `name` | 201 session. |
| `listCourses` | `GET /api/courses/` | `page` | 200 paginated courses. |
| `createCourse` | `POST /api/courses/` | `code`, `title` | 201 course. |
| `listCourseOfferings` | `GET /api/course-offerings/` | `page` | 200 paginated offerings. |
| `createCourseOffering` | `POST /api/course-offerings/` | Offering fields below | 201 offering. |
| `listGradingScales` | `GET /api/grading-scales/` | `page` | 200 paginated scales. |
| `createGradingScale` | `POST /api/grading-scales/` | `name`, `bands` | 201 unpublished scale. |
| `getGradingScale` | `GET /api/grading-scales/{scale_id}/` | Integer ID | 200 scale. |
| `updateGradingScale` | `PATCH /api/grading-scales/{scale_id}/` | Changed `name` and/or full `bands` | 200 updated draft scale. |
| `publishGradingScale` | `POST /api/grading-scales/{scale_id}/publish/` | Empty object | 200 published scale. |
| `assignOfferingGradingScale` | `PATCH /api/course-offerings/{offering_id}/grading-scale/` | `grading_scale` | 200 offering. |

Catalog shapes and validation:

| Resource | Fields |
| --- | --- |
| Academic session | Read-only `id`; required unique `name` in consecutive `YYYY/YYYY` form, for example `2026/2027`. |
| Course | Read-only `id`; required unique `code` (maximum 30) and `title` (maximum 200). |
| Course offering | Read-only `id`; required integer `course`, integer `academic_session`, `semester`, positive `level`, positive `credit_units`; optional published `grading_scale` ID. |
| Grading scale | Read-only `id`, `is_published`; write fields `name` (unique, maximum 100) and nonempty `bands`. |

An offering is unique by course/session/semester. If its scale is omitted,
creation uses the migrated "Initial five-point scale"; the database must be
prepared for that default to exist. Published scale IDs should be taken from
the catalog, not assumed from a sample.

Each grading band has exactly `minimum`, `maximum` and `grade_point`. Score
boundaries allow up to two decimal places. Bands must cover 0–100 without gaps
or overlaps; grade points are integers 0–5. A band includes its lower boundary
and excludes its upper boundary, except that 100 belongs to the final band.
PATCH of `bands` replaces the complete band list; it does not patch one array
element. Published scales are immutable. An offering with results cannot change
its scale, preserving the historical basis of saved results.

```javascript
// Illustrative complete five-point bands, matching the backend's initial scale.
// Institutionally approved scale changes belong in a new reviewed version.
const exampleScale = {
  name: "Synthetic five-point version",
  bands: [
    { minimum: "0", maximum: "40", grade_point: "0" },
    { minimum: "40", maximum: "45", grade_point: "1" },
    { minimum: "45", maximum: "50", grade_point: "2" },
    { minimum: "50", maximum: "60", grade_point: "3" },
    { minimum: "60", maximum: "70", grade_point: "4" },
    { minimum: "70", maximum: "100", grade_point: "5" },
  ],
};

// GET sessions: HOD retrieves names and integer IDs for catalog-based selectors.
// Students/advisers cannot currently use this endpoint as a public selector feed.
export function listAcademicSessions(page = 1, signal) {
  return apiGet("/api/academic-sessions/", { page }, signal);
}

// POST session: save a unique consecutive-year display name, e.g. 2026/2027.
// This does not change the server's CURRENT_ACADEMIC_SESSION environment setting.
export function createAcademicSession(name) {
  return apiPost("/api/academic-sessions/", { name });
}

// GET courses: HOD retrieves course IDs/codes/titles in code order.
// There is no server-side course search parameter on this route at present.
export function listCourses(page = 1, signal) {
  return apiGet("/api/courses/", { page }, signal);
}

// POST course: create the code/title catalog entry; units belong to an offering.
// This alone does not register a student or assign a lecturer to the course.
export function createCourse(code, title) {
  return apiPost("/api/courses/", { code, title });
}

// GET offerings: HOD retrieves the period/semester/level/units/scale definitions.
// The current endpoint supports page, not course/session/level query filtering.
export function listCourseOfferings(page = 1, signal) {
  return apiGet("/api/course-offerings/", { page }, signal);
}

// POST offering: send {course, academic_session, semester, level, credit_units,
// grading_scale?}, using numeric IDs. This creates no registration or result.
export function createCourseOffering(offering) {
  return apiPost("/api/course-offerings/", offering);
}

// GET grading versions: include draft and published scales for HOD management.
// Do not equate a list entry with a published scale suitable for new results.
export function listGradingScales(page = 1, signal) {
  return apiGet("/api/grading-scales/", { page }, signal);
}

// POST grading version: validate and save a draft with a complete bands list.
// Publication is a separate deliberate action after reviewing every boundary.
export function createGradingScale(scale) {
  return apiPost("/api/grading-scales/", scale);
}

// GET grading detail: fetch the precise boundaries and publication state.
// The version ID is what offerings/results reference, rather than its name.
export function getGradingScale(scaleId, signal) {
  return apiGet(`/api/grading-scales/${pathId(scaleId)}/`, {}, signal);
}

// PATCH a draft version: change name and/or replace all bands.
// Published scales reject edits; use a new scale version for future changes.
export function updateGradingScale(scaleId, changes) {
  return apiPatch(`/api/grading-scales/${pathId(scaleId)}/`, changes);
}

// POST publication: lock the reviewed grading version for use by offerings.
// No is_published flag is accepted through the general create/edit payload.
export function publishGradingScale(scaleId) {
  return apiPost(`/api/grading-scales/${pathId(scaleId)}/publish/`);
}

// PATCH offering scale: choose a published version before this offering has results.
// Existing result histories cannot be reinterpreted by changing the offering.
export function assignOfferingGradingScale(offeringId, scaleId) {
  return apiPatch(`/api/course-offerings/${pathId(offeringId)}/grading-scale/`, {
    grading_scale: scaleId,
  });
}
```

### 8.5 Course requirements and graduation route catalog

All methods in this table are **HOD-only**.

| Client method | HTTP route | Input | Success |
| --- | --- | --- | --- |
| `listCourseRequirements` | `GET /api/students/{student_id}/course-requirements/` | `page` | 200 paginated requirements. |
| `createCourseRequirement` | `POST /api/students/{student_id}/course-requirements/` | `offering`, optional `resolution`, `reason` | 201 requirement. |
| `getCourseRequirement` | `GET /api/students/{student_id}/course-requirements/{requirement_id}/` | IDs in path | 200 requirement. |
| `updateCourseRequirement` | `PATCH /api/students/{student_id}/course-requirements/{requirement_id}/` | Changed requirement fields | 200 requirement. |
| `getGraduationReview` | `GET /api/students/{student_id}/graduation-review/` | UUID | 200 current eligible history/digest and prior review, or 400 for ineligible/incomplete history. |
| `approveGraduationReview` | `POST /api/students/{student_id}/graduation-review/` | Approval fields below | 200 saved review; status does not change yet. |

Requirement responses contain `id`, `student`, `offering`, `resolution`,
`reason`, `recorded_by`; `id`, `student`, `recorded_by` are read-only. An offering
may appear only once per student. `resolution` is `result` (default), `exemption`
or `transfer`. Exemption/transfer require a nonblank reason and do not create
invented grades or CGPA units. During graduation review, a `result` requirement
must have a recorded result for that offering.

GET graduation review returns `student_id`, `cgpa`, `history_digest`,
`review_current` and `review`. The review is null or contains `student`,
`reviewed_by`, `reviewed_at`, `notes`, `cgpa_snapshot`. Approval POST requires
`expected_digest` (the exact 64-character lowercase hexadecimal digest returned
by GET), nonblank `notes`, `history_complete=true` and
`other_requirements_satisfied=true`. It returns the review object.

```javascript
// GET required offerings: inspect the HOD-maintained manifest for this student.
// This is a reviewed list, not an automatic derivation from curriculum rules.
export function listCourseRequirements(studentId, page = 1, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/course-requirements/`, { page }, signal);
}

// POST requirement: send {offering, resolution?, reason?}; the URL supplies student.
// Transfers/exemptions need an explanation and do not create academic marks.
export function createCourseRequirement(studentId, requirement) {
  return apiPost(`/api/students/${pathId(studentId)}/course-requirements/`, requirement);
}

// GET one requirement: inspect the recorded offering and its reviewed resolution.
// The requirement must belong to the student in the parent path.
export function getCourseRequirement(studentId, requirementId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/course-requirements/${pathId(requirementId)}/`, {}, signal);
}

// PATCH requirement: change offering/resolution/reason before graduation.
// Any history change can invalidate the student's earlier graduation review.
export function updateCourseRequirement(studentId, requirementId, changes) {
  return apiPatch(`/api/students/${pathId(studentId)}/course-requirements/${pathId(requirementId)}/`, changes);
}

// GET graduation preview: validate recorded requirements and verified history.
// Capture history_digest for the exact history that the HOD is about to approve.
export function getGraduationReview(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/graduation-review/`, {}, signal);
}

// POST HOD approval: send the reviewed digest, notes and both true attestations.
// This certifies the current history; a separate student status change graduates it.
export function approveGraduationReview(studentId, approval) {
  return apiPost(`/api/students/${pathId(studentId)}/graduation-review/`, approval);
}
```

The complete flow is: record the required offerings and justified resolutions,
ensure every saved attempt has a score and is verified, GET the preview, review
the complete history and other official requirements, POST approval, then PATCH
`academic_status` to `graduated` or use the bulk status method.

Review requires a nonempty required-offering manifest, at least one recorded
result and unrounded CGPA >= 1.00. It cannot discover courses omitted from the
HOD's manifest or automatically determine all institutional graduation rules.
Results, requirements, level, admission year or admission mode changes make an
existing review stale. Contact-only edits do not. Save academic-profile edits
before approving; do not combine them with graduation in one PATCH.

Graduated histories are protected against result and requirement edits until
the HOD reopens status to `undergraduate`. A graduation review stores the latest
approval; it is not an immutable audit history.

### 8.6 Current academic session and attendance

These are mounted APIs, independent of the unfinished identity-check proposal.
All browser writes require session authentication and CSRF. Attendance responses
use no-store caching. See [attendance API](docs/attendance-api.md) and
[pending capture batches](docs/attendance-pending-batches.md) for full details.

#### Current academic session

| Client method | HTTP route | Access / payload | Response |
| --- | --- | --- | --- |
| `getCurrentAcademicSession` | `GET /api/academic-sessions/current/` | HOD | 200 `{academic_session, name, source}`; ID can be null before selection; source is `database` or `environment`. |
| `selectCurrentAcademicSession` | `PUT /api/academic-sessions/current/` | HOD; `academic_session` catalog integer ID, `expected_session_id` previously returned ID or null | 200 updated selection; stale selection returns 400. |

The database selection overrides the environment fallback for adviser scope,
messaging and academic permissions. Selection history records the actor. It does
not promote students, copy assignments, change results or open attendance classes.

#### Attendance route catalog

`{session_id}` is an attendance-class UUID, distinct from the academic-session
integer ID. `{record_id}` is an integer. Ordinary staff require an active explicit
assignment to the offering in the current academic session and
`attendance.view_attendance`. Actions additionally require the permission shown;
an adviser-level assignment alone does not grant course access. HOD has department
visibility, including historical classes; new classes must use current offerings.

| Client method | HTTP route | Access / request | Response |
| --- | --- | --- | --- |
| `getAttendanceRoster` | `GET /api/attendance/offerings/{offering_id}/roster/` | HOD; `page` | 200 paginated candidates plus `confirmed_revision`, `confirmed_student_ids`. |
| `confirmAttendanceRoster` | `PUT /api/attendance/offerings/{offering_id}/roster/` | HOD; `student_ids` (1–1000 unique UUIDs), `expected_revision` (0 initially) | 200 `{revision, student_ids}`. |
| `setAttendanceStaff` | `PUT /api/attendance/offerings/{offering_id}/staff/` | HOD; `staff` account integer ID, `is_active` boolean | 200 `{id, staff, is_active}`; this is not a staff-directory/list API. |
| `listAttendanceSessions` | `GET /api/attendance/sessions/` | HOD or scoped attendance reader; `page` | 200 paginated visible classes. |
| `openAttendanceSession` | `POST /api/attendance/sessions/` | HOD or scoped staff + `attendance.manage_attendance`; `offering`, `title`, `starts_at`, `ends_at` | 201 class. |
| `getAttendanceSession` | `GET /api/attendance/sessions/{session_id}/` | HOD or scoped attendance reader | 200 class plus frozen `student_ids`. |
| `closeAttendanceSession` | `POST /api/attendance/sessions/{session_id}/close/` | HOD or scoped staff + `attendance.manage_attendance`; empty object | 200 closed class; idempotent. |
| `listAttendanceRecords` | `GET /api/attendance/sessions/{session_id}/records/` | HOD or scoped attendance reader; `page` | 200 paginated records. |
| `recordManualAttendance` | `POST /api/attendance/sessions/{session_id}/records/` | HOD or scoped staff + `attendance.record_attendance`; `student` UUID, `event_id` UUID, `reason` | 201 new event, 200 duplicate/retry; `{event_id, duplicate, replayed}`. |
| `correctAttendanceRecord` | `POST /api/attendance/records/{record_id}/correct/` | HOD or scoped staff + `attendance.correct_attendance`; `status` (`present` or `absent`), `reason` | 200 `{id, status}`; correction history retained. |
| `getMyAttendance` | `GET /api/me/attendance/` | Signed in with linked student; `page` | 200 own paginated records only. |

Roster suggestions include active undergraduates at the offering level and those
whose latest eligible verified/scored earlier attempt failed under its saved
grading version. HOD confirms actual registration, including additions/removals;
suggestions are not automatic enrollment. Each opened class freezes the approved
roster revision. Later roster/level changes do not rewrite that snapshot.

Class responses contain `id`, `offering`, `title`, `starts_at`, `ends_at`, `status`,
`roster_revision`, `closed_at`. Supply timezone-aware ISO-8601 start/end timestamps,
with end after start. A current offering and confirmed roster are required. New
manual events require an open class within its inclusive time window and an
eligible active undergraduate. Reasons are nonblank and at most 1000 characters.
One record exists per class/student: a new duplicate event does not overwrite it.
Exact authorized retries retain the same event UUID and payload, including after
closure; changed payloads or revoked access cannot use retry to bypass checks.

Staff record rows contain `id`, `student_id`, `status`, `recorded_at`,
`recorded_by_id`, `reason`; own-student rows contain `id`, `session_id`,
`session__offering_id`, `status`, `recorded_at`. Missing rows are not automatically
absences. Cancel/reopen, excused-class rules, percentages and warnings remain
unfinished. The agreed future threshold is 75%, excluding formally excused classes
from the denominator; the current API does not calculate it.

#### Pending USB capture uploads

| Client method | HTTP route | Response |
| --- | --- | --- |
| `previewPendingCaptures` | `POST /api/attendance/sessions/{session_id}/pending-batches/preview/` | 200 validated metadata and whole-file `file_sha256`; no persistence. |
| `importPendingCaptures` | `POST /api/attendance/sessions/{session_id}/pending-batches/` | 201 new receipt or 200 exact-file retry. |
| `listPendingCaptureBatches` | `GET /api/attendance/sessions/{session_id}/pending-batches/` | 200 paginated metadata, counts and review flags. |

All three require active staff with `attendance.import_pending_captures` and course
visibility; HOD satisfies the permission through active superuser access. Ordinary
staff need the separate view permission and current course assignment. Closed or
expired classes can accept evidence for later review.

POST the original JSONL file bytes with `Content-Type: application/x-ndjson` and
the usual CSRF header/cookie. Import additionally requires `X-Capture-SHA256` equal
to preview's whole-file `file_sha256`, not the JSONL trailer's prefix digest.
JSON wrappers and multipart FormData are unsupported; ordinary JSON client helpers
must not be used for these two writes. Limits: 2 MiB/file, 512 events,
4096 bytes/line, 2048 decoded bytes/probe. See the linked format contract rather
than inventing student IDs, matric numbers or scanner slots in capture records.

Import revalidates access and bytes atomically. Exact retries preserve the original
receipt; snapshots can append to the same immutable prefix, and older prefixes
remain safely retryable. Changed evidence or reused event identities return 409;
invalid files return 400 and unsupported content types 415. Rejections write no
partial evidence. Receipt fields include `receipt_id`, `file_sha256`, `received_at`,
`event_count`, `new_events`, `existing_events`, `batch_event_count`, `replayed`.

Every imported batch remains `pending_review`, with identity/timing review required
and `device_authenticated=false`. Imports never mark attendance or create warnings.
No response exposes probe bytes, and no raw-probe read/export API exists. Receipt
time is not capture time; boot IDs/uptime do not establish trusted wall-clock time.
A receipt never authorizes deletion of the device file. Restricted student bindings,
matching/reconciliation, trusted clocks, authenticated devices, retention/encryption
and field operation remain unfinished.

```javascript
// These examples use the shared JSON helpers above; raw uploads need a separate helper.
export const getCurrentAcademicSession = (signal) =>
  apiGet("/api/academic-sessions/current/", {}, signal);
export const selectCurrentAcademicSession = (academicSession, expectedSessionId) =>
  apiPut("/api/academic-sessions/current/", {
    academic_session: academicSession, expected_session_id: expectedSessionId,
  });
export const getAttendanceSession = (sessionId, signal) =>
  apiGet(`/api/attendance/sessions/${pathId(sessionId)}/`, {}, signal);
export const recordManualAttendance = (sessionId, event) =>
  apiPost(`/api/attendance/sessions/${pathId(sessionId)}/records/`, event);
// Preserve event_id and the entire payload on an exact retry. Never call this
// manual endpoint to claim that an unidentified fingerprint has been matched.
```

## 9. Implemented guardian result-sharing methods

### 9.1 Route catalog

All methods below are **HOD-only**. Guardian profile permissions do not grant
control of result sharing. Writes use the same session/CSRF contract as other
backend operations.

| Client method | HTTP route | Input | Success |
| --- | --- | --- | --- |
| `getGuardianSharingPreferences` | `GET /api/students/{student_id}/guardians/{guardian_id}/result-sharing/` | UUIDs | 200 channel preferences/evidence. |
| `setGuardianSharingPreferences` | `PUT /api/students/{student_id}/guardians/{guardian_id}/result-sharing/` | `email_enabled`, `whatsapp_enabled`, `evidence` | 200 saved preferences. |
| `previewGuardianResults` | `POST /api/result-shares/preview/` | Preview payload below | 201 persisted batch, including when reusing an identical request ID. |
| `listResultShares` | `GET /api/result-shares/` | `page` | 200 paginated batch summaries. |
| `getResultShare` | `GET /api/result-shares/{batch_id}/` | Batch UUID | 200 private batch preview/status. |
| `queueResultShare` | `POST /api/result-shares/{batch_id}/send/` | `expected_digest` | 202 batch; eligible deliveries queued. |
| `retryFailedResultShares` | `POST /api/result-shares/{batch_id}/retry/` | Empty object | 202 `{requeued}`. |

### 9.2 Payloads and responses

Preference responses contain `email_enabled`, `whatsapp_enabled`, `evidence`
and `updated_at`. Without a saved preference, both channel flags are false,
evidence is empty and update time is null. PUT requires both boolean flags and
a meaningful nonblank evidence string of at most 2000 characters. Record the
actual basis for enabling sharing or withdrawing it.

Preview payload:

```javascript
// Generate this UUID once for this exact selection and retain it while retrying.
// A deliberate fresh preview after changed data/selection needs a new request_id.
const examplePreview = {
  request_id: crypto.randomUUID(),
  student_ids: ["11111111-1111-4111-8111-111111111111"],
  academic_session: 1, // Numeric session catalog ID, not "2026/2027".
  semester: "harmattan",
  channels: ["email", "whatsapp"],
};
```

There must be 1–100 distinct student UUIDs and 1–2 distinct channels chosen from
`email` and `whatsapp`. The batch ID equals the submitted `request_id`. Reusing
the same ID and same request returns the saved batch. Reusing it for a different
selection, period, channels or creator is rejected.

Preview/detail/queue batch responses contain:

| Field | Meaning |
| --- | --- |
| `id` | Batch UUID. |
| `history_digest` | Digest of the reviewed preview; copy into queue `expected_digest`. |
| `queued_at` | Null before queueing, timestamp afterward. |
| `preview` | Per-student entries: `student_id`, `name`, `identifier`, `report`, `diagnostic_code`, `recipients`. |
| `counts` | A mapping of delivery status to number of delivery rows/parts. Missing statuses can be displayed as zero. |
| `deliveries` | Rows with `id`, `student_id`, `guardian_id`, `channel`, `part_number`, `destination`, `status`, `diagnostic_code`, `attempts`, `provider_id`. |

A report is null when blocked, otherwise it contains `gpa`, `cgpa`, `records`
and `text`. Its records cover cumulative history through the selected period;
the displayed report text contains the selected semester's attempts and its
GPA/CGPA. Record fields are `id`, `course`, `title`, `session`, `semester`,
`attempt`, `score`, `units`, `scale`, `grade_point`. Recipient entries contain
`parts`, `guardian_id`, `guardian_name`, `channel`, `destination`,
`preference_updated_at`, `diagnostic_code`.

The batch-list summary is smaller: `id`, numeric `academic_session`, `semester`,
`created_at`, `queued_at`, `counts`. Use detail for reports and individual
delivery outcomes; do not assume list summaries contain the full preview.

### 9.3 Commented methods

```javascript
// GET guardian preferences: inspect explicit permission for each sharing channel.
// A saved phone/email alone does not enable reports; absent preferences default off.
export function getGuardianSharingPreferences(studentId, guardianId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/result-sharing/`, {}, signal);
}

// PUT guardian preferences: send both flags and the actual permission/withdrawal basis.
// Preference changes invalidate old previews and can cancel pending submissions.
export function setGuardianSharingPreferences(studentId, guardianId, preferences) {
  return apiPut(`/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/result-sharing/`, preferences);
}

// POST preview: save reports, selected recipients and diagnostics without sending.
// Payload is {request_id, student_ids, academic_session, semester, channels}.
// The caller must retain request_id across retries of this exact instruction.
export function previewGuardianResults(previewRequest) {
  return apiPost("/api/result-shares/preview/", previewRequest);
}

// GET sharing history: return paginated summaries with per-status delivery counts.
// Counts include multipart WhatsApp rows; they are not distinct-student counts.
export function listResultShares(page = 1, signal) {
  return apiGet("/api/result-shares/", { page }, signal);
}

// GET batch detail: inspect the saved preview and current delivery status rows.
// This read can be polled by the HOD screen while a deployment worker processes it.
export function getResultShare(batchId, signal) {
  return apiGet(`/api/result-shares/${pathId(batchId)}/`, {}, signal);
}

// POST send: queue eligible deliveries only after the HOD reviews the preview.
// Copy history_digest into expected_digest; changed data rejects a stale send.
// Repeating Send on an already queued batch does not create another delivery set.
export function queueResultShare(batchId, expectedDigest) {
  return apiPost(`/api/result-shares/${pathId(batchId)}/send/`, {
    expected_digest: expectedDigest,
  });
}

// POST retry: requeue only known failed deliveries with fewer than three attempts.
// Unknown/accepted/processing/cancelled/skipped rows are never retried by this route.
export function retryFailedResultShares(batchId) {
  return apiPost(`/api/result-shares/${pathId(batchId)}/retry/`);
}
```

### 9.4 Review, queue and delivery behavior

1. Inspect guardian contacts and record channel preferences.
2. Save a preview, keeping its request UUID. Display student reports, destinations,
   multipart counts and skipped diagnostics for HOD review.
3. On the explicit Send action, queue that batch using its reviewed digest.
4. Read batch status while the separate backend worker processes queued rows.
5. Offer the retry action only for known failures; uncertain outcomes need
   operator reconciliation before any new send.

Reports require selected-period results and fully scored/verified history through
that period. Missing/unverified results block the affected student's report;
other eligible students in the batch can proceed. Diagnostics include
`results_missing_or_unverified`, `no_guardians`, `sharing_not_enabled`,
`invalid_email`, `international_phone_required` and `duplicate_contact`.

WhatsApp contacts require `+` followed by 8–15 digits, starting nonzero. No
automatic local-number conversion exists. Duplicate contacts within the same
student/channel are skipped. Reports are sent per student/recipient, with no
shared email recipient list. The report is a summary of verified recorded
results, not an official transcript or proof of complete curriculum history.

Status values are `draft`, `queued`, `processing`, `accepted`, `failed`,
`unknown`, `skipped` and `cancelled`. **Accepted means that the provider accepted
the submission; it does not prove delivery or reading.** Webhooks for delivered,
read or bounced outcomes are unfinished. Do not automatically reset a stuck
processing row or retry an unknown row, because an external submission may
already have succeeded.

Queueing validates the required provider configuration before changing the
batch; configuration/business failures return 400 rather than partially
queueing. `RESULT_SHARING_ENABLED` defaults false. SMTP/Meta setup and a regularly
scheduled `process_result_shares` worker are required for actual submissions.
The worker rechecks result/contact/preference snapshots before submission.
Transport adapters and the durable queue exist. The user confirmed a live Gmail
mock receipt; the page/worker integration used in-memory email and synthetic data.
Production worker activation, sharing-worker PostgreSQL concurrency and Meta
acceptance remain unfinished.

All sharing endpoints use no-store caching. Keep private reports and destinations
out of browser localStorage, analytics and application logs. Queue status may be
read with ordinary GET polling; no WebSocket or SSE connection is implemented.

### 9.5 Implemented React page and email worker

The separate [guardian-results page](frontend/guardian-results/README.md) implements
HOD departmental login, student/period selection, guardian email permission,
preview and explicit review/send, status polling, history and known-failure retry.
Its [API adapter](frontend/guardian-results/src/api.js) is ready for integration
into the finished React frontend. The disposable demo links to it. New batches
from this page use email only; historical mixed-channel batches are view-only.
Gmail credentials remain on the server, separate from departmental login.

Run the email worker from the configured administrator environment:

```powershell
.\.venv\Scripts\python.exe manage.py process_result_shares --channel email --watch --interval 5 --limit 25
```

Without --watch it exits after the bounded limit; in watch mode the limit applies
per pass. --channel email leaves WhatsApp jobs queued; omitting --channel processes
both. Stop requests finish the current submission. No automatic retry is made for
unknown outcomes. Deployment templates are in deploy/; no production service has
been installed or activated. API and worker must use the same database/config.

For Gmail setup/connection checks and the synthetic receipt command, see
[guardian-email-setup.md](docs/guardian-email-setup.md). Use a Google App Password
with the configured SMTP authentication method; never put credentials in React or
this reference. [Validation record](docs/guardian-result-sharing-validation.md):
13 frontend tests/build passed; full backend run succeeded with 360 tests and
15 PostgreSQL-only skips, with no migration drift. This is not production approval.

## 10. Calling methods from React screens

### 10.1 Read data with cancellation and distinct screen states

Assume the section 4–9 methods have been assembled into the suggested
`frontend/src/api.js`, and this example is saved beside it as
`frontend/src/StudentDirectory.jsx`. Load this screen only for an appropriate
signed-in staff account; backend checks still apply.

Effects can run again when dependencies change and are checked with an extra
setup/cleanup cycle in React development mode. Clean up reads and ignore stale
responses. Perform user-triggered writes in event handlers. See the [React useEffect reference](https://react.dev/reference/react/useEffect).

```jsx
import { useEffect, useState } from "react";
import { listStudents } from "./api.js";

export function StudentDirectory() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [state, setState] = useState({ loading: true, data: null, error: null });

  useEffect(() => {
    // Each search/page selection owns its read and its cleanup.
    const controller = new AbortController();
    let ignore = false;
    setState({ loading: true, data: null, error: null });

    listStudents({ search, page }, controller.signal)
      .then((data) => {
        // An older search result must not overwrite the newest selection.
        if (!ignore) setState({ loading: false, data, error: null });
      })
      .catch((error) => {
        // Cancellation is expected during cleanup, not a visible failure.
        if (!ignore && error.name !== "AbortError") {
          setState({ loading: false, data: null, error });
        }
      });

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [search, page]);

  return (
    <section>
      <h1>Students</h1>
      <label>
        Search name or identifier
        <input value={search} onChange={(event) => {
          setSearch(event.target.value);
          setPage(1); // A new filter begins at its first page.
        }} />
      </label>
      {state.loading && <p role="status">Loading students…</p>}
      {state.error && <p role="alert">{state.error.message}</p>}
      {state.data && (
        <>
          {state.data.results.length === 0 && <p>No matching students.</p>}
          <ul>{state.data.results.map((student) => (
            <li key={student.student_id}>
              {student.full_name} — {student.identifier_value}
            </li>
          ))}</ul>
          <button disabled={!state.data.previous} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <button disabled={!state.data.next} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </>
      )}
    </section>
  );
}
```

### 10.2 Submit an instruction from a form

```jsx
import { useState } from "react";
import { updateStudent } from "./api.js";

// Parent supplies a visible student and renders the form for a permitted editor.
// onSaved replaces the parent's record with the backend's authoritative response.
// Mount with key={student.student_id} when switching between student records.
export function StudentPhoneForm({ student, onSaved }) {
  const [phone, setPhone] = useState(student.phone_number);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault(); // Keep navigation under React's control.
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      // This is one PATCH instruction. Do not send the whole displayed object.
      const saved = await updateStudent(student.student_id, { phone_number: phone });
      onSaved(saved);
    } catch (failure) {
      // Preserve the entered value; validation failures must not clear the form.
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Student phone
        <input required maxLength={30} value={phone}
          onChange={(event) => setPhone(event.target.value)} />
      </label>
      {error && <p role="alert">
        {error.details?.phone_number?.[0] || error.message}
      </p>}
      <button disabled={busy} type="submit">{busy ? "Saving…" : "Save phone"}</button>
    </form>
  );
}
```

Apply the same pattern to score entry, guardian editing and other writes:
validate basic inputs for usability, send documented fields, disable duplicate
submission while awaiting the response, show backend validation, then refresh
affected reads. Client validation does not replace server validation.

After an ambiguous network failure, inspect the current record before repeating
a non-idempotent creation or message-send operation. Aborting fetch does not
undo a request that the server already received.

### 10.3 Authentication and score-review sequences

```javascript
// Login-form handler: complete the login/token refresh before enabling protected UI.
// Never retain the password in localStorage or include it in diagnostic logging.
const identity = await login(enteredUsername, enteredPassword);
// The auth provider can now keep identity in memory and select the allowed screen.

// A score edit returns its saved value and may clear verification.
const editedResult = await updateResultScore(selectedResultId, "68.50");
// Display editedResult and let a permitted verifier review it before the next call.
// Only after that review action, pass the exact displayed saved score:
const verifiedResult = await verifyResult(editedResult.id, editedResult.score);
// Refresh relevant result lists and GPA/CGPA summaries after the successful action.
```

The two score operations belong to separate user actions when review is
required. Having edit permission does not imply verification permission.

### 10.4 Download the existing profile CSV

```javascript
// Call from the Export button for a caller with students.export_student.
// This helper is a browser download action, not another backend route.
export async function downloadStudentProfiles(filters = {}) {
  const blob = await exportStudentProfiles(filters);
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = "student-profiles.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Allow the browser to begin consuming the object URL before releasing it.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
```

### 10.5 Sharing retries and status polling

Keep the preview request object and its `request_id` in the screen's state for
the lifetime of that selection. If its response is lost, retry the same object.
If selected data changes or a stale digest is reported, deliberately create a
fresh request UUID, fetch a new preview and review it before sending.

```javascript
// First explicit Preview action: create one instruction and keep it in UI state.
const previewRequest = {
  request_id: crypto.randomUUID(),
  student_ids: selectedStudentIds,
  academic_session: selectedSessionId,
  semester: selectedSemester,
  channels: selectedChannels,
};
const batch = await previewGuardianResults(previewRequest);

// Separate explicit Send action after HOD review of reports and destinations.
const queued = await queueResultShare(batch.id, batch.history_digest);

// Subsequent GETs inspect progress; queued/processing/unknown are distinct states.
const latest = await getResultShare(queued.id);
// A lost Send response can be resolved by reading this same batch UUID.
// Do not create a fresh batch automatically: that would be a new potential send.
```

If polling is added, space GETs appropriately, stop on unmount or logout, avoid
overlapping reads, and back off on failures. Polling only reads status; it does
not start the worker or prove provider delivery. The project has not agreed a
production polling interval.

## 11. Methods and integration work not completed yet

Everything in this section is separate from the implemented method catalog.
An existing prototype button or local converter function does not establish an
API route. Names below are **proposed client responsibilities**, not callable
backend methods. Unless an existing proposal is explicitly linked, HTTP paths,
payloads, roles and state transitions still need a reviewed contract.

### 11.1 Backend business methods that do not exist yet

| Proposed method(s) | What they would do | Missing work / current boundary |
| --- | --- | --- |
| `uploadImportFile`, `previewImport`, `commitImport`, `getImportStatus` | Upload extracted CSV, validate rows/conflicts, show a review, and atomically accept it with safe re-import behavior. | No active import routes. PDF/CSV scripts are local tools; staging, provenance, conflict reporting and safe commit are unfinished. |
| `createRegistrationDraft`, `updateRegistrationDraft`, `submitRegistration`, `reviewRegistration` | Save/select courses, submit to an adviser, return for correction or approve enrollment. | Browser demo only; registration models/routes, validation and review transitions need implementation. Course catalogs are not registrations. |
| `listLecturerCourses`, `listCourseRoster`, `submitResultBatch`, `reviewResultBatch` | Scope a lecturer to assigned courses and review an entered/uploaded batch of scores. | Attendance-specific course assignments and confirmed rosters now exist (8.6); they do not grant lecturer result access. No lecturer result-batch draft/submitted/returned state exists. Existing result APIs manage individual rows and verification. |
| `exportAcademicResults`, `downloadTranscript` | Download reviewed period-specific academic reports or an official transcript. | Only student-profile CSV export exists. Result-sharing messages are not CSV/PDF transcripts. Report scope, format and authority need implementation. |
| `updateMyStudentProfile` | Let a student edit explicitly allowed own contact fields. | `/api/me/student/` is read-only. Staff PATCH is not student self-service. |
| `listAdviserAssignments`, `listStaffChoices`, `createAdviserAssignment`, `updateAdviserAssignment` | Feed React selectors and administer adviser/staff assignment changes. | Models/admin exist, but no React JSON assignment/account-list APIs. `auth/me/` provides levels only. |
| `createLecturerAssignment`, `updateLecturerAssignment` | Administer course-based lecturer access. | Attendance-only course assignments exist (8.6). General lecturer profile/result access remains unfinished; academic APIs use staff permissions and adviser scope. |
| `listStudentCatalogChoices` | Supply permitted sessions/courses/offerings to student/adviser screens. | Current catalogs are HOD-only. Broader selector access and field/scope rules need reviewed API support. |
| `listTimetable`, `updateTimetable`, `publishTimetable` | Read schedules and publish authorized time/venue changes. | Prototype only; no active timetable API. |
| `uploadLearningResource`, `listLearningResources`, `downloadLearningResource` | Publish and privately retrieve permitted course materials. | Prototype only; file storage, validation, access and download APIs are unfinished. |
| `createStudentRequest`, `respondToRequest`, `escalateRequest`, `reviewRequest` | Submit a student enquiry/request and track adviser/HOD decisions. | Prototype only; persistent request, attachment and review contracts are missing. |
| `requestAppointment`, `reviewAppointment`, `listAppointments` | Request and confirm/decline advising appointments. | Prototype only; no backend appointment routes. |
| `createAdvisingNote`, `updateAdvisingNote`, `listAdvisingNotes` | Save guidance with explicit student/staff visibility and follow-up information. | Prototype only; backend visibility and persistence rules remain unfinished. |
| `sendCourseAnnouncement`, `listNotifications`, `markNotificationRead` | Address course cohorts and maintain unread notifications. | Existing adviser/HOD inboxes have fixed audiences; no course broadcast, unread flag, notification API or HOD-message detail route. |
| `getDashboardMetrics`, `listDecisionHistory`, `listAuditEvents` | Return role-scoped metrics and durable action/review history. | Prototype data is illustrative; complete backend metrics/audit routes and sensitive-action audit recording are unfinished. |
| `evaluateCurriculumCompleteness`, `listAcademicWarnings` | Apply agreed credit/course/pass rules and explain outstanding requirements. | Current graduation is HOD-manifest review. Automatic curricula, substitutions and deferred warning rules remain unfinished. |
| `uploadStudentDocument`, `downloadStudentDocument`, `archiveStudentDocument` | Manage private student filing documents and revisions. | Scope, permitted files/sizes, private storage, malware checks, retention and versioning must be agreed and implemented. |
| `deleteStudent`, `deleteGuardian`, `deleteResult`, catalog deletion methods | Remove data under agreed history/retention rules. | No active DELETE endpoints. Relationships and academic history must not be treated as disposable prototype state. |

The expanded journeys are described in
[frontend/prototypes/WORKFLOWS.md](frontend/prototypes/WORKFLOWS.md). Those screens
currently use browser-local synthetic state. A production React implementation
must distinguish available backend operations from these proposals.

If a placeholder is needed in frontend planning code, make its unavailability
explicit; do not fabricate a working request:

```javascript
// TODO: agree the multipart payload, validation/preview response and upload route.
// This is deliberately a planning stub, not an implemented API call.
export async function uploadImportFile(file) {
  void file;
  throw new Error("Import upload is not implemented in the active backend.");
}
```

### 11.2 Identity/ESP32 methods: proposed, not implemented

The existing proposal in
[docs/api-esp32-cheat-sheet.md](docs/api-esp32-cheat-sheet.md) names the following
routes. They are **absent from the active URL configuration**; response codes
and authentication details still require contract review.

| Proposed caller/method | Proposed HTTP route | Intended instruction |
| --- | --- | --- |
| React staff: `createIdentityCheck` | `POST /api/identity/v1/checks/` | Request a check for a selected registered device. Server would create the request, challenge and expiry. |
| Device: `getNextIdentityCheck` | `GET /api/identity/v1/devices/me/checks/next/` | Obtain that authenticated device's pending check. This is a firmware call, not a React student's call. |
| Device: `submitIdentityOutcome` | `POST /api/identity/v1/outcomes/` | Report matched/no-match/error with request/event/challenge binding and a credential reference when appropriate. |
| React staff: `getIdentityCheck` | `GET /api/identity/v1/checks/{request_id}/` | Read the permitted server-validated outcome. Academic records would still require separate authorization. |

Device registry, enrollment/mapping, actual sensor capabilities, authentication,
expiry/replay rejection, deduplication and integration tests are unfinished.
Fingerprint capture/templates/matching belong to the separately reviewed
biometric design; the React student-record API is not a biometric upload API.
Attendance/class sessions and pending JSONL ingestion are implemented in 8.6.
They do not implement identity-check routes or prove device/student identity.

### 11.3 Communication approaches not configured

| Approach | Status and intended use |
| --- | --- |
| Multipart `FormData` upload | No multipart application upload route. Pending attendance captures use raw application/x-ndjson (8.6); future CSV imports/attachments need their own contract. The JSON helper cannot send FormData; a future upload helper must let the browser set its multipart boundary. |
| WebSocket | No implemented socket endpoint/consumer. A possible future push channel for terminal outcomes or notifications; requires its own authentication and message contract. |
| Server-sent events (SSE) | No implemented event stream. Ordinary GET status reads exist for sharing batches. |
| GraphQL | No schema or endpoint. Current methods use REST routes. |
| JWT/bearer API login | No issued access/refresh-token contract. Browser authentication currently uses Django sessions and CSRF. |
| Direct cross-origin React API access | CORS/cookie deployment support is not configured; current integration assumes a same-origin proxy. |
| OpenAPI/Swagger API discovery | No generated schema/documentation route is configured. This Markdown reference is manually checked against source. |

An HTTP library such as Axios would be another client for the existing HTTP
contract, not another backend capability. No Axios setup exists in this workspace;
the examples here use native fetch. Choosing a client library does not make
the unfinished methods available.

### 11.4 Implemented backend methods with unfinished integration

| Existing capability | Work still required |
| --- | --- |
| Login/current identity/logout | Implemented and browser-verified for the guardian-email page. Extend shared auth/navigation to the finished frontend and other screens. |
| Password change/reset and account provisioning | Build React pages; configure reset URL/SMTP and shared throttle cache; validate mail/browser recovery flow and initial credential handling. |
| Students/guardians and profile export | Build real React directory/edit/export controls with scope checks and loading/empty/denied states; verify actual browser downloads. |
| Individual results, grading and graduation | Build authorized screens, independent verification controls, digest-based review and clear completeness handling; validate approved rules/data in PostgreSQL. |
| Adviser/HOD messaging | Build actual compose/inbox screens; provide an agreed assignment/recipient selection source without inventing IDs or widening access. |
| Guardian preview/queue/history/retry | Email React controls and polling worker are implemented; Gmail mock receipt confirmed. Merge into the finished frontend, activate supervised production worker, configure Meta template/token/version and validate sharing concurrency/provider delivery. |
| Attendance/classes and pending uploads | APIs exist (8.6); React controls, reviewed student binding/matching/reconciliation, trusted timing, device authentication and completed-class/excused/75% metrics remain unfinished. |
| Provider delivery outcomes | Add authenticated webhooks/reconciliation for delivered/read/bounce status. Current `accepted` remains submission acceptance only. |
| Database and deployment | Reconcile the shared source schema/data, prepare a dedicated PostgreSQL target, validate migrations/recovery, configure HTTPS/proxy/secrets/monitoring and complete deployment checks. |
| Sensitive-action auditing | Record profile/result/verification/import/bulk/permission events; existing latest-review records are not a complete immutable audit system. |

For the current work inventory, see
[docs/project-remaining-work.md](docs/project-remaining-work.md). Historical
README/guide statements can lag behind active code; verify the relevant route
before changing a feature's implemented status.

## 12. Source files and maintenance

| Contract area | Active implementation |
| --- | --- |
| Root prefixes and mounted routes | [app/config/urls.py](app/config/urls.py) |
| Sessions, CSRF, identity, messaging | [app/accounts/urls.py](app/accounts/urls.py), [message_urls.py](app/accounts/message_urls.py), [views.py](app/accounts/views.py), [serializers.py](app/accounts/serializers.py), [services.py](app/accounts/services.py) |
| Password/account lifecycle | [app/accounts/lifecycle_views.py](app/accounts/lifecycle_views.py), [lifecycle.py](app/accounts/lifecycle.py) |
| Student profiles, filtering, transitions | [app/students/urls.py](app/students/urls.py), [views.py](app/students/views.py), [serializers.py](app/students/serializers.py), [services.py](app/students/services.py) |
| Guardians and profile CSV | [app/students/guardian_views.py](app/students/guardian_views.py), [export_views.py](app/students/export_views.py) |
| Academics, catalogs, grading and review | [app/academics/urls.py](app/academics/urls.py), [views.py](app/academics/views.py), [serializers.py](app/academics/serializers.py), [services.py](app/academics/services.py), [graduation.py](app/academics/graduation.py), [calculations.py](app/academics/calculations.py) |
| Current academic session | [app/academics/current_session_views.py](app/academics/current_session_views.py), [current_session.py](app/academics/current_session.py) |
| Attendance and pending uploads | [app/attendance/urls.py](app/attendance/urls.py), [views.py](app/attendance/views.py), [pending_views.py](app/attendance/pending_views.py), [docs/attendance-pending-batches.md](docs/attendance-pending-batches.md) |
| Guardian React integration | [frontend/guardian-results/README.md](frontend/guardian-results/README.md), [src/api.js](frontend/guardian-results/src/api.js) |
| Guardian result sharing | [app/academics/sharing_views.py](app/academics/sharing_views.py), [sharing.py](app/academics/sharing.py), [sharing_worker.py](app/academics/sharing_worker.py), [sharing_transport.py](app/academics/sharing_transport.py) |
| Deployment/auth settings | [app/config/settings.py](app/config/settings.py), [.env.example](.env.example) |
| Additional contract detail | [docs/backend-lifecycle-guide.md](docs/backend-lifecycle-guide.md), [docs/academics-api.md](docs/academics-api.md), [docs/guardian-result-sharing.md](docs/guardian-result-sharing.md) |

When adding/changing an API, update its route row, commented client method,
payload/response fields, access rules and unfinished-work status together.
Keep proposed routes separate until they are mounted in the active application.
Examples should continue to use synthetic records and should never include
credentials or personal student/guardian data.
