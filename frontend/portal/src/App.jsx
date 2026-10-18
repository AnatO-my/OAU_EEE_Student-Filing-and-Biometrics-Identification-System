import { lazy, Suspense } from "react";
import { BrowserRouter as Router, Navigate, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AppLayout from "./Applayout";
import { ToastContainer } from "react-toastify";
import Register from "./pages/Register";
import PortalNotice from "./pages/PortalNotice";
import InformationPage from "./pages/InformationPage";
import Admindashboard from "./pages/Admindashboard";
import Studentprofile from "./pages/Studentprofile";
import AttendanceDashboard from "./pages/AttendanceDashboard";
import { AuthProvider } from "./auth/AuthContext";

const Portal = lazy(() => import("./pages/Portal"));

function App() {
  return (
    <>
      <Router>
        <AuthProvider>
          <Suspense fallback={<main className="flex min-h-[60vh] items-center justify-center bg-[#080b12] text-sm text-blue-200" role="status">Loading portal...</main>}>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<Landing />} />
                <Route path="admin" element={<Admindashboard />} />
                <Route path="attendance" element={<AttendanceDashboard />} />
                <Route path="student" element={<Studentprofile />} />
                <Route path="student/profile" element={<Navigate to="/portal/student/profile" replace />} />
                <Route path="portal/:role/:section?" element={<Portal />} />
                <Route path="login" element={<Login />} />
                <Route path="register" element={<Register />} />
                <Route path="recover-password" element={<PortalNotice />} />
                <Route path="session-expired" element={<PortalNotice />} />
                <Route path="access-denied" element={<PortalNotice />} />
                <Route path="help" element={<InformationPage />} />
                <Route path="privacy" element={<InformationPage />} />
                <Route path="about" element={<InformationPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
        <ToastContainer />
      </Router>
    </>
  );
}

export default App;
