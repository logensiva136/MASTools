import { Routes, Route, Link } from "react-router-dom";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import AppDetailPage from "./pages/AppDetailPage";
import TestRunPage from "./pages/TestRunPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="top">
        <h1>
          <Link to="/" style={{ color: "inherit" }}>
            MASTools
          </Link>
        </h1>
        <span className="subtitle">OWASP MASVS / MASTG / MASWE testing workbench</span>
      </header>
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/apps/:appId" element={<AppDetailPage />} />
        <Route path="/test-runs/:testRunId" element={<TestRunPage />} />
      </Routes>
    </div>
  );
}
