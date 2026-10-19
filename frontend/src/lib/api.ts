import { clearToken, getToken } from "./auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Fired on any 401 so the app shell can drop back to the login screen —
// set by AuthContext so this module doesn't need to import React state.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

export type Platform = "android" | "ios";
export type AppStatus = "uploaded" | "analyzing" | "analyzed" | "failed";
export type ResultStatus = "pending" | "passed" | "failed" | "not_applicable" | "manual_review";
export type ResultMethod = "manual" | "automated";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type TestRunStatus = "created" | "running" | "completed" | "failed";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface AppRecord {
  id: string;
  project_id: string;
  filename: string;
  platform: Platform;
  package_name: string | null;
  version_name: string | null;
  status: AppStatus;
  uploaded_at: string;
  extracted_metadata: Record<string, unknown> | null;
}

export interface Control {
  id: string;
  version: string;
  code: string;
  category: string;
  title: string;
  description: string;
  mastg_tests: string[];
  maswe_ids: string[];
  applies_to: string[];
  automatable: boolean;
}

export interface TestRun {
  id: string;
  app_id: string;
  catalog_version: string;
  status: TestRunStatus;
  started_at: string;
  completed_at: string | null;
  tester_name: string | null;
  notes: string | null;
}

export interface ControlResult {
  id: string;
  test_run_id: string;
  control_id: string;
  status: ResultStatus;
  method: ResultMethod;
  evidence: string | null;
  notes: string | null;
  updated_at: string;
  control: Control;
}

export interface Finding {
  id: string;
  test_run_id: string;
  control_id: string | null;
  title: string;
  severity: Severity;
  description: string;
  evidence: string | null;
  remediation: string | null;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (!(init?.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...headers, ...init?.headers } });

  if (res.status === 401) {
    clearToken();
    onUnauthorized?.();
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Report endpoints need the same Authorization header as everything else,
// so a plain <a href> (no custom headers) can't hit them directly — fetch
// the report as the authenticated client and hand back a blob: URL the
// browser can open, same as any other fetched-then-downloaded file.
async function fetchReportBlobUrl(testRunId: string, format: "md" | "html"): Promise<string> {
  const token = getToken();
  const res = await fetch(`${BASE_URL}/api/test-runs/${testRunId}/report.${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (res.status === 401) {
    clearToken();
    onUnauthorized?.();
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export const api = {
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: async (email: string, password: string): Promise<string> => {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${BASE_URL}/api/auth/login`, { method: "POST", body: form });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    const data = (await res.json()) as { access_token: string };
    return data.access_token;
  },
  me: () => request<User>("/api/auth/me"),

  listProjects: () => request<Project[]>("/api/projects"),
  createProject: (name: string, description?: string) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),

  listApps: (projectId: string) => request<AppRecord[]>(`/api/projects/${projectId}/apps`),
  getApp: (appId: string) => request<AppRecord>(`/api/apps/${appId}`),
  uploadApp: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<AppRecord>(`/api/projects/${projectId}/apps`, { method: "POST", body: form });
  },
  triggerScan: (appId: string) => request<{ task_id: string; status: string }>(`/api/apps/${appId}/scan`, { method: "POST" }),

  listControls: (version?: string) => request<Control[]>(`/api/controls${version ? `?version=${version}` : ""}`),

  listTestRuns: (appId: string) => request<TestRun[]>(`/api/apps/${appId}/test-runs`),
  createTestRun: (appId: string, testerName?: string) =>
    request<TestRun>(`/api/apps/${appId}/test-runs`, { method: "POST", body: JSON.stringify({ tester_name: testerName }) }),
  getTestRun: (testRunId: string) => request<TestRun>(`/api/test-runs/${testRunId}`),
  completeTestRun: (testRunId: string) => request<TestRun>(`/api/test-runs/${testRunId}/complete`, { method: "POST" }),

  listResults: (testRunId: string) => request<ControlResult[]>(`/api/test-runs/${testRunId}/results`),
  updateResult: (resultId: string, payload: Partial<Pick<ControlResult, "status" | "evidence" | "notes">>) =>
    request<ControlResult>(`/api/results/${resultId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  listFindings: (testRunId: string) => request<Finding[]>(`/api/test-runs/${testRunId}/findings`),
  createFinding: (testRunId: string, payload: Omit<Finding, "id" | "test_run_id" | "created_at">) =>
    request<Finding>(`/api/test-runs/${testRunId}/findings`, { method: "POST", body: JSON.stringify(payload) }),

  openReport: fetchReportBlobUrl,
};
