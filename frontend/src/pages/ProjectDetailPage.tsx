import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, AppRecord, Project } from "../lib/api";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [apps, setApps] = useState<AppRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function refresh() {
    if (!projectId) return;
    api.getProject(projectId).then(setProject).catch((e) => setError(String(e)));
    api.listApps(projectId).then(setApps).catch((e) => setError(String(e)));
  }

  useEffect(refresh, [projectId]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file || !projectId) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadApp(projectId, file);
      if (fileInput.current) fileInput.current.value = "";
      refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleScan(appId: string) {
    await api.triggerScan(appId);
    refresh();
  }

  return (
    <div>
      <p>
        <Link to="/">&larr; Projects</Link>
      </p>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{project?.name ?? "Loading..."}</h2>
        {project?.description && <p className="muted">{project.description}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Upload app (.apk / .ipa)</h3>
        <form onSubmit={handleUpload} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input ref={fileInput} type="file" accept=".apk,.ipa" required />
          <button type="submit" disabled={uploading}>
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
        {error && <p className="muted">{error}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Apps</h3>
        {apps.length === 0 && <p className="muted">No apps uploaded yet.</p>}
        {apps.map((a) => (
          <div className="list-item" key={a.id}>
            <div>
              <Link to={`/apps/${a.id}`}>{a.filename}</Link>
              <div className="muted">
                {a.platform} · {a.package_name ?? "package unknown"} {a.version_name ? `v${a.version_name}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span className={`badge ${a.status === "analyzed" ? "passed" : a.status === "failed" ? "failed" : "pending"}`}>
                {a.status}
              </span>
              <button className="secondary" onClick={() => handleScan(a.id)} disabled={a.status === "analyzing"}>
                {a.status === "analyzing" ? "Scanning..." : "Scan"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
