import { Link } from "react-router-dom";

const Navbar = () => {
  return (
    <nav
      aria-label="Main navigation"
      className="flex flex-wrap items-center justify-center gap-1 rounded-2xl py-1 backdrop-blur-sm sm:gap-2"
    >
      <Link
        className="rounded-full px-3 py-2 text-xs font-semibold transition hover:bg-blue-500 hover:shadow-lg sm:px-4 sm:text-sm"
        to="/help"
      >
        Help
      </Link>
      <Link
        className="rounded-full px-3 py-2 text-xs font-semibold transition hover:bg-blue-500 hover:shadow-2xl sm:px-4 sm:text-sm"
        to="/privacy"
      >
        Privacy
      </Link>
      <Link
        className="rounded-full px-3 py-2 text-xs font-semibold transition hover:bg-blue-500 hover:shadow-2xl sm:px-4 sm:text-sm"
        to="/about"
      >
        About
      </Link>
      <Link
        className="rounded-full px-3 py-2 text-xs font-semibold transition hover:bg-blue-500 hover:shadow-2xl sm:px-4 sm:text-sm"
        to="/attendance"
      >
        Attendance
      </Link>
    </nav>
  );
};

export default Navbar;
