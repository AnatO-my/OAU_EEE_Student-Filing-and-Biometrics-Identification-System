import { Link } from "react-router-dom";
import Sectionheader from "../components/Sectionheader";
import studentImage from "../assets/fast1193.webp";

export default function Register() {
  return (
    <main className="bg-white text-slate-950">
      <section
        className="relative flex min-h-72 items-center justify-center bg-cover bg-center px-5 py-12 text-center text-white sm:min-h-80"
        style={{
          backgroundImage: `linear-gradient(90deg, rgb(5 13 18 / 82%), rgb(5 13 18 / 68%)), url("${studentImage}")`,
        }}
      >
        <div className="relative z-10 max-w-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-200">
            EEE OAU · Academic portal
          </p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
            Request portal access
          </h1>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-200">
            Portal accounts are issued by the department. Self-service
            registration is not available.
          </p>
          <Link
            to="/login"
            className="mt-5 inline-flex rounded-md bg-blue-700 px-5 py-2 text-xs font-semibold text-white transition hover:bg-blue-600"
          >
            Return to sign in
          </Link>
        </div>
      </section>

      <section className="px-5 py-9 sm:px-8 sm:py-12">
        <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-slate-50 p-6 sm:p-9">
          <Sectionheader title="How to get an account" level={3} centered accent />
          <p className="mt-4 text-center text-sm leading-6 text-slate-600">
            Contact your departmental administrator with your institutional
            details. Once your account has been created, sign in with the
            username and temporary or assigned password provided to you.
          </p>
          <p className="mt-4 text-center text-xs leading-5 text-slate-500">
            For security, do not send passwords through email or include them
            in support requests.
          </p>
        </div>
      </section>
    </main>
  );
}
