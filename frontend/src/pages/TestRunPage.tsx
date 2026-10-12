import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ControlResult, Finding, ResultStatus, Severity, TestRun } from "../lib/api";

const STATUS_OPTIONS: ResultStatus[] = ["pending", "passed", "failed", "manual_review", "not_applicable"];
const SEVERITY_OPTIONS: Severity[] = ["info", "low", "medium", "high", "critical"];

export default function TestRunPage() {
  const { testRunId } = useParams<{ testRunId: string }>();
  const [testRun, setTestRun] = useState<TestRun | null>(null);
  const [results, setResults] = useState<ControlResult[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [showFindingForm, setShowFindingForm] = useState(false);

  function refresh() {
    if (!testRunId) return;
    api.getTestRun(testRunId).then(setTestRun);
    api.listResults(testRunId).then(setResults);
    api.listFindings(testRunId).then(setFindings);
  }

  useEffect(refresh, [testRunId]);

  const byCategory = useMemo(() => {
    const groups: Record<string, ControlResult[]> = {};
    for (const r of results) {
      groups[r.control.category] ??= [];
      groups[r.control.category].push(r);
    }
    return groups;
  }, [results]);

  const summary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of results) counts[r.status] = (counts[r.status] ?? 0) + 1;
    return counts;
  }, [results]);

  async function handleResultChange(result: ControlResult, patch: Partial<ControlResult>) {
    setResults((prev) => prev.map((r) => (r.id === result.id ? { ...r, ...patch } : r)));
    await api.updateResult(result.id, patch);
  }

  async function handleComplete() {
    if (!testRunId) return;
    await api.completeTestRun(testRunId);
    refresh();
  }

  if (!testRun) return <p className="muted">Loading...</p>;

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 style={{ marginTop: 0 }}>Test run — {testRun.catalog_version}</h2>
          <span className={`badge ${testRun.status === "completed" ? "passed" : "pending"}`}>{testRun.status}</span>
        </div>
        <p className="muted">
          {testRun.tester_name && `Tester: ${testRun.tester_name} · `}
          Started {new Date(testRun.started_at).toLocaleString()}
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {Object.entries(summary).map(([status, count]) => (
            <span key={status} className={`badge ${status}`}>
              {status}: {count}
            </span>
          ))}
        </div>
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
          {testRun.status !== "completed" && <button onClick={handleComplete}>Mark complete</button>}
          <a href={api.reportUrl(testRun.id, "html")} target="_blank" rel="noreferrer">
            <button className="secondary" type="button">
              View HTML report
            </button>
          </a>
          <a href={api.reportUrl(testRun.id, "md")} target="_blank" rel="noreferrer">
            <button className="secondary" type="button">
              View Markdown report
            </button>
          </a>
        </div>
      </div>

      {Object.entries(byCategory).map(([category, items]) => (
        <div className="category-group card" key={category}>
          <h3>{category}</h3>
          {items.map((r) => (
            <ControlRow key={r.id} result={r} onChange={(patch) => handleResultChange(r, patch)} />
          ))}
        </div>
      ))}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h3 style={{ marginTop: 0 }}>Findings</h3>
          <button className="secondary" onClick={() => setShowFindingForm((s) => !s)}>
            {showFindingForm ? "Cancel" : "Add finding"}
          </button>
        </div>
        {showFindingForm && testRunId && (
          <FindingForm
            testRunId={testRunId}
            onCreated={() => {
              setShowFindingForm(false);
              refresh();
            }}
          />
        )}
        {findings.length === 0 && <p className="muted">No findings recorded.</p>}
        {findings.map((f) => (
          <div className="list-item" key={f.id} style={{ display: "block" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong>{f.title}</strong>
              <span className={`badge ${f.severity === "critical" || f.severity === "high" ? "failed" : "manual_review"}`}>
                {f.severity}
              </span>
            </div>
            <p className="muted" style={{ margin: "0.25rem 0" }}>
              {f.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ControlRow({ result, onChange }: { result: ControlResult; onChange: (patch: Partial<ControlResult>) => void }) {
  const [evidence, setEvidence] = useState(result.evidence ?? "");
  const [notes, setNotes] = useState(result.notes ?? "");

  return (
    <div className="control-row">
      <div className="control-head">
        <div>
          <code>{result.control.code}</code> — {result.control.title}
          {result.control.automatable && <span className="muted"> · automatable</span>}
        </div>
        <select
          value={result.status}
          onChange={(e) => onChange({ status: e.target.value as ResultStatus })}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s} {result.method === "automated" && s === result.status ? "(auto)" : ""}
            </option>
          ))}
        </select>
      </div>
      <p className="muted" style={{ margin: "0.4rem 0" }}>
        {result.control.description}
      </p>
      <div className="refs">
        MASTG: {result.control.mastg_tests.join(", ") || "—"} · MASWE: {result.control.maswe_ids.join(", ") || "—"}
      </div>
      <div className="fields">
        <textarea
          placeholder="Evidence"
          value={evidence}
          onChange={(e) => setEvidence(e.target.value)}
          onBlur={() => onChange({ evidence })}
        />
        <textarea
          placeholder="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => onChange({ notes })}
        />
      </div>
    </div>
  );
}

function FindingForm({ testRunId, onCreated }: { testRunId: string; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [description, setDescription] = useState("");
  const [remediation, setRemediation] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setSaving(true);
    try {
      await api.createFinding(testRunId, {
        title: title.trim(),
        severity,
        description: description.trim(),
        evidence: null,
        remediation: remediation.trim() || null,
        control_id: null,
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ margin: "0.5rem 0" }}>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 1 }} required />
        <select value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <textarea
        placeholder="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        style={{ width: "100%", minHeight: "3rem", marginBottom: "0.5rem" }}
        required
      />
      <textarea
        placeholder="Remediation (optional)"
        value={remediation}
        onChange={(e) => setRemediation(e.target.value)}
        style={{ width: "100%", minHeight: "2.5rem", marginBottom: "0.5rem" }}
      />
      <button type="submit" disabled={saving}>
        {saving ? "Saving..." : "Save finding"}
      </button>
    </form>
  );
}
