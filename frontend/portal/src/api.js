let csrfToken = null;
let csrfRequest = null;
let sessionEpoch = 0;
const sessionListeners = new Set();

export function subscribeSessionLost(listener) {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

export function forgetSession() {
  sessionEpoch += 1;
  csrfToken = null;
  csrfRequest = null;
}

function sessionLost() {
  forgetSession();
  sessionListeners.forEach((listener) => listener());
}

// A forbidden action is not necessarily an expired session. Ask /me before
// removing a signed-in user's private workspace after an ordinary 403.
async function checkForbiddenSession(started) {
  try {
    const response = await fetch('/api/auth/me/', {
      credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
    });
    if (started === sessionEpoch && [401, 403].includes(response.status)) sessionLost();
  } catch { /* Keep the original action error when the network is unavailable. */ }
}

export class ApiError extends Error {
  constructor(message, status, details = null, retryAfter = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

function buildApiUrl(path, query = {}) {
  if (!path.startsWith("/api/")) {
    throw new TypeError("API paths must start with /api/.");
  }

  const url = new URL(path, window.location.origin);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url;
}

function pathId(value) {
  return encodeURIComponent(String(value));
}

function requestErrorMessage(details, status) {
  if (typeof details?.detail === "string") return details.detail;
  if (Array.isArray(details?.non_field_errors)) {
    return details.non_field_errors.join(" ");
  }
  if (details && typeof details === "object") {
    const fieldErrors = Object.values(details)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter((value) => typeof value === "string");
    if (fieldErrors.length) return fieldErrors.join(" ");
  }
  return `The request failed (${status}).`;
}

export async function apiRequest(
  path,
  { method = "GET", query = {}, body, rawBody = false, signal, responseType = "json", headers: extraHeaders = {} } = {},
) {
  const started = sessionEpoch;
  const verb = method.toUpperCase();
  const headers = {
    Accept: responseType === "blob" ? "text/csv" : "application/json",
    ...extraHeaders,
  };
  const isWrite = !["GET", "HEAD", "OPTIONS"].includes(verb);

  if (isWrite) {
    headers["X-CSRFToken"] = await getCsrfToken();
  }
  if (body !== undefined && !rawBody) {
    headers["Content-Type"] = "application/json";
  }
  if (started !== sessionEpoch) throw new ApiError('The session changed. Sign in again.', 401);

  let response;
  try {
    response = await fetch(buildApiUrl(path, query), {
    method: verb,
    credentials: "same-origin",
    cache: "no-store",
    headers,
    body: body === undefined ? undefined : rawBody ? body : JSON.stringify(body),
    signal,
  });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Unable to reach the server. Check your connection and try again.', 0);
  }
  if (started !== sessionEpoch) throw new ApiError('The session changed. Sign in again.', 401);

  if (!response.ok) {
    const text = await response.text();
    let details = null;
    if ((response.headers.get("Content-Type") || "").includes("application/json")) {
      try {
        details = JSON.parse(text);
      } catch {
        details = null;
      }
    }
    if (response.status === 403 && isWrite) { csrfToken = null; csrfRequest = null; }
    if (!path.startsWith('/api/auth/login/') && !path.startsWith('/api/auth/password/reset/') && !path.startsWith('/api/auth/student/setup/')) {
      if (response.status === 401 || (response.status === 403 && path === '/api/auth/me/')) sessionLost();
      else if (response.status === 403) await checkForbiddenSession(started);
    }
    throw new ApiError(
      requestErrorMessage(details, response.status),
      response.status,
      details,
      response.headers.get("Retry-After"),
    );
  }

  if (response.status === 204 || verb === "HEAD") return null;
  if (responseType === "blob") {
    const value = await response.blob();
    if (started !== sessionEpoch) throw new ApiError('The session changed. Sign in again.', 401);
    return value;
  }
  if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
    throw new ApiError(
      "Expected a JSON API response. Check the API proxy.",
      response.status,
    );
  }

  const data = await response.json();
  if (started !== sessionEpoch) throw new ApiError('The session changed. Sign in again.', 401);
  return data;
}

function apiGet(path, query = {}, signal) {
  return apiRequest(path, { query, signal });
}

function apiPost(path, body = {}) {
  return apiRequest(path, { method: "POST", body });
}

function apiPatch(path, body) {
  return apiRequest(path, { method: "PATCH", body });
}

function apiPut(path, body) {
  return apiRequest(path, { method: "PUT", body });
}

export async function getCsrfToken({ refresh = false } = {}) {
  if (refresh) {
    csrfToken = null;
    csrfRequest = null;
  }
  if (csrfToken) return csrfToken;
  if (!csrfRequest) {
    const pending = apiGet("/api/auth/csrf/")
      .then((data) => {
        const token = data?.csrfToken;
        if (typeof token !== "string" || !token) {
          throw new ApiError("The CSRF endpoint returned no token.", 200);
        }
        csrfToken = token;
        return token;
      })
      .finally(() => {
        if (csrfRequest === pending) csrfRequest = null;
      });
    csrfRequest = pending;
  }
  return csrfRequest;
}

export async function login(username, password) {
  forgetSession();
  const identity = await apiPost("/api/auth/login/", { username, password });
  await getCsrfToken({ refresh: true });
  return identity;
}

export async function logout() {
  await apiPost("/api/auth/logout/");
  forgetSession();
}

export function getCurrentUser(signal) {
  return apiGet("/api/auth/me/", {}, signal);
}

export function changePassword(currentPassword, newPassword) {
  return apiPost("/api/auth/password/change/", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export function getAdministrationOptions(signal) {
  return apiGet('/api/accounts/administration-options/', {}, signal);
}

export function listManagedStaff(query = {}, signal) {
  return apiGet('/api/accounts/staff/', query, signal);
}

export function createManagedStaff(values) {
  return apiPost('/api/accounts/staff/', values);
}

export function updateManagedStaff(staffId, values) {
  return apiPatch(`/api/accounts/staff/${pathId(staffId)}/`, values);
}

export function listAdviserAssignments(query = {}, signal) {
  return apiGet('/api/accounts/adviser-assignments/', query, signal);
}

export function createAdviserAssignment(values) {
  return apiPost('/api/accounts/adviser-assignments/', values);
}

export function updateAdviserAssignment(assignmentId, values) {
  return apiPatch(`/api/accounts/adviser-assignments/${pathId(assignmentId)}/`, values);
}

export function transferHod(values) {
  return apiPost('/api/accounts/transfer-hod/', values);
}

export function requestPasswordReset(email) {
  return apiPost("/api/auth/password/reset/", { email });
}

export function confirmPasswordReset(uid, token, newPassword) {
  return apiPost("/api/auth/password/reset/confirm/", {
    uid,
    token,
    new_password: newPassword,
  });
}

export function createStudentAccount(studentId, account) {
  return apiPost(`/api/students/${pathId(studentId)}/account/`, account);
}

export function getStudentLoginAccount(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/account/`, {}, signal);
}

export function issueStudentSetupLink(studentId, values = {}) {
  return apiPost(`/api/students/${pathId(studentId)}/account/setup-link/`, values);
}

export function updateStudentLoginAccount(studentId, values) {
  return apiPatch(`/api/students/${pathId(studentId)}/account/`, values);
}

export function emailStudentAccessLink(studentId, values) {
  return apiPost(`/api/students/${pathId(studentId)}/account/email-link/`, values);
}

export function confirmStudentSetup(uid, token, newPassword) {
  return apiPost('/api/auth/student/setup/confirm/', { uid, token, new_password: newPassword });
}

export function linkStudentAccount(studentId, accountId) {
  return apiPut(`/api/students/${pathId(studentId)}/account/`, {
    account_id: accountId,
  });
}

export function listStudents(filters = {}, signal) {
  return apiGet("/api/students/", filters, signal);
}

export function createStudent(student) {
  return apiPost("/api/students/", student);
}

export function lookupStudentIdentifier(identifierType, identifierValue, signal) {
  return apiGet('/api/students/lookup/', { identifier_type: identifierType, identifier_value: identifierValue }, signal);
}

export function promoteStudentIdentifier(studentId, identifierValue, expectedType, expectedValue) {
  return apiPost(`/api/students/${pathId(studentId)}/promote-identifier/`, {
    identifier_value: identifierValue, expected_identifier_type: expectedType, expected_identifier_value: expectedValue,
  });
}

export function listRecordImports(page = 1, signal, kind) {
  return apiGet('/api/imports/', { page, kind }, signal);
}

export function previewRecordImport(request) {
  return apiPost('/api/imports/previews/', request);
}

export function prepareRecordImport(file, options = {}) {
  const body = new FormData();
  body.append('file', file);
  for (const [name, value] of Object.entries(options)) {
    if (value !== '' && value !== undefined && value !== null) body.append(name, String(value));
  }
  return apiRequest('/api/imports/prepare/', { method: 'POST', body, rawBody: true });
}

export function getRecordImport(importId, signal) {
  return apiGet(`/api/imports/${pathId(importId)}/`, {}, signal);
}

export function refreshRecordImport(importId) {
  return apiPost(`/api/imports/${pathId(importId)}/refresh/`);
}

export function commitRecordImport(importId, review) {
  return apiPost(`/api/imports/${pathId(importId)}/commit/`, review);
}

export function getStudent(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/`, {}, signal);
}

export function updateStudent(studentId, changes) {
  return apiPatch(`/api/students/${pathId(studentId)}/`, changes);
}

export function getMyStudentProfile(signal) {
  return apiGet("/api/me/student/", {}, signal);
}

export function exportStudentProfiles(filters = {}, signal) {
  return apiRequest("/api/students/export/", {
    query: filters,
    signal,
    responseType: "blob",
  });
}

export function bulkChangeStudentLevels(studentIds, expectedLevel, currentLevel) {
  return apiPost("/api/students/bulk-level-change/", {
    student_ids: studentIds,
    expected_level: expectedLevel,
    current_level: currentLevel,
  });
}

export function bulkChangeStudentStatuses(
  studentIds,
  expectedStatus,
  academicStatus,
) {
  return apiPost("/api/students/bulk-status-change/", {
    student_ids: studentIds,
    expected_status: expectedStatus,
    academic_status: academicStatus,
  });
}

export function listGuardians(studentId, page = 1, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/guardians/`,
    { page },
    signal,
  );
}

export function createGuardian(studentId, guardian) {
  return apiPost(`/api/students/${pathId(studentId)}/guardians/`, guardian);
}

export function getGuardian(studentId, guardianId, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/`,
    {},
    signal,
  );
}

export function updateGuardian(studentId, guardianId, changes) {
  return apiPatch(
    `/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/`,
    changes,
  );
}

export function sendAdviserMessage(message) {
  return apiPost("/api/adviser-messages/", message);
}

export function sendHodMessage(message) {
  return apiPost("/api/hod-messages/", message);
}

export function listMyAdviserMessages(page = 1, signal) {
  return apiGet("/api/me/messages/", { page }, signal);
}

export function getMyAdviserMessage(messageId, signal) {
  return apiGet(`/api/me/messages/${pathId(messageId)}/`, {}, signal);
}

export function listMyHodMessages(page = 1, signal) {
  return apiGet("/api/me/hod-messages/", { page }, signal);
}

export function listResults(filters = {}, signal) {
  return apiGet("/api/results/", filters, signal);
}

export function createResult(result) {
  return apiPost("/api/results/", result);
}

export function getResult(resultId, signal) {
  return apiGet(`/api/results/${pathId(resultId)}/`, {}, signal);
}

export function updateResultScore(resultId, score) {
  return apiPatch(`/api/results/${pathId(resultId)}/`, { score });
}

export function verifyResult(resultId, expectedScore) {
  return apiPost(`/api/results/${pathId(resultId)}/verify/`, {
    expected_score: expectedScore,
  });
}

export function getStudentGpa(studentId, academicSession, semester, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/gpa/`,
    { academic_session: academicSession, semester },
    signal,
  );
}

export function getStudentCgpa(studentId, signal) {
  return apiGet(`/api/students/${pathId(studentId)}/cgpa/`, {}, signal);
}

export function getMyGpa(academicSession, semester, signal) {
  return apiGet(
    "/api/me/gpa/",
    { academic_session: academicSession, semester },
    signal,
  );
}

export function getMyCgpa(signal) {
  return apiGet("/api/me/cgpa/", {}, signal);
}

export function listMyResults(page = 1, signal) {
  return apiGet("/api/me/results/", { page }, signal);
}

export function getMyResult(resultId, signal) {
  return apiGet(`/api/me/results/${pathId(resultId)}/`, {}, signal);
}

export function listAcademicSessions(page = 1, signal) {
  return apiGet("/api/academic-sessions/", { page }, signal);
}

export function getCurrentAcademicSession(signal) {
  return apiGet("/api/academic-sessions/current/", {}, signal);
}

export function selectCurrentAcademicSession(academicSessionId, expectedSessionId = null) {
  return apiPut("/api/academic-sessions/current/", {
    academic_session: academicSessionId,
    expected_session_id: expectedSessionId,
  });
}

export function createAcademicSession(name) {
  return apiPost("/api/academic-sessions/", { name });
}

export function listCourses(page = 1, signal) {
  return apiGet("/api/courses/", { page }, signal);
}

export function createCourse(code, title) {
  return apiPost("/api/courses/", { code, title });
}

export function listCourseOfferings(page = 1, signal) {
  return apiGet("/api/course-offerings/", { page }, signal);
}

export function createCourseOffering(offering) {
  return apiPost("/api/course-offerings/", offering);
}

export function listGradingScales(page = 1, signal) {
  return apiGet("/api/grading-scales/", { page }, signal);
}

export function createGradingScale(scale) {
  return apiPost("/api/grading-scales/", scale);
}

export function getGradingScale(scaleId, signal) {
  return apiGet(`/api/grading-scales/${pathId(scaleId)}/`, {}, signal);
}

export function updateGradingScale(scaleId, changes) {
  return apiPatch(`/api/grading-scales/${pathId(scaleId)}/`, changes);
}

export function publishGradingScale(scaleId) {
  return apiPost(`/api/grading-scales/${pathId(scaleId)}/publish/`);
}

export function assignOfferingGradingScale(offeringId, scaleId) {
  return apiPatch(
    `/api/course-offerings/${pathId(offeringId)}/grading-scale/`,
    { grading_scale: scaleId },
  );
}

export function listCourseRequirements(studentId, page = 1, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/course-requirements/`,
    { page },
    signal,
  );
}

export function createCourseRequirement(studentId, requirement) {
  return apiPost(
    `/api/students/${pathId(studentId)}/course-requirements/`,
    requirement,
  );
}

export function getCourseRequirement(studentId, requirementId, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/course-requirements/${pathId(requirementId)}/`,
    {},
    signal,
  );
}

export function updateCourseRequirement(studentId, requirementId, changes) {
  return apiPatch(
    `/api/students/${pathId(studentId)}/course-requirements/${pathId(requirementId)}/`,
    changes,
  );
}

export function getGraduationReview(studentId, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/graduation-review/`,
    {},
    signal,
  );
}

export function approveGraduationReview(studentId, approval) {
  return apiPost(
    `/api/students/${pathId(studentId)}/graduation-review/`,
    approval,
  );
}

export function getGuardianSharingPreferences(studentId, guardianId, signal) {
  return apiGet(
    `/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/result-sharing/`,
    {},
    signal,
  );
}

export function setGuardianSharingPreferences(studentId, guardianId, preferences) {
  return apiPut(
    `/api/students/${pathId(studentId)}/guardians/${pathId(guardianId)}/result-sharing/`,
    preferences,
  );
}

export function previewGuardianResults(previewRequest) {
  return apiPost("/api/result-shares/preview/", previewRequest);
}

export function listResultShares(page = 1, signal) {
  return apiGet("/api/result-shares/", { page }, signal);
}

export function getResultShare(batchId, signal) {
  return apiGet(`/api/result-shares/${pathId(batchId)}/`, {}, signal);
}

export function queueResultShare(batchId, expectedDigest) {
  return apiPost(`/api/result-shares/${pathId(batchId)}/send/`, {
    expected_digest: expectedDigest,
  });
}

export function retryFailedResultShares(batchId) {
  return apiPost(`/api/result-shares/${pathId(batchId)}/retry/`);
}

export function getAttendanceRoster(offeringId, page = 1, signal) {
  return apiGet(`/api/attendance/offerings/${pathId(offeringId)}/roster/`, { page }, signal);
}

export function confirmAttendanceRoster(offeringId, studentIds, expectedRevision) {
  return apiPut(`/api/attendance/offerings/${pathId(offeringId)}/roster/`, {
    student_ids: studentIds,
    expected_revision: expectedRevision,
  });
}

export function setAttendanceStaff(offeringId, staffId, isActive) {
  return apiPut(`/api/attendance/offerings/${pathId(offeringId)}/staff/`, {
    staff: staffId,
    is_active: isActive,
  });
}

export function listAttendanceSessions(page = 1, signal) {
  return apiGet("/api/attendance/sessions/", { page }, signal);
}

export function openAttendanceSession(session) {
  return apiPost("/api/attendance/sessions/", session);
}

export function getAttendanceSession(sessionId, signal) {
  return apiGet(`/api/attendance/sessions/${pathId(sessionId)}/`, {}, signal);
}

export function closeAttendanceSession(sessionId) {
  return apiPost(`/api/attendance/sessions/${pathId(sessionId)}/close/`);
}

export function listAttendanceRecords(sessionId, page = 1, signal) {
  return apiGet(`/api/attendance/sessions/${pathId(sessionId)}/records/`, { page }, signal);
}

export function recordManualAttendance(sessionId, event) {
  return apiPost(`/api/attendance/sessions/${pathId(sessionId)}/records/`, event);
}

export function correctAttendanceRecord(recordId, status, reason) {
  return apiPost(`/api/attendance/records/${pathId(recordId)}/correct/`, {
    status,
    reason,
  });
}

export function getMyAttendance(page = 1, signal) {
  return apiGet("/api/me/attendance/", { page }, signal);
}

export function previewPendingCaptures(sessionId, fileBody, captureHash) {
  return apiRequest(`/api/attendance/sessions/${pathId(sessionId)}/pending-batches/preview/`, {
    method: "POST",
    body: fileBody,
    rawBody: true,
    headers: { "Content-Type": "application/x-ndjson", ...(captureHash ? { "X-Capture-SHA256": captureHash } : {}) },
  });
}

export function importPendingCaptures(sessionId, fileBody, captureHash) {
  return apiRequest(`/api/attendance/sessions/${pathId(sessionId)}/pending-batches/`, {
    method: "POST",
    body: fileBody,
    rawBody: true,
    headers: { "Content-Type": "application/x-ndjson", "X-Capture-SHA256": captureHash },
  });
}

// Follow page numbers only; never follow an arbitrary next URL with credentials.
export async function collectPages(loader, signal) {
  const rows = [];
  for (let page = 1; page <= 500; page += 1) {
    const data = await loader(page, signal);
    if (!Array.isArray(data?.results)) throw new ApiError('The server returned an invalid page.', 200);
    rows.push(...data.results);
    if (!data.next) return rows;
  }
  throw new ApiError('Too many records to load at once. Contact the administrator.', 0);
}

export function listPendingCaptureBatches(sessionId, page = 1, signal) {
  return apiGet(`/api/attendance/sessions/${pathId(sessionId)}/pending-batches/`, { page }, signal);
}
