import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import Sectionheader from "../components/Sectionheader";

const roles = {
  student: { title: "Student", welcome: "Your academic workspace" },
  staff: { title: "Staff / Lecturer", welcome: "Your teaching workspace" },
  hod: { title: "Head of Department", welcome: "Department overview" },
  adviser: { title: "Part Adviser", welcome: "Your cohort workspace" },
};

const navigation = {
  student: [
    ["dashboard", "Dashboard"],
    ["profile", "Profile"],
    ["courses", "Courses & registration"],
    ["results", "Results"],
    ["timetable", "Timetable"],
    ["resources", "Learning resources"],
    ["requests", "Requests & complaints"],
    ["adviser", "Part adviser"],
    ["notifications", "Notifications"],
  ],
  staff: [
    ["dashboard", "Dashboard"],
    ["profile", "Profile"],
    ["courses", "Course management"],
    ["results", "Results management"],
    ["students", "Student records"],
    ["communication", "Communication"],
    ["timetable", "Timetable"],
  ],
  hod: [
    ["dashboard", "Department overview"],
    ["profile", "Profile"],
    ["assignments", "Staff assignments"],
    ["courses", "Course oversight"],
    ["approvals", "Approval queue"],
    ["communication", "Department announcements"],
    ["reports", "Reports"],
    ["history", "Decision history"],
  ],
  adviser: [
    ["dashboard", "Advising dashboard"],
    ["profile", "Profile"],
    ["students", "Assigned students"],
    ["academic-summary", "Academic summaries"],
    ["approvals", "Registration review"],
    ["records", "Advising records"],
    ["communication", "Student communication"],
    ["escalations", "Escalations"],
  ],
};

const courses = [
  { code: "EEE 301", title: "Electrical Machines I", units: 3, type: "Compulsory" },
  { code: "EEE 303", title: "Electromagnetic Fields", units: 3, type: "Compulsory" },
  { code: "EEE 305", title: "Digital Systems Design", units: 2, type: "Compulsory" },
  { code: "EEE 307", title: "Control Engineering", units: 3, type: "Compulsory" },
  { code: "EEE 309", title: "Introduction to Robotics", units: 2, type: "Elective" },
];

const students = [
  { name: "Adebayo Olumide", matric: "EEE/2022/014", level: "300", status: "Submitted" },
  { name: "Akinola Tobi", matric: "EEE/2022/027", level: "300", status: "Pending review" },
  { name: "Balogun Ife", matric: "EEE/2022/038", level: "300", status: "Returned" },
];

const className =
  "rounded-2xl border border-blue-400/20 bg-slate-950/80 shadow-lg shadow-blue-950/20";
const fieldClass =
  "w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30";
const primaryButton =
  "rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-300";
const secondaryButton =
  "rounded-xl border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-blue-400 hover:text-white";

function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <Sectionheader eyebrow={eyebrow} title={title} level={1} />
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{description}</p>}
      </div>
      {action}
    </div>
  );
}

function StatCard({ label, value, detail }) {
  return (
    <div className={`${className} p-5`}>
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      {detail && <p className="mt-2 text-xs text-blue-300">{detail}</p>}
    </div>
  );
}

function Panel({ title, subtitle, children, className: extraClass = "" }) {
  return (
    <section className={`${className} p-5 sm:p-6 ${extraClass}`}>
      {(title || subtitle) && (
        <div className="mb-5">
          {title && <h2 className="text-lg font-bold text-white">{title}</h2>}
          {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

function Status({ children }) {
  const tone =
    children === "Approved" || children === "Published"
      ? "bg-emerald-400/10 text-emerald-300"
      : children === "Returned" || children === "Needs attention"
        ? "bg-amber-400/10 text-amber-200"
        : "bg-blue-400/10 text-blue-200";
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${tone}`}>{children}</span>;
}

function DataTable({ headers, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
          <tr>{headers.map((header) => <th key={header} className="px-3 py-3 font-semibold">{header}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="text-slate-300">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-3 py-4">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DemoForm({ title, description, submitLabel = "Save draft", fields = ["Title", "Details"] }) {
  const handleSubmit = (event) => {
    event.preventDefault();
    toast.info("Demo only: this item has not been sent to a server.", { position: "top-center" });
  };
  return (
    <Panel title={title} subtitle={description}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {fields.map((field) => (
          <label key={field} className="block text-sm font-medium text-slate-300">
            {field}<span className="ml-1 text-blue-300">*</span>
            {field.toLowerCase().includes("details") || field.toLowerCase().includes("message") ? (
              <textarea className={`${fieldClass} mt-2 min-h-28 resize-y`} required placeholder={`Enter ${field.toLowerCase()}`} />
            ) : (
              <input className={`${fieldClass} mt-2`} required placeholder={`Enter ${field.toLowerCase()}`} />
            )}
          </label>
        ))}
        <label className="block text-sm text-slate-400">
          Supporting attachment (optional)
          <input className="mt-2 block w-full text-sm text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:font-semibold file:text-white" type="file" />
        </label>
        <button className={primaryButton} type="submit">{submitLabel}</button>
      </form>
    </Panel>
  );
}

function Dashboard({ role, navigateTo }) {
  const isStudent = role === "student";
  const isHod = role === "hod";
  const isAdviser = role === "adviser";

  if (isStudent) {
    return (
      <>
        <style>{`
          .student-dashboard {
            color: #1a2940;
          }

          .student-dashboard-shell {
            background: #f3f5f8;
            border: 1px solid rgba(35, 73, 128, 0.16);
            border-radius: 12px;
            padding: 0;
            overflow: hidden;
          }

          .student-dashboard-top {
            background: linear-gradient(180deg, #0c3e89 0%, #0d3a7a 100%);
            padding: 18px 22px 20px;
            color: #fff;
          }

          .student-dashboard-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
          }

          .student-dashboard-brand {
            font-size: 0.95rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            color: #f7faff;
          }

          .student-dashboard-links {
            display: flex;
            align-items: center;
            gap: 14px;
            font-size: 0.72rem;
            color: rgba(255,255,255,0.82);
          }

          .student-dashboard-links a {
            color: inherit;
            text-decoration: none;
          }

          .student-dashboard-links .student-dashboard-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
          }

          .student-dashboard-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            margin-top: 18px;
            padding: 0 4px 0 2px;
          }

          .student-dashboard-profile {
            display: flex;
            align-items: center;
            gap: 15px;
          }

          .student-dashboard-avatar {
            display: grid;
            place-items: center;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(255,255,255,0.18);
            border: 1px solid rgba(255,255,255,0.24);
            font-size: 1.1rem;
            font-weight: 700;
          }

          .student-dashboard-name {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 700;
          }

          .student-dashboard-meta {
            margin: 4px 0 0;
            font-size: 0.72rem;
            color: rgba(255,255,255,0.8);
          }

          .student-dashboard-actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
          }

          .student-dashboard-btn {
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 7px;
            padding: 9px 15px;
            background: rgba(255,255,255,0.08);
            color: #f4f7ff;
            font-size: 0.74rem;
            font-weight: 600;
            cursor: pointer;
          }

          .student-dashboard-btn.primary {
            background: #0d5bd5;
            border-color: rgba(255,255,255,0.6);
          }

          .student-dashboard-content {
            background: #edf3f7;
            padding: 20px 18px 18px;
            border-top: 1px solid rgba(18, 54, 112, 0.13);
          }

          .student-dashboard-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 12px;
          }

          .student-dashboard-title h3 {
            margin: 0;
            font-size: 1.05rem;
            font-weight: 700;
            color: #152741;
          }

          .student-dashboard-card {
            background: #ffffff;
            border: 1px solid rgba(28, 64, 117, 0.14);
            border-radius: 10px;
            box-shadow: 0 6px 15px rgba(17, 36, 65, 0.04);
          }

          .student-dashboard-overview {
            padding: 14px 18px 8px;
          }

          .student-dashboard-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 8px;
          }

          .student-dashboard-field {
            background: #f7f9fb;
            border: 1px solid rgba(31, 63, 104, 0.08);
            border-radius: 8px;
            padding: 10px 12px;
          }

          .student-dashboard-field span {
            display: block;
            font-size: 0.7rem;
            color: #58708b;
            margin-bottom: 4px;
          }

          .student-dashboard-field strong {
            font-size: 0.86rem;
            color: #1c2d44;
            overflow-wrap: anywhere;
          }

          .student-dashboard-status {
            margin-top: 18px;
            padding: 14px 18px 16px;
          }

          .student-dashboard-status table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            font-size: 0.8rem;
          }

          .student-dashboard-table-wrap {
            overflow-x: auto;
          }

          .student-dashboard-status th,
          .student-dashboard-status td {
            padding: 10px 8px;
            text-align: left;
            border-bottom: 1px solid rgba(31, 63, 104, 0.09);
            color: #24354b;
          }

          .student-dashboard-status th {
            color: #576d89;
            font-size: 0.7rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
          }

          .student-dashboard-status .positive {
            color: #0d6b47;
            font-weight: 600;
          }

          .student-dashboard-status .muted {
            color: #5d6e87;
          }

          .student-dashboard-footer {
            margin-top: 12px;
            text-align: center;
            font-size: 0.7rem;
            color: #75849a;
          }

          @media (max-width: 820px) {
            .student-dashboard-grid {
              grid-template-columns: 1fr;
            }

            .student-dashboard-header,
            .student-dashboard-hero,
            .student-dashboard-title {
              flex-direction: column;
              align-items: flex-start;
            }

            .student-dashboard-links {
              flex-wrap: wrap;
            }

            .student-dashboard-status table {
              min-width: 420px;
            }
          }
        `}</style>

        <div className="student-dashboard">
          <div className="student-dashboard-shell">
            <div className="student-dashboard-top">
              <div className="student-dashboard-header">
                <div className="student-dashboard-brand">Student Page</div>
                <div className="student-dashboard-links">
                  <a href="#">Dashboard</a>
                  <a href="#">Academic</a>
                  <a href="#">Results</a>
                  <a href="#" className="student-dashboard-pill">Button</a>
                </div>
              </div>

              <div className="student-dashboard-hero">
                <div className="student-dashboard-profile">
                  <div className="student-dashboard-avatar">JA</div>
                  <div>
                    <p className="student-dashboard-name">John A. Okafor</p>
                    <p className="student-dashboard-meta">Student ID: EEE/2022/014 · 300 Level</p>
                  </div>
                </div>

                <div className="student-dashboard-actions">
                  <button type="button" className="student-dashboard-btn">Notifications</button>
                  <button type="button" className="student-dashboard-btn primary">View Results</button>
                </div>
              </div>
            </div>

            <div className="student-dashboard-content">
              <div className="student-dashboard-title">
                <h3>Student Overview</h3>
              </div>

              <div className="student-dashboard-card student-dashboard-overview">
                <div className="student-dashboard-grid">
                  <div className="student-dashboard-field">
                    <span>Student Name</span>
                    <strong>John A. Okafor</strong>
                  </div>
                  <div className="student-dashboard-field">
                    <span>Matriculation Number</span>
                    <strong>EEE/2022/014</strong>
                  </div>
                  <div className="student-dashboard-field">
                    <span>Level / Part</span>
                    <strong>300 / 2</strong>
                  </div>
                  <div className="student-dashboard-field">
                    <span>Department / Programme</span>
                    <strong>Electrical & Electronic Engineering</strong>
                  </div>
                  <div className="student-dashboard-field">
                    <span>Current Academic Session</span>
                    <strong>2026/2027</strong>
                  </div>
                  <div className="student-dashboard-field">
                    <span>Current Semester</span>
                    <strong>First Semester</strong>
                  </div>
                </div>
              </div>

              <div className="student-dashboard-card student-dashboard-status">
                <div className="student-dashboard-title" style={{ marginBottom: 0 }}>
                  <h3>Student Status</h3>
                </div>
                <div className="student-dashboard-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Course</th>
                        <th>Units</th>
                        <th>Grade</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>EEE 301</td>
                        <td>3</td>
                        <td className="positive">A</td>
                        <td className="positive">Pass</td>
                      </tr>
                      <tr>
                        <td>EEE 305</td>
                        <td>3</td>
                        <td className="positive">B</td>
                        <td className="positive">Pass</td>
                      </tr>
                      <tr>
                        <td>EEE 303</td>
                        <td>2</td>
                        <td className="muted">C</td>
                        <td className="muted">In review</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="student-dashboard-footer">© 2026 University Student Portal · Privacy · Terms</div>
            </div>
          </div>
        </div>
      </>
    );
  }

  const title = isHod ? "Department at a glance" : isAdviser ? "Welcome, Part Adviser" : "Welcome back, Dr. Adeyemi";
  const stats = isHod
    ? [["Students", "486", "Across all levels"], ["Staff", "32", "Department personnel"], ["Pending approvals", "8", "Requires review"]]
    : isAdviser
      ? [["Assigned cohort", "64", "300 level"], ["Pending registrations", "12", "Review requested"], ["Open requests", "4", "Awaiting follow-up"]]
      : [["Assigned courses", "4", "Current semester"], ["Students", "182", "Across your classes"], ["Pending tasks", "6", "Including result drafts"]];
  const announcements = [
    ["Course registration deadline", "Submit and review course selections by 18 October.", "Today"],
    ["Department seminar", "Seminar room 2, Friday at 2:00 PM.", "Yesterday"],
    ["Portal maintenance", "Scheduled maintenance this Sunday, 8:00–9:00 AM.", "2 days ago"],
  ];
  return (
    <>
      <PageHeading eyebrow={roles[role].title} title={title} description="A clear view of your academic activity, upcoming dates and items that need your attention." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {stats.map(([label, value, detail]) => <StatCard key={label} label={label} value={value} detail={detail} />)}
      </div>
      <div className="mt-6 grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Panel title={isStudent ? "Next steps" : "Needs your attention"} subtitle="Your most important pending items">
          <div className="space-y-3">
            {(isHod || isAdviser
              ? [["Review course registrations", "Several student submissions are awaiting review.", "approvals", "Open approval queue"], ["Check department activity", "Review current workloads and open requests.", "reports", "View activity"]]
              : [["Prepare result submissions", "Save a draft before the departmental deadline.", "results", "Manage results"], ["Check assigned classes", "Review enrolment and course resources.", "courses", "Open courses"]]
            ).map(([titleText, detail, section, action]) => (
              <div key={titleText} className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-black/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div><h3 className="font-semibold text-white">{titleText}</h3><p className="mt-1 text-sm text-slate-400">{detail}</p></div>
                <button onClick={() => navigateTo(section)} className={secondaryButton}>{action}</button>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Department announcements" subtitle="Updates relevant to your role">
          <ul className="space-y-4">
            {announcements.map(([titleText, detail, date]) => (
              <li key={titleText} className="border-l-2 border-blue-500 pl-4">
                <div className="flex justify-between gap-3"><h3 className="text-sm font-semibold text-white">{titleText}</h3><span className="shrink-0 text-xs text-slate-500">{date}</span></div>
                <p className="mt-1 text-sm leading-5 text-slate-400">{detail}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}

function PortalContent({ role, section, notify }) {
  const [selectedCourses, setSelectedCourses] = useState(["EEE 301", "EEE 303", "EEE 305", "EEE 307"]);
  const [decisions, setDecisions] = useState({});
  const [search, setSearch] = useState("");
  const [semester, setSemester] = useState("First semester");

  const filteredStudents = useMemo(
    () => students.filter((student) => `${student.name} ${student.matric}`.toLowerCase().includes(search.toLowerCase())),
    [search],
  );

  if (section === "dashboard") return <Dashboard role={role} navigateTo={notify} />;

  if (section === "profile") {
    return (
      <>
        <PageHeading eyebrow="Account" title="My profile" description="Review your department, contact and academic or staff details." />
        <Panel title="Personal information" subtitle="Required fields are marked. Profile changes in this prototype are not saved.">
          <form onSubmit={(event) => { event.preventDefault(); toast.info("Demo only: profile changes are not saved.", { position: "top-center" }); }} className="grid gap-5 md:grid-cols-2">
            {[["Full name", role === "student" ? "Olumide Adebayo" : "Dr. K. Adeyemi"], ["Email address", role === "student" ? "olumide@example.edu" : "k.adeyemi@example.edu"], ["Phone number", "+234 800 000 0000"], ["Department", "Electrical and Electronic Engineering"], [role === "student" ? "Matric number" : "Designation", role === "student" ? "EEE/2022/014" : roles[role].title], [role === "student" ? "Level / Part" : "Office", role === "student" ? "300 Level" : "Engineering Building"]].map(([label, value]) => (
              <label key={label} className="text-sm font-medium text-slate-300">{label}<input className={`${fieldClass} mt-2`} defaultValue={value} required /></label>
            ))}
            <div className="md:col-span-2"><button className={primaryButton}>Save profile</button></div>
          </form>
        </Panel>
      </>
    );
  }

  if (section === "courses" && role === "student") {
    const units = courses.filter((course) => selectedCourses.includes(course.code)).reduce((sum, course) => sum + course.units, 0);
    return (
      <>
        <PageHeading eyebrow="Academics" title="Course registration" description="Select your compulsory and elective courses for the current session. Confirm your total credit load before submitting." action={<Status>Draft</Status>} />
        <div className="mb-5 flex flex-wrap gap-3">
          <label className="text-sm text-slate-300">Session<select className={`${fieldClass} mt-1 min-w-44`}><option>2026/2027</option><option>2025/2026</option></select></label>
          <label className="text-sm text-slate-300">Semester<select className={`${fieldClass} mt-1 min-w-44`}><option>First semester</option><option>Second semester</option></select></label>
        </div>
        <Panel title="Available courses" subtitle="Compulsory courses are preselected; you may change your elective selection.">
          <div className="space-y-3">
            {courses.map((course) => (
              <label key={course.code} className="flex cursor-pointer items-center gap-4 rounded-xl border border-slate-800 p-4 hover:border-blue-500/60">
                <input className="size-4 accent-blue-500" type="checkbox" checked={selectedCourses.includes(course.code)} onChange={() => setSelectedCourses((current) => current.includes(course.code) ? current.filter((code) => code !== course.code) : [...current, course.code])} />
                <span className="min-w-0 flex-1"><span className="block font-semibold text-white">{course.code} · {course.title}</span><span className="mt-1 block text-xs text-slate-400">{course.type}</span></span>
                <span className="text-sm text-slate-300">{course.units} units</span>
              </label>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-slate-800 pt-5">
            <p className="text-sm text-slate-300">Selected credit load: <strong className="text-white">{units} units</strong></p>
            <button className={primaryButton} onClick={() => toast.info("Demo only: registration is not submitted to an adviser.", { position: "top-center" })}>Submit for adviser review</button>
          </div>
        </Panel>
      </>
    );
  }

  if (section === "results" && role === "student") {
    return (
      <>
        <PageHeading eyebrow="Academics" title="Results & progress" description="View published grades, current GPA and outstanding courses. Unpublished results are not displayed." />
        <div className="mb-5 flex flex-wrap gap-3">
          <label className="text-sm text-slate-300">Session<select className={`${fieldClass} mt-1 min-w-44`}><option>2025/2026</option><option>2024/2025</option></select></label>
          <label className="text-sm text-slate-300">Semester<select value={semester} onChange={(event) => setSemester(event.target.value)} className={`${fieldClass} mt-1 min-w-44`}><option>First semester</option><option>Second semester</option></select></label>
        </div>
        <div className="mb-5 grid gap-4 sm:grid-cols-3"><StatCard label="Semester GPA" value="4.12" detail="2025/2026 · First semester" /><StatCard label="CGPA" value="3.87" detail="Cumulative average" /><StatCard label="Outstanding courses" value="2" detail="Speak with your part adviser" /></div>
        <Panel title={`${semester} grades`}><DataTable headers={["Course", "Title", "Units", "Grade", "Status"]} rows={[[ "EEE 201", "Circuit Theory I", "3", "A", <Status key="a">Approved</Status> ], ["EEE 203", "Electronics I", "3", "B", <Status key="b">Approved</Status>], ["EEE 205", "Engineering Mathematics", "2", "C", <Status key="c">Approved</Status>]]} /></Panel>
      </>
    );
  }

  if (section === "timetable") {
    return <><PageHeading eyebrow="Schedule" title="Timetable" description="Review teaching, lecture and examination activities. Check announcements for schedule changes." /><div className="mb-5 flex gap-3"><select className={`${fieldClass} max-w-56`}><option>2026/2027 · First semester</option><option>2026/2027 · Second semester</option></select></div><Panel title="Weekly schedule" subtitle="Monday – Friday"><DataTable headers={["Day", "Time", "Course / activity", "Venue"]} rows={[[ "Monday", "09:00–11:00", "EEE 301 · Electrical Machines I", "Engineering Lecture Theatre" ], ["Tuesday", "11:00–13:00", "EEE 303 · Electromagnetic Fields", "Room E204" ], ["Wednesday", "14:00–16:00", "EEE 305 · Digital Systems Lab", "Power Systems Laboratory" ], ["Thursday", "09:00–11:00", "EEE 307 · Control Engineering", "Room E103" ], ["Friday", "12:00–13:00", "Advising / office hours", "Department Office" ]]}/></Panel></>;
  }

  if (section === "resources") {
    return <><PageHeading eyebrow="Study materials" title="Learning resources" description="Materials are grouped by course. Download permissions depend on your course enrolment." /><Panel title="Available course materials"><DataTable headers={["Course", "Resource", "Updated", "Action"]} rows={[[ "EEE 301", "Lecture notes · Week 1–4", "12 Sep 2026", <button key="d1" className={secondaryButton} onClick={() => toast.info("Demo resource: connect file storage to enable downloads.")}>Preview / download</button> ], [ "EEE 303", "Problem set 1", "10 Sep 2026", <button key="d2" className={secondaryButton} onClick={() => toast.info("Demo resource: connect file storage to enable downloads.")}>Preview / download</button> ], [ "EEE 305", "Laboratory safety guide", "08 Sep 2026", <button key="d3" className={secondaryButton} onClick={() => toast.info("Demo resource: connect file storage to enable downloads.")}>Preview / download</button> ]]}/></Panel></>;
  }

  if (section === "requests" || section === "escalations") {
    return <><PageHeading eyebrow="Support" title={section === "requests" ? "Requests & complaints" : "Escalations"} description="Submit a request, attach supporting documents, and follow its review status."/><div className="grid gap-5 xl:grid-cols-2"><DemoForm title="New request" description="Provide enough detail for the department to assist you." fields={["Request type", "Details"]} submitLabel="Submit request"/><Panel title="Your recent cases"><DataTable headers={["Reference", "Category", "Submitted", "Status"]} rows={[[ "REQ-2026-014", "Course registration", "14 Sep 2026", <Status key="s1">Pending review</Status> ], [ "REQ-2026-009", "Academic record", "02 Sep 2026", <Status key="s2">Approved</Status> ]]}/></Panel></div></>;
  }

  if (section === "adviser") {
    return <><PageHeading eyebrow="Student support" title="Your part adviser" description="Contact your assigned adviser or request an appointment."/><Panel title="Assigned adviser"><div className="grid gap-5 sm:grid-cols-2"><div><p className="text-2xl font-bold text-white">Dr. K. Adeyemi</p><p className="mt-1 text-sm text-blue-200">300 Level · Part Adviser</p><p className="mt-4 text-sm text-slate-400">k.adeyemi@example.edu<br/>Engineering Building, Room 12</p></div><button className={`${primaryButton} self-start`} onClick={() => toast.info("Demo only: appointment requests are not sent.")}>Request an appointment</button></div></Panel></>;
  }

  if (section === "notifications") {
    return <><PageHeading eyebrow="Updates" title="Notifications" description="Registration decisions, new materials, announcements and reminders."/><Panel title="Recent notifications"><ul className="divide-y divide-slate-800">{[["Registration closes soon", "Course registration closes on 18 October.", "Today · Reminder"], ["New learning resource", "EEE 301 lecture notes for weeks 1–4 are available.", "Yesterday · Resource"], ["Department seminar", "Seminar room 2, Friday at 2:00 PM.", "12 Sep · Announcement"]].map(([title, detail, meta]) => <li key={title} className="flex gap-4 py-4"><span className="mt-1 size-2 shrink-0 rounded-full bg-blue-400"/><div><p className="font-semibold text-white">{title}</p><p className="mt-1 text-sm text-slate-400">{detail}</p><p className="mt-2 text-xs text-slate-500">{meta}</p></div></li>)}</ul></Panel></>;
  }

  if (section === "students" || section === "academic-summary") {
    return <><PageHeading eyebrow={role === "adviser" ? "Advising" : "Records"} title={section === "academic-summary" ? "Student academic summaries" : "Student records"} description="Search authorised cohort records and review academic activity."/><Panel title={role === "adviser" ? "Assigned 300-level cohort" : "Department students"} subtitle="Access is restricted to records permitted for your role."><label className="mb-4 block max-w-md text-sm text-slate-300">Search by student name or matric number<input className={`${fieldClass} mt-2`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="e.g. EEE/2022/014"/></label><DataTable headers={["Student", "Matric number", "Level", "Registration"]} rows={filteredStudents.map((student) => [student.name, student.matric, student.level, <Status key={student.matric}>{student.status}</Status>])}/>{filteredStudents.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No matching students found.</p>}</Panel></>;
  }

  if (section === "courses" && role !== "student") {
    return <><PageHeading eyebrow={role === "hod" ? "Curriculum" : "Teaching"} title={role === "hod" ? "Course oversight" : "Course management"} description={role === "hod" ? "Review course coverage and departmental curriculum." : "Manage assigned courses, enrolment lists and learning materials."} action={<button className={primaryButton} onClick={() => toast.info("Demo only: course changes are not saved.")}>{role === "hod" ? "Review curriculum" : "Upload resource"}</button>}/><Panel title="Current session courses"><DataTable headers={["Course", "Title", "Units", "Lecturer", "Enrolment"]} rows={courses.map((course, index) => [course.code, course.title, String(course.units), ["Dr. K. Adeyemi", "Prof. O. Akin", "Dr. M. Bello"][index % 3], String(38 + index * 5)])}/></Panel></>;
  }

  if (section === "results" && role !== "student") {
    return <><PageHeading eyebrow="Assessment" title="Results management" description="Enter or validate scores, save a draft, then submit through the departmental approval workflow."/><Panel title="EEE 301 · Electrical Machines I" subtitle="2026/2027 · First semester · Draft"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-400">Upload a CSV to validate scores, or edit student scores below.</p><label className={secondaryButton}>Upload score sheet<input type="file" accept=".csv" className="sr-only" onChange={() => toast.info("Demo only: score uploads are not processed.")}/></label></div><DataTable headers={["Student", "Matric number", "CA / 40", "Exam / 60", "Total"]} rows={students.map((student, index) => [student.name, student.matric, <input key={`ca${index}`} className="w-20 rounded border border-slate-700 bg-black px-2 py-1" type="number" min="0" max="40" defaultValue={32 - index * 3}/>, <input key={`exam${index}`} className="w-20 rounded border border-slate-700 bg-black px-2 py-1" type="number" min="0" max="60" defaultValue={48 - index * 4}/>, `${80 - index * 7}%`])}/><div className="mt-5 flex flex-wrap gap-3"><button className={secondaryButton} onClick={() => toast.info("Demo only: draft scores are not saved.")}>Save draft</button><button className={primaryButton} onClick={() => toast.info("Demo only: results are not sent for approval.")}>Submit for approval</button></div></Panel></>;
  }

  if (section === "approvals") {
    return <><PageHeading eyebrow="Workflow" title={role === "adviser" ? "Registration review" : "Approval queue"} description="Review submissions, add comments, and approve or return items for correction."/><Panel title="Items awaiting your decision" subtitle="Actions are local demo state only and do not notify students or update records."><div className="space-y-4">{students.map((student) => <article key={student.matric} className="rounded-xl border border-slate-800 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-white">{student.name} · {student.matric}</h3><p className="mt-1 text-sm text-slate-400">300 Level · 2026/2027 first semester · 13 units selected</p></div><Status>{decisions[student.matric] || student.status}</Status></div><label className="mt-4 block text-xs text-slate-400">Reviewer comment<input className={`${fieldClass} mt-2`} placeholder="Add a note for the student"/></label><div className="mt-3 flex flex-wrap gap-2"><button className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600" onClick={() => setDecisions({ ...decisions, [student.matric]: "Approved" })}>Approve</button><button className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600" onClick={() => setDecisions({ ...decisions, [student.matric]: "Returned" })}>Return for correction</button><button className={secondaryButton} onClick={() => toast.info("Demo record: details are illustrative only.")}>View details</button></div></article>)}</div></Panel></>;
  }

  if (section === "assignments") {
    return <><PageHeading eyebrow="Department administration" title="Staff assignments" description="Review course lecturer and part adviser assignments for this academic session." action={<button className={primaryButton} onClick={() => toast.info("Demo only: staff assignments are not saved.")}>Assign staff</button>}/><Panel title="Current assignments"><DataTable headers={["Staff member", "Role", "Course / cohort", "Session"]} rows={[[ "Dr. K. Adeyemi", "Lecturer", "EEE 301, EEE 307", "2026/2027" ], ["Dr. K. Adeyemi", "Part Adviser", "300 Level", "2026/2027" ], ["Prof. O. Akin", "Lecturer", "EEE 303, EEE 305", "2026/2027" ]]}/></Panel></>;
  }

  if (section === "communication") {
    return <><PageHeading eyebrow="Communication" title={role === "hod" ? "Department announcements" : "Communication"} description="Compose an announcement and select the intended audience."/><div className="grid gap-5 xl:grid-cols-2"><DemoForm title="Compose announcement" description="Messages will be visible to the selected audience in a connected system." fields={["Announcement title", "Message"]} submitLabel="Save announcement"/><Panel title="Audience"><div className="space-y-3">{["All department students", "My assigned courses", "300 Level cohort", "Teaching staff", "Selected individuals"].map((audience) => <label key={audience} className="flex items-center gap-3 rounded-xl border border-slate-800 p-3 text-sm text-slate-300"><input type="checkbox" className="size-4 accent-blue-500"/>{audience}</label>)}</div><p className="mt-4 text-xs text-slate-500">Select a specific audience before sending. Demo mode does not send messages.</p></Panel></div></>;
  }

  if (section === "reports") {
    return <><PageHeading eyebrow="Analytics" title="Department reports" description="Filter academic summaries by session, semester, level and course."/><Panel title="Report filters"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[["Session", "2026/2027"], ["Semester", "First semester"], ["Level", "All levels"], ["Course", "All courses"]].map(([label, value]) => <label key={label} className="text-sm text-slate-300">{label}<select className={`${fieldClass} mt-2`}><option>{value}</option><option>2025/2026</option></select></label>)}</div><div className="mt-5 flex gap-3"><button className={primaryButton} onClick={() => toast.info("Demo report only: connect the reporting service for live data.")}>Generate report</button><button className={secondaryButton} onClick={() => toast.info("Demo only: there is no report file to export.")}>Export CSV</button></div></Panel><div className="mt-5 grid gap-4 sm:grid-cols-3"><StatCard label="Registration completion" value="86%" detail="Illustrative demo data"/><StatCard label="Courses covered" value="28 / 32" detail="Illustrative demo data"/><StatCard label="Results awaiting approval" value="8" detail="Illustrative demo data"/></div></>;
  }

  if (section === "history") {
    return <><PageHeading eyebrow="Audit trail" title="Decision history" description="Review who submitted, reviewed or approved an item and when."/><Panel title="Recent decisions"><DataTable headers={["Item", "Action", "Actor", "Date / time"]} rows={[[ "EEE 201 results", "Approved", "Prof. O. Akin · HOD", "14 Sep 2026, 11:32" ], [ "EEE/2022/009 registration", "Returned for correction", "Dr. K. Adeyemi · Adviser", "13 Sep 2026, 15:06" ], [ "EEE 301 results", "Submitted", "Dr. K. Adeyemi · Lecturer", "12 Sep 2026, 09:21" ]]}/></Panel></>;
  }

  if (section === "records") {
    return <><PageHeading eyebrow="Advising" title="Advising records" description="Record guidance and follow-up actions. Keep notes relevant and visible only to authorised roles."/><div className="grid gap-5 xl:grid-cols-2"><Panel title="Recent advising notes"><DataTable headers={["Student", "Note", "Follow-up", "Visibility"]} rows={[[ "EEE/2022/014", "Discussed outstanding courses", "Review next advising session", "Adviser / HOD" ], [ "EEE/2022/027", "Registration selection reviewed", "Await student update", "Adviser / HOD" ]]}/></Panel><DemoForm title="Record guidance" description="Use factual, concise notes and set follow-up expectations." fields={["Student matric number", "Details"]} submitLabel="Save advising note"/></div></>;
  }

  return <><PageHeading eyebrow="Department portal" title="Page not available" description="This area may not be part of your role or has not been configured."/><Panel title="Check your access"><p className="text-sm text-slate-400">Choose another page from the navigation, or go to your dashboard.</p><Link className={`${primaryButton} mt-4 inline-flex`} to={`/portal/${role}/dashboard`}>Return to dashboard</Link></Panel></>;
}

export default function Portal() {
  const { role: requestedRole = "student", section: requestedSection = "dashboard" } = useParams();
  const navigate = useNavigate();
  const role = Object.hasOwn(roles, requestedRole) ? requestedRole : "student";
  const menu = navigation[role];
  const section = menu.some(([key]) => key === requestedSection) ? requestedSection : "dashboard";
  const currentLabel = menu.find(([key]) => key === section)?.[1] || "Dashboard";

  const changeRole = (event) => navigate(`/portal/${event.target.value}/dashboard`);
  const navigateTo = (targetSection) => navigate(`/portal/${role}/${targetSection}`);
  const logout = () => {
    toast.info("Demo portal: no authenticated session is active.", { position: "top-center" });
    navigate("/");
  };

  return (
    <main className="min-h-screen bg-[#080b12] px-4 py-8 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-7 flex flex-col gap-4 rounded-2xl border border-blue-400/20 bg-gradient-to-r from-blue-950/80 via-slate-950 to-black p-5 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-300">EEE OAU · Academic portal</p><h2 className="mt-2 text-xl font-bold">{roles[role].title}</h2><p className="mt-1 text-sm text-slate-400">{roles[role].welcome} · Demo data</p></div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="role-switcher">Switch portal role</label>
            <select id="role-switcher" value={role} onChange={changeRole} className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-white focus:border-blue-400 focus:outline-none">
              {Object.entries(roles).map(([value, item]) => <option key={value} value={value}>{item.title}</option>)}
            </select>
            <Link to="/session-expired" className={secondaryButton}>Session help</Link>
            <button className={secondaryButton} onClick={logout}>Log out</button>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside className={`${className} h-fit p-3`} aria-label="Portal navigation">
            <p className="px-3 pb-3 pt-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Workspace</p>
            <nav className="flex gap-2 overflow-x-auto lg:flex-col">
              {menu.map(([key, label]) => (
                <Link key={key} to={`/portal/${role}/${key}`} aria-current={section === key ? "page" : undefined} className={`shrink-0 rounded-xl px-3 py-2.5 text-sm transition lg:shrink ${section === key ? "bg-blue-600 font-semibold text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`}>
                  {label}
                </Link>
              ))}
            </nav>
            <div className="mt-4 border-t border-slate-800 px-3 pt-4">
              <p className="text-xs leading-5 text-slate-500">Need help accessing a page?</p>
              <Link to="/access-denied" className="mt-2 inline-block text-xs font-semibold text-blue-300 hover:text-blue-200">Access and privacy help</Link>
            </div>
          </aside>

          <div className="min-w-0">
            <div className="mb-4 flex items-center gap-2 text-xs text-slate-500"><span>Workspace</span><span aria-hidden="true">/</span><span className="text-slate-300">{currentLabel}</span></div>
            <PortalContent role={role} section={section} notify={navigateTo}/>
            <p className="mt-6 text-center text-xs text-slate-600">Prototype only. This screen uses illustrative data; changes are not persisted or sent to staff.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
