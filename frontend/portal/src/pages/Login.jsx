import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import Sectionheader from "../components/Sectionheader";
import { useAuth } from "../auth/useAuth";

const Login = () => {
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loginForm = async (event) => {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const identity = await signIn(username.trim(), password);
      setPassword("");
      toast.success("Signed in successfully.", { position: "top-center" });
      navigate(`/portal/${identity.role}/dashboard`);
    } catch (error) {
      const retryAfter = error.retryAfter
        ? ` The server asked you to wait: ${error.retryAfter}.`
        : "";
      toast.error(`${error.message || "Unable to sign in."}${retryAfter}`, {
        position: "top-center",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <style>{`
        .login-page {
          min-height: 100vh;
          background: #121212;
          font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
          color: #0b1f38;
        }

        .login-shell {
          width: min(100%, 980px);
          max-width: 980px;
          margin: 0 auto;
          padding: 18px 18px 32px;
        }

        .login-topbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 8px 18px;
          color: #f4f7ff;
        }

        .login-brand {
          font-size: 1.15rem;
          font-weight: 700;
          letter-spacing: 0.02em;
          color: #f2f6ff;
          text-decoration: none;
        }

        .login-links {
          display: flex;
          align-items: center;
          gap: 24px;
          font-size: 0.82rem;
          color: rgba(255, 255, 255, 0.8);
        }

        .login-links a {
          color: inherit;
          text-decoration: none;
        }

        .login-links .link-pill {
          padding: 8px 14px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.18);
        }

        .welcome-panel {
          background: linear-gradient(180deg, #0f3f89 0%, #0e3d8b 100%);
          border-radius: 16px 16px 0 0;
          padding: 12px 18px 18px;
          box-shadow: 0 12px 40px rgba(7, 27, 76, 0.38);
        }

        .welcome-inner {
          max-width: 320px;
          margin: 0 auto;
          text-align: center;
        }

        .welcome-inner h1 {
          margin: 8px 0 0;
          font-size: clamp(1.7rem, 3vw, 2.2rem);
          line-height: 1.2;
          font-weight: 700;
          color: #f4f7ff;
        }

        .welcome-inner p {
          margin: 8px 0 0;
          font-size: 0.76rem;
          color: rgba(255, 255, 255, 0.84);
        }

        .hero-form {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-top: 18px;
        }

        .hero-form .field {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 8px;
        }

        .hero-form label {
          font-size: 0.73rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.74);
        }

        .hero-form input {
          width: 100%;
          padding: 12px 12px;
          border: 1px solid rgba(255, 255, 255, 0.26);
          border-radius: 8px;
          outline: none;
          background: rgba(255, 255, 255, 0.08);
          color: #ffffff;
          font-size: 0.87rem;
          box-sizing: border-box;
        }

        .hero-form input::placeholder {
          color: rgba(255, 255, 255, 0.5);
        }

        .hero-form input:focus {
          border-color: rgba(255, 255, 255, 0.74);
          box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1);
        }

        .hero-actions {
          display: flex;
          justify-content: center;
          gap: 12px;
          margin-top: 18px;
        }

        .button {
          border: 1px solid rgba(255, 255, 255, 0.3);
          border-radius: 8px;
          padding: 10px 18px;
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          text-decoration: none;
        }

        .button.secondary {
          background: rgba(255, 255, 255, 0.08);
          color: #edf4ff;
        }

        .button.primary {
          background: #0b56d4;
          border-color: rgba(255, 255, 255, 0.8);
          color: #f4f7ff;
        }

        .button:hover {
          filter: brightness(1.05);
          transform: translateY(-1px);
        }

        .login-card {
          background: #eef3f8;
          border: 2px dashed rgba(72, 124, 234, 0.8);
          border-top: none;
          border-radius: 0 0 12px 12px;
          padding: 24px 22px 18px;
          box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.4);
        }

        .login-grid {
          display: grid;
          grid-template-columns: 1.05fr 1fr;
          gap: 22px;
          align-items: center;
        }

        .login-panel h2 {
          margin: 0 0 10px;
          font-size: clamp(1.8rem, 2vw, 2.25rem);
          font-weight: 700;
          color: #1a2d48;
        }

        .login-panel p {
          margin: 0 0 18px;
          font-size: 0.76rem;
          color: #586b87;
        }

        .login-form {
          display: grid;
          gap: 12px;
        }

        .login-form label {
          display: grid;
          gap: 7px;
          font-size: 0.72rem;
          font-weight: 600;
          color: #3d4d63;
        }

        .login-form input {
          width: 100%;
          border-radius: 8px;
          border: 1px solid #c8d2e2;
          background: rgba(255, 255, 255, 0.72);
          padding: 11px 12px;
          font-size: 0.9rem;
          box-sizing: border-box;
          color: #1b2b3b;
        }

        .login-form input::placeholder {
          color: #7d8ca1;
        }

        .login-form input:focus {
          outline: none;
          border-color: #3c8dff;
          box-shadow: 0 0 0 3px rgba(60, 141, 255, 0.18);
        }

        .login-helper {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 4px;
          margin-bottom: 6px;
          font-size: 0.74rem;
        }

        .login-helper a {
          color: #1e6fe6;
          text-decoration: none;
        }

        .checkbox-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-top: 6px;
          margin-bottom: 2px;
        }

        .check-wrap {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          color: #56708f;
          font-size: 0.72rem;
        }

        .check-wrap input {
          width: auto;
          accent-color: #0e54d8;
        }

        .login-actions {
          display: flex;
          gap: 10px;
          margin-top: 14px;
        }

        .login-actions .button {
          flex: 1;
        }

        .button.dark {
          background: #0d213c;
          color: white;
          border-color: #0d213c;
        }

        .visual {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
        }

        .visual-frame {
          width: 100%;
          max-width: 360px;
          aspect-ratio: 1.25;
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid rgba(31, 69, 126, 0.15);
          background-image: url("https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=900&q=80");
          background-size: cover;
          background-position: center;
          box-shadow: 0 10px 28px rgba(34, 57, 89, 0.18);
        }

        .visual-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 220px;
          padding: 10px 18px;
          background: #1f5adf;
          border-radius: 10px;
          color: #ffffff;
          font-weight: 700;
          font-size: 0.72rem;
          letter-spacing: 0.04em;
          box-shadow: 0 8px 18px rgba(31, 90, 223, 0.25);
        }

        .new-here {
          text-align: center;
          margin-top: 18px;
          font-weight: 700;
          font-size: 1rem;
          color: #1b2940;
        }

        @media (max-width: 700px) {
          .hero-form,
          .login-grid {
            grid-template-columns: 1fr;
          }

          .login-links {
            gap: 12px;
            font-size: 0.72rem;
          }

          .login-shell {
            padding-left: 12px;
            padding-right: 12px;
          }

          .visual-frame {
            max-width: 480px;
            aspect-ratio: 1.6;
          }
        }

        @media (max-width: 480px) {
          .login-shell {
            padding: 12px 10px 24px;
          }

          .login-topbar {
            align-items: flex-start;
            gap: 12px;
          }

          .login-links {
            flex-shrink: 0;
          }

          .welcome-panel {
            padding: 16px 14px;
          }

          .hero-actions,
          .login-actions {
            flex-direction: column;
          }

          .hero-actions .button,
          .login-actions .button {
            width: 100%;
          }

          .login-card {
            padding: 20px 14px 16px;
          }

          .login-helper,
          .checkbox-row {
            align-items: flex-start;
            flex-wrap: wrap;
          }

          .visual-badge {
            min-width: 0;
            width: 100%;
            text-align: center;
          }
        }
      `}</style>

      <div className="login-page">
        <div className="login-shell">
          <header className="login-topbar">
            <Sectionheader
              className="login-brand"
              aria-label="Brand logo "
              title="Login"
            />

            <nav className="login-links" aria-label="Main navigation">
              <Link to="/register" className="link-pill">
                Sign up
              </Link>
            </nav>
          </header>

          <section className="welcome-panel" aria-label="Welcome banner">
            <div className="welcome-inner">
              <h1>Welcome back</h1>
              <p>Sign in with your institutional account to continue.</p>
            </div>
          </section>

          <section className="login-card" aria-label="Sign in section">
            <div className="login-grid">
              <div className="login-panel">
                <h2>Sign in</h2>
                <p>Use the username and password issued for your account.</p>

                <form
                  id="login-form-main"
                  onSubmit={loginForm}
                  className="login-form"
                >
                  <label htmlFor="signin-username">
                    Username
                    <input
                      id="signin-username"
                      type="text"
                      name="username"
                      autoComplete="username"
                      placeholder="Your username"
                      required
                      value={username}
                      onChange={(event) => setUsername(event.target.value)}
                    />
                  </label>

                  <label htmlFor="signin-password">
                    Password
                    <input
                      id="signin-password"
                      type="password"
                      name="password"
                      autoComplete="current-password"
                      placeholder="Password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </label>

                  <div className="login-helper">
                    <span>Secure session authentication</span>
                    <Link to="/recover-password">Forgot password?</Link>
                  </div>

                  <div className="login-actions">
                    <Link to="/register" className="button secondary">
                      Request an account
                    </Link>
                    <button type="submit" className="button dark" disabled={isSubmitting}>
                      {isSubmitting ? "Signing in..." : "Sign in"}
                    </button>
                  </div>
                </form>
              </div>

              <div className="visual">
                <div className="visual-frame" aria-label="Student learning" />
              </div>
            </div>
          </section>

          <div className="new-here">
            <Link to="/register">New here?</Link>
          </div>
        </div>
      </div>
    </>
  );
};

export default Login;
