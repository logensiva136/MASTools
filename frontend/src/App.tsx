import { Routes, Route, Link, Navigate } from "react-router-dom";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import AppDetailPage from "./pages/AppDetailPage";
import TestRunPage from "./pages/TestRunPage";
import LoginPage from "./pages/LoginPage";
import { AuthProvider, useAuth } from "./context/AuthContext";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="top">
      <h1>
        <Link to="/" style={{ color: "inherit" }}>
          MASTools
        </Link>
      </h1>
      <span className="subtitle">OWASP MASVS / MASTG / MASWE testing workbench</span>
      {user && (
        <span className="muted" style={{ marginLeft: "auto", display: "flex", gap: "0.75rem", alignItems: "center" }}>
          {user.email}
          <button className="secondary" onClick={logout} type="button">
            Sign out
          </button>
        </span>
      )}
    </header>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div className="app-shell">
        <Header />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <ProjectsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:projectId"
            element={
              <RequireAuth>
                <ProjectDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/apps/:appId"
            element={
              <RequireAuth>
                <AppDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/test-runs/:testRunId"
            element={
              <RequireAuth>
                <TestRunPage />
              </RequireAuth>
            }
          />
        </Routes>
      </div>
    </AuthProvider>
  );
}
