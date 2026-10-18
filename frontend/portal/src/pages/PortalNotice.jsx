import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { toast } from "react-toastify";
import Sectionheader from "../components/Sectionheader";
import { requestPasswordReset } from "../api";

const notices = {
  "/session-expired": {
    title: "Your session has expired",
    message: "For your security, sign in again to continue.",
    action: "Sign in",
    href: "/login",
  },
  "/access-denied": {
    title: "Access is restricted",
    message: "You may not have permission to view this area. Contact your department administrator if you believe this is an error.",
    action: "Return to portal",
    href: "/portal/student/dashboard",
  },
};

export default function PortalNotice() {
  const { pathname } = useLocation();
  const notice = notices[pathname];
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (notice) {
    return (
      <main className="flex min-h-[65vh] items-center justify-center bg-[#080b12] px-4 py-12 text-white">
        <section className="w-full max-w-lg rounded-2xl border border-blue-400/20 bg-slate-950 p-8 text-center shadow-xl shadow-blue-950/30">
          <Sectionheader
            eyebrow="EEE OAU portal"
            title={notice.title}
            level={1}
            centered
          />
          <p className="mt-4 text-sm leading-6 text-slate-400">{notice.message}</p>
          <Link to={notice.href} className="mt-7 inline-flex rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-500">{notice.action}</Link>
        </section>
      </main>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email.trim());
      setEmail("");
      toast.info(
        "If the address is eligible, password reset instructions will be sent.",
        { position: "top-center" },
      );
    } catch (error) {
      toast.error(error.message || "Unable to request a password reset.", {
        position: "top-center",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-[65vh] items-center justify-center bg-[#080b12] px-4 py-12 text-white">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-blue-400/20 bg-slate-950 p-8 shadow-xl shadow-blue-950/30">
        <Sectionheader eyebrow="Account support" title="Reset your password" level={1} />
        <p className="mt-3 text-sm leading-6 text-slate-400">Enter your institutional email to request a password reset link.</p>
        <label className="mt-6 block text-sm font-medium text-slate-300" htmlFor="recovery-email">Institutional email
          <input id="recovery-email" name="email" className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="name@example.edu"/>
        </label>
        <button disabled={isSubmitting} className="mt-5 w-full rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-wait disabled:opacity-60">{isSubmitting ? "Sending request..." : "Request reset link"}</button>
        <Link to="/login" className="mt-5 block text-center text-sm font-semibold text-blue-300 hover:text-blue-200">Back to login</Link>
        <p className="mt-5 text-center text-xs text-slate-600">For privacy, the response will not confirm whether an account uses this email address.</p>
      </form>
    </main>
  );
}
