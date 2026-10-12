import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Project } from "../lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api.createProject(name.trim(), description.trim() || undefined);
    setName("");
    setDescription("");
    refresh();
  }

  return (
    <div>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>New project</h2>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <input placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <button type="submit">Create</button>
        </form>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Projects</h2>
        {loading && <p className="muted">Loading...</p>}
        {error && <p className="muted">{error}</p>}
        {!loading && projects.length === 0 && <p className="muted">No projects yet — create one above.</p>}
        {projects.map((p) => (
          <div className="list-item" key={p.id}>
            <div>
              <Link to={`/projects/${p.id}`}>{p.name}</Link>
              {p.description && <div className="muted">{p.description}</div>}
            </div>
            <span className="muted">{new Date(p.created_at).toLocaleDateString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
