import { Link, useLocation } from "react-router-dom";
import Sectionheader from "../components/Sectionheader";

const content = {
  "/help": {
    label: "Portal help",
    title: "How can we help?",
    intro: "Choose the correct role workspace and use its navigation to reach academic records, registration, course tools or departmental approvals.",
    sections: [
      ["Sign-in and access", "Use your institutional account. If you cannot access a page, contact the department administrator to verify your role and permissions."],
      ["Student registration", "Select courses, confirm the displayed credit load, and submit your registration for adviser review. Returned registrations should include a reviewer comment."],
      ["Staff and approvals", "Lecturers manage assigned courses and result drafts. Part advisers review their assigned cohort. HOD users manage departmental assignments and approvals."],
    ],
  },
  "/privacy": {
    label: "Privacy",
    title: "Your information and privacy",
    intro: "Sign-in and password-reset requests use the departmental API. Most portal screens still show illustrative records and do not yet load or save academic data.",
    sections: [
      ["Use of personal information", "A production portal should only collect information required for academic administration and should restrict access by role."],
      ["Academic records", "Student records, advising notes and results should only be available to authorised users and should be protected by server-side access controls."],
      ["Prototype warning", "Use an institutional account only when the approved API is configured. Academic workflows, file storage and audit logging still require implementation and production review."],
    ],
  },
  "/about": {
    label: "About the portal",
    title: "EEE OAU academic portal",
    intro: "A departmental workspace concept for coordinating student academic services and authorised staff workflows.",
    sections: [
      ["For students", "Review profile information, course registration, published results, schedules, resources, requests and announcements."],
      ["For department staff", "Support course and result management, student communication, advising, departmental oversight and approval workflows."],
      ["Designed as a prototype", "The current screens use illustrative content. A secure backend and department-approved requirements are needed before real academic work can be performed."],
    ],
  },
};

export default function InformationPage() {
  const { pathname } = useLocation();
  const page = content[pathname] || content["/help"];

  return (
    <main className="min-h-[65vh] bg-[#080b12] px-4 py-12 text-white sm:px-6">
      <div className="mx-auto max-w-4xl">
        <Sectionheader eyebrow={page.label} title={page.title} level={1} />
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-400">{page.intro}</p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {page.sections.map(([title, description]) => (
            <section key={title} className="rounded-2xl border border-blue-400/20 bg-slate-950 p-5">
              <h2 className="font-bold text-white">{title}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">{description}</p>
            </section>
          ))}
        </div>
        <Link to="/login" className="mt-8 inline-flex rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-500">Go to login</Link>
      </div>
    </main>
  );
}
