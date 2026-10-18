import {Link} from "react-router-dom";
import Sectionheader from "./Sectionheader";
import studentImage from "../assets/fast1193.webp";

const SignupCard = () => {
  return (
    <section className="bg-white px-5 py-12 sm:px-8 sm:py-16">
      <div
        className="relative mx-auto flex min-h-72 max-w-6xl items-center justify-center overflow-hidden rounded-2xl bg-cover bg-center px-6 py-10 text-center text-white shadow-xl sm:min-h-80"
        style={{
          backgroundImage: `linear-gradient(90deg, rgb(5 13 18 / 82%), rgb(5 13 18 / 68%)), url("${studentImage}")`,
        }}
      >
        <div className="relative z-10 max-w-xl">
          <Sectionheader eyebrow="Access Portal" title="Create your account" centered />
          <p className="mt-4 text-sm leading-6 text-slate-200">
            Join the Electrical and Electronic Engineering portal to manage
            your academic journey.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              to="/login"
              className="rounded-md border border-white/50 bg-black/20 px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-white/15"
            >
              Already have an account? Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-md bg-blue-700 px-6 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-600"
            >
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};

export default SignupCard;