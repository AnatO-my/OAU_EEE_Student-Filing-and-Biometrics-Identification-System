import { lazy, Suspense } from "react";
import { BrowserRouter as Router, Navigate, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AppLayout from "./Applayout";
import { ToastContainer } from "react-toastify";
import Register from "./pages/Register";
import PortalNotice from "./pages/PortalNotice";
import InformationPage from "./pages/InformationPage";
import { AuthProvider } from "./auth/AuthContext";
import ResetPassword from './pages/ResetPassword';
import SetupStudent from './pages/SetupStudent';
import { useAuth } from './auth/useAuth';

const Portal = lazy(() => import("./live/LivePortal"));

function PortalRedirect({ section = 'dashboard' }) {
  const { user, status } = useAuth();
  if (status === 'loading') return <p role="status">Checking your session…</p>;
  return <Navigate to={user ? `/portal/${user.role}/${section}` : '/login'} replace />;
}

function App() {
  return (
    <>
      <Router>
        <AuthProvider>
          <Suspense fallback={<main className="flex min-h-[60vh] items-center justify-center bg-[#080b12] text-sm text-blue-200" role="status">Loading portal...</main>}>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<Landing />} />
                <Route path="attendance" element={<PortalRedirect section="attendance" />} />
                <Route path="portal" element={<PortalRedirect />} />
                <Route path="guardian-results" element={<PortalRedirect section="guardian-results" />} />
                <Route path="student" element={<PortalRedirect />} />
                <Route path="student/profile" element={<PortalRedirect section="profile" />} />
                <Route path="portal/:role/:section?" element={<Portal />} />
                <Route path="login" element={<Login />} />
                <Route path="register" element={<Register />} />
                <Route path="recover-password" element={<PortalNotice />} />
                <Route path="reset-password" element={<ResetPassword />} />
                <Route path="setup-student" element={<SetupStudent />} />
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
