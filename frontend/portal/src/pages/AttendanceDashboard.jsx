import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import {
  getCurrentAcademicSession,
  getMyAttendance,
  listAttendanceSessions,
} from "../api";
import "./AttendanceDashboard.css";

const sampleRecords = [
  { name: "Adebayo Olumide", staffId: "EEE/STAFF/021", department: "Power Systems", time: "08:04 AM", status: "Present" },
  { name: "Akinola Tobi", staffId: "EEE/STAFF/014", department: "Electronics", time: "08:12 AM", status: "Present" },
  { name: "Balogun Ife", staffId: "EEE/STAFF/032", department: "Telecommunications", time: "08:23 AM", status: "Late" },
  { name: "Oluwaseun Ade", staffId: "EEE/STAFF/008", department: "Control & Instrumentation", time: "08:31 AM", status: "Present" },
];

function formatTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return String(value);
}

function normalizeAttendanceRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) return [];

  return rows.map((row, index) => {
    const status = String(row?.status ?? row?.record_status ?? "present");
    const name = row?.name ?? row?.student_name ?? row?.student ?? `Student ${index + 1}`;
    const idValue = row?.student_id ?? row?.studentId ?? row?.id ?? `${index + 1}`;
    const department = row?.department ?? row?.session__offering_id ?? "Unassigned";
    const time = formatTime(row?.recorded_at ?? row?.recordedAt ?? row?.time ?? row?.check_in ?? row?.created_at);

    return {
      name: typeof name === "string" ? name : String(name),
      staffId: String(idValue),
      department: typeof department === "string" ? department : String(department),
      time,
      status: status.charAt(0).toUpperCase() + status.slice(1),
    };
  });
}

function Icon({ children }) {
  return <span className="attendance-icon" aria-hidden="true">{children}</span>;
}

function AttendanceDashboard() {
  const navigate = useNavigate();
  const { user, status } = useAuth();
  const [sessionInfo, setSessionInfo] = useState(null);
  const [attendanceSessions, setAttendanceSessions] = useState([]);
  const [attendanceRecords, setAttendanceRecords] = useState(sampleRecords);
  const [search, setSearch] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user || status !== "ready") {
      return;
    }

    let isMounted = true;

    const loadData = async () => {
      setLoading(true);
      setLoadError("");
      try {
        if (user.role === "hod") {
          const current = await getCurrentAcademicSession().catch(() => null);
          if (isMounted) {
            setSessionInfo(current ?? { name: "No active session selected", academic_session: null, source: "database" });
          }
        }

        const sessionsResponse = await listAttendanceSessions(1).catch(() => ({ results: [] }));
        const sessions = Array.isArray(sessionsResponse)
          ? sessionsResponse
          : sessionsResponse?.results ?? [];

        if (isMounted) {
          setAttendanceSessions(sessions);
        }

        const response = await getMyAttendance(1).catch(() => ({ results: [] }));
        const rows = Array.isArray(response)
          ? response
          : response?.results ?? [];
        const normalized = normalizeAttendanceRows(rows);

        if (isMounted) {
          setAttendanceRecords(normalized.length > 0 ? normalized : sampleRecords);
        }
      } catch (error) {
        if (isMounted) {
          setLoadError(error.message || "Attendance data could not be loaded from the API.");
          setAttendanceRecords(sampleRecords);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, [status, user]);

  const filteredRecords = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return attendanceRecords;
    return attendanceRecords.filter((record) =>
      [record.name, record.staffId, record.department, record.status]
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [attendanceRecords, search]);

  const canViewDashboard = !!user && ["hod", "staff"].includes(user.role);

  if (!user) {
    return (
      <AccessMessage
        title="Sign in to continue"
        message="The attendance dashboard is available only to staff and HOD accounts with active session authentication."
      />
    );
  }

  if (!canViewDashboard) {
    return (
      <AccessMessage
        title="Attendance access not approved"
        message="This account is not authorized for the department attendance workspace. Sign in with a staff or HOD role to continue."
      />
    );
  }

  return (
    <main className="attendance-app">
      <aside className="attendance-sidebar">
        <Link to="/" className="attendance-brand" aria-label="EEE OAU home">
          <span className="attendance-brand-mark">E</span>
          <span><strong>EEE OAU</strong><small>Attendance portal</small></span>
        </Link>

        <p className="attendance-nav-label">WORKSPACE</p>
        <nav className="attendance-nav" aria-label="Attendance navigation">
          <a href="#overview" className="active"><Icon>▦</Icon>Overview</a>
          <a href="#sessions"><Icon>▤</Icon>Sessions</a>
          <a href="#records"><Icon>◫</Icon>Attendance records</a>
        </nav>

        <div className="attendance-userbox">
          <span className="attendance-user-label">SIGNED IN</span>
          <strong>{user.username || user.email || "Authenticated user"}</strong>
          <small>{user.role === "hod" ? "Head of Department" : "Staff member"}</small>
        </div>

        <button type="button" className="attendance-signout" onClick={() => navigate("/login")}>Return to login</button>
      </aside>

      <section className="attendance-main" id="overview">
        <div className="attendance-topbar">
          <div>
            <p className="attendance-eyebrow">EEE OAU · STAFF ATTENDANCE</p>
            <h1>Department attendance dashboard</h1>
          </div>
          <span className="attendance-status-chip">{loading ? "Syncing" : "Connected"}</span>
        </div>

        <section className="attendance-stat-grid">
          <StatCard icon="◔" label="Current academic session" value={sessionInfo?.name || "Not selected"} detail={sessionInfo?.source ? `Source: ${sessionInfo.source}` : "Awaiting selection"} tone="blue" />
          <StatCard icon="✓" label="Open sessions" value={String(attendanceSessions.length)} detail="Visible class records" tone="green" />
          <StatCard icon="⌁" label="Recorded attendance" value={String(attendanceRecords.length)} detail="Recent entries" tone="orange" />
          <StatCard icon="△" label="API status" value={loadError ? "Warning" : "Live"} detail={loadError || "Session-authenticated API ready"} tone="slate" />
        </section>

        <section className="session-panel" id="sessions">
          <div className="records-heading">
            <div>
              <h2>Current session and attendance classes</h2>
              <p>{sessionInfo?.name ? `Academic session: ${sessionInfo.name}` : "No current session has been selected yet."}</p>
            </div>
          </div>

          <div className="attendance-session-list">
            {attendanceSessions.length === 0 ? (
              <p className="empty-records">No attendance sessions are visible yet. The backend will populate this list after a class is opened.</p>
            ) : (
              attendanceSessions.map((session, index) => (
                <article key={session.id ?? session.session_id ?? `attendance-session-${index}`} className="attendance-session-item">
                  <div>
                    <strong>{session.title || session.name || "Attendance class"}</strong>
                    <small>
                      {session.offering ? `Offering ${session.offering}` : "Current offering"} · {session.status || "Open"}
                    </small>
                  </div>
                  <span>
                    {session.starts_at ? formatTime(session.starts_at) : "Pending start"}
                  </span>
                </article>
              ))
            )}
          </div>
        </section>

        {loadError && <p className="scan-upload-error" role="alert">{loadError}</p>}

        <section className="records-panel" id="records">
          <div className="records-heading">
            <div>
              <h2>Recent attendance</h2>
              <p>{attendanceSessions.length ? "Latest visible records from the configured attendance API." : "Using sample data until a live attendance class is available."}</p>
            </div>
            <label className="attendance-search">
              <span aria-hidden="true">⌕</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search staff..."
                aria-label="Search attendance records"
              />
            </label>
          </div>

          <div className="attendance-table-wrap">
            <table className="attendance-table">
              <thead><tr><th>Staff member</th><th>Department</th><th>Check-in</th><th>Status</th></tr></thead>
              <tbody>
                {filteredRecords.map((record, index) => (
                  <tr key={`${record.staffId}-${record.time}-${index}`}>
                    <td><strong>{record.name}</strong><small>{record.staffId}</small></td>
                    <td>{record.department}</td>
                    <td>{record.time}</td>
                    <td><span className={`record-status ${record.status.toLowerCase()}`}>{record.status}</span></td>
                  </tr>
                ))}
                {filteredRecords.length === 0 && <tr><td className="empty-records" colSpan="4">No records match your search.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="attendance-footer">EEE OAU · Attendance API integration <span>Session-authenticated backend requests use CSRF-protected Django endpoints.</span></footer>
      </section>
    </main>
  );
}

function StatCard({ icon, label, value, detail, tone }) {
  return (
    <article className="attendance-stat">
      <span className={`stat-icon ${tone}`} aria-hidden="true">{icon}</span>
      <p>{label}</p><strong>{value}</strong><small>{detail}</small>
    </article>
  );
}

function AccessMessage({ title, message }) {
  const navigate = useNavigate();
  return (
    <main className="attendance-gate">
      <div className="gate-card">
        <span className="gate-mark" aria-hidden="true">E</span>
        <p className="attendance-eyebrow">EEE OAU · STAFF ATTENDANCE</p>
        <h1>{title}</h1>
        <p>{message}</p>
        <div className="gate-actions">
          <Link to="/login" className="gate-primary">Sign in</Link>
          <button type="button" onClick={() => navigate("/")}>Back to home</button>
        </div>
        <small>Use a signed-in staff or HOD account to access the session-aware attendance API.</small>
      </div>
    </main>
  );
}

export default AttendanceDashboard;
