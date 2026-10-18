import { Link, useLocation } from "react-router-dom";

export default function Footer() {
  const { pathname } = useLocation();

  if (pathname === "/register") {
    return (
      <footer className="border-t border-slate-100 bg-white px-5 py-6 text-slate-700">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-x-7 gap-y-3 text-xs">
          <span>© {new Date().getFullYear()} EEE OAU</span>
          <Link to="/privacy" className="hover:text-blue-700">Privacy Policy</Link>
          <Link to="/about" className="hover:text-blue-700">Terms of Service</Link>
          <Link to="/help" className="hover:text-blue-700">Contact Support</Link>
        </div>
      </footer>
    );
  }

  return (
    <footer className="border-t border-blue-950 bg-[#080b12] px-6 py-8 text-slate-400">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-white">EEE OAU · Academic Portal</p>
          <p className="mt-1 text-xs">Department of Electronic and Electrical Engineering</p>
        </div>
        <nav aria-label="Footer navigation" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <Link to="/help" className="transition hover:text-blue-300">Help</Link>
          <Link to="/privacy" className="transition hover:text-blue-300">Privacy</Link>
          <Link to="/about" className="transition hover:text-blue-300">About</Link>
          <Link to="/access-denied" className="transition hover:text-blue-300">Access support</Link>
        </nav>
      </div>
      <p className="mx-auto mt-5 max-w-7xl text-xs text-slate-600">Prototype interface. Academic records and actions shown are illustrative.</p>
    </footer>
  );
}
