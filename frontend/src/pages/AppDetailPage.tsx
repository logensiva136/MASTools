import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, AppRecord, TestRun } from "../lib/api";

export default function AppDetailPage() {
  const { appId } = useParams<{ appId: string }>();
  const [app, setApp] = useState<AppRecord | null>(null);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [testerName, setTesterName] = useState("");
  const [creating, setCreating] = useState(false);

  function refresh() {
    if (!appId) return;
    api.getApp(appId).then(setApp);
    api.listTestRuns(appId).then(setTestRuns);
  }

  useEffect(refresh, [appId]);

  async function handleCreateRun(e: React.FormEvent) {
    e.preventDefault();
    if (!appId) return;
    setCreating(true);
    try {
      const run = await api.createTestRun(appId, testerName.trim() || undefined);
      setTesterName("");
      refresh();
      window.location.href = `/test-runs/${run.id}`;
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <p>
        {app && <Link to={`/projects/${app.project_id}`}>&larr; Project</Link>}
      </p>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{app?.filename}</h2>
        {app && (
          <p className="muted">
            {app.platform} · {app.package_name ?? "package unknown"} {app.version_name ? `v${app.version_name}` : ""} ·
            status: {app.status}
          </p>
        )}
        {app?.extracted_metadata && (
          <details>
            <summary>Extracted metadata</summary>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
              {JSON.stringify(app.extracted_metadata, null, 2)}
            </pre>
          </details>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Start a new test run</h3>
        <form onSubmit={handleCreateRun} style={{ display: "flex", gap: "0.5rem" }}>
          <input placeholder="Tester name (optional)" value={testerName} onChange={(e) => setTesterName(e.target.value)} />
          <button type="submit" disabled={creating}>
            {creating ? "Creating..." : "Start test run"}
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Test runs</h3>
        {testRuns.length === 0 && <p className="muted">No test runs yet.</p>}
        {testRuns.map((tr) => (
          <div className="list-item" key={tr.id}>
            <div>
              <Link to={`/test-runs/${tr.id}`}>{tr.catalog_version}</Link>
              <div className="muted">
                started {new Date(tr.started_at).toLocaleString()} {tr.tester_name && `· ${tr.tester_name}`}
              </div>
            </div>
            <span className={`badge ${tr.status === "completed" ? "passed" : "pending"}`}>{tr.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
