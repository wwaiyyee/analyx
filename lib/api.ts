/**
 * Analyx API Client
 * Typed client for interacting with the Analyx FastAPI backend.
 */

function resolveApiBase(): string {
  const envUrl =
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE;
  if (!envUrl) return "http://localhost:8000/api";
  const trimmed = envUrl.replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const API_BASE_URL = resolveApiBase();

const TOKEN_STORAGE_KEY = "analyx_auth_token";
const WORKSPACE_STORAGE_KEY = "analyx_workspace_id";

// --- Token Management ---

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string, workspaceId?: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
  if (workspaceId) {
    localStorage.setItem(WORKSPACE_STORAGE_KEY, workspaceId);
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(WORKSPACE_STORAGE_KEY);
}

export function getStoredWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(WORKSPACE_STORAGE_KEY);
}

// --- Error Class ---

export class ApiError extends Error {
  public status: number;
  public code: string;
  public details: Record<string, unknown> | null;

  constructor(status: number, message: string, code = "API_ERROR", details: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// --- Base Fetch Wrapper ---

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    let errorCode = "HTTP_ERROR";
    let details: Record<string, unknown> | null = null;

    try {
      const errorJson = await response.json();
      if (errorJson.error) {
        errorMessage = errorJson.error.message || errorMessage;
        errorCode = errorJson.error.code || errorCode;
        details = errorJson.error.details || null;
      } else if (errorJson.detail) {
        if (typeof errorJson.detail === "string") {
          errorMessage = errorJson.detail;
        } else if (errorJson.detail.error) {
          errorMessage = errorJson.detail.error.message || errorMessage;
          errorCode = errorJson.detail.error.code || errorCode;
        }
      }
    } catch {
      // Use fallback error message
    }

    throw new ApiError(response.status, errorMessage, errorCode, details);
  }

  // Handle empty responses
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

// --- Domain Types ---

export interface NonceResponse {
  nonce: string;
  message: string;
}

export interface VerifyAuthResponse {
  token: string;
  workspace_id: string;
}

export interface DatasetItem {
  id: string;
  workspace_id: string;
  name: string;
  source_type: string;
  created_at: string;
  updated_at: string;
  current_version_id?: string;
  row_count?: number;
  version_hash?: string;
}

export interface DataDictionaryEntry {
  id: string;
  column_name: string;
  semantic_role: string;
  data_type: string;
  unit?: string | null;
  is_pii: boolean;
  masking_rule?: string | null;
  description?: string | null;
}

export interface JobStatusResponse {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  job_type: string;
  progress: number;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface AnalysisSessionDetail {
  session: {
    id: string;
    title: string;
    workspace_id: string;
    time_anchor?: string | null;
    created_at: string;
    updated_at: string;
  };
  messages: Array<{
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    created_at: string;
  }>;
  findings: Array<FindingItem>;
  assumptions: Array<AssumptionItem>;
}

export interface FindingItem {
  id: string;
  session_id: string;
  claim: string;
  claim_type: string;
  status: "supported" | "partially_supported" | "insufficient" | "not_applicable";
  evidence_id?: string | null;
  numbers_grounded: boolean;
  validation_json?: string | null;
}

export interface AssumptionItem {
  id: string;
  session_id: string;
  name: string;
  value: string;
  rationale?: string | null;
  source: string;
}

export interface EvidenceDetail {
  id: string;
  session_id: string;
  spec_json: string;
  metrics_json: string;
  reproduction_json: string;
  result_hash: string;
  row_count: number;
  created_at: string;
}

export interface EvidenceSlice {
  rows: Array<Record<string, unknown>>;
  total_count: number;
  row_refs?: Record<string, unknown>;
}

export interface ProveResponse {
  verified: boolean;
  expected_hash: string;
  recomputed_hash: string;
  duration_ms: number;
}

export interface ReportItem {
  id: string;
  session_id: string;
  workspace_id: string;
  title: string;
  markdown_content: string;
  sha256: string;
  frozen_region_hashes_json: string;
  created_at: string;
}

export interface PrepareAttestationResponse {
  report_id: string;
  root: string;
  memo: string;
  bundle: Record<string, unknown>;
}

export interface ConfirmAttestationResponse {
  status: string;
  explorer_url: string;
  attestation_record: {
    id: string;
    report_id: string;
    root: string;
    tx_signature: string;
    cluster: string;
    signer: string;
  };
}

export interface VerificationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface OnChainDetails {
  cluster: string;
  tx_signature: string;
  slot?: number | null;
  block_time?: string | null;
  signer: string;
  explorer_url: string;
}

export interface PublicVerifyResponse {
  status: "VERIFIED" | "MODIFIED" | "NOT_ANCHORED" | "INVALID_BUNDLE";
  checks: VerificationCheck[];
  on_chain?: OnChainDetails | null;
}

// --- API Methods ---

export const api = {
  // Health
  health: async (): Promise<{ status: string; version: string; backend: string }> => {
    return apiRequest("/health");
  },

  // Auth
  auth: {
    getNonce: async (wallet: string): Promise<NonceResponse> => {
      return apiRequest<NonceResponse>("/auth/nonce", {
        method: "POST",
        body: JSON.stringify({ wallet }),
      });
    },

    verify: async (
      wallet: string,
      signature: string,
      message: string
    ): Promise<VerifyAuthResponse> => {
      const res = await apiRequest<VerifyAuthResponse>("/auth/verify", {
        method: "POST",
        body: JSON.stringify({ wallet, signature, message }),
      });
      if (res.token) {
        setStoredToken(res.token, res.workspace_id);
      }
      return res;
    },

    demo: async (): Promise<VerifyAuthResponse> => {
      const res = await apiRequest<VerifyAuthResponse>("/auth/demo", {
        method: "POST",
      });
      if (res.token) {
        setStoredToken(res.token, res.workspace_id);
      }
      return res;
    },
  },

  // Datasets
  datasets: {
    list: async (): Promise<DatasetItem[]> => {
      return apiRequest<DatasetItem[]>("/datasets");
    },

    get: async (datasetId: string): Promise<DatasetItem> => {
      return apiRequest<DatasetItem>(`/datasets/${datasetId}`);
    },

    upload: async (
      file: File,
      name?: string
    ): Promise<{
      job_id: string;
      dataset_id: string;
      version_id: string;
      row_count: number;
      status: string;
    }> => {
      const formData = new FormData();
      formData.append("file", file);
      const query = name ? `?name=${encodeURIComponent(name)}` : "";
      return apiRequest(`/datasets/upload${query}`, {
        method: "POST",
        body: formData,
      });
    },

    getProfile: async (datasetId: string): Promise<Record<string, unknown>> => {
      return apiRequest<Record<string, unknown>>(`/datasets/${datasetId}/profile`);
    },

    getDictionary: async (datasetId: string): Promise<DataDictionaryEntry[]> => {
      return apiRequest<DataDictionaryEntry[]>(`/datasets/${datasetId}/dictionary`);
    },

    updateDictionary: async (
      datasetId: string,
      entries: Partial<DataDictionaryEntry>[]
    ): Promise<{ status: string; count: number }> => {
      return apiRequest(`/datasets/${datasetId}/dictionary`, {
        method: "PUT",
        body: JSON.stringify({ entries }),
      });
    },

    syncOnchain: async (
      address: string,
      cluster = "devnet"
    ): Promise<{ job_id: string; status: string }> => {
      return apiRequest("/datasets/sync-onchain", {
        method: "POST",
        body: JSON.stringify({ address, cluster }),
      });
    },
  },

  // Jobs
  jobs: {
    get: async (jobId: string): Promise<JobStatusResponse> => {
      return apiRequest<JobStatusResponse>(`/jobs/${jobId}`);
    },
  },

  // Sessions
  sessions: {
    create: async (
      title?: string,
      datasetIds?: string[]
    ): Promise<{ id: string; title: string; workspace_id: string }> => {
      return apiRequest("/sessions", {
        method: "POST",
        body: JSON.stringify({ title, dataset_ids: datasetIds }),
      });
    },

    get: async (sessionId: string): Promise<AnalysisSessionDetail> => {
      return apiRequest<AnalysisSessionDetail>(`/sessions/${sessionId}`);
    },

    getEvidenceList: async (sessionId: string): Promise<EvidenceDetail[]> => {
      return apiRequest<EvidenceDetail[]>(`/sessions/${sessionId}/evidence`);
    },
  },

  // Evidence
  evidence: {
    get: async (evidenceId: string): Promise<EvidenceDetail> => {
      return apiRequest<EvidenceDetail>(`/evidence/${evidenceId}`);
    },

    getSlice: async (evidenceId: string, limit = 200): Promise<EvidenceSlice> => {
      return apiRequest<EvidenceSlice>(`/evidence/${evidenceId}/slice?limit=${limit}`);
    },

    prove: async (evidenceId: string): Promise<ProveResponse> => {
      return apiRequest<ProveResponse>(`/evidence/${evidenceId}/prove`, {
        method: "POST",
      });
    },
  },

  // Reports
  reports: {
    generate: async (
      sessionId: string,
      title = "Analysis Report"
    ): Promise<ReportItem> => {
      return apiRequest<ReportItem>(`/sessions/${sessionId}/report`, {
        method: "POST",
        body: JSON.stringify({ title }),
      });
    },

    get: async (reportId: string): Promise<ReportItem> => {
      return apiRequest<ReportItem>(`/reports/${reportId}`);
    },

    exportMarkdown: async (reportId: string): Promise<string> => {
      return apiRequest<string>(`/reports/${reportId}/export?format=md`);
    },
  },

  // Attestation
  attestation: {
    prepare: async (
      reportId: string,
      signer: string,
      cluster = "devnet"
    ): Promise<PrepareAttestationResponse> => {
      return apiRequest<PrepareAttestationResponse>(
        `/reports/${reportId}/attestation/prepare`,
        {
          method: "POST",
          body: JSON.stringify({ signer, cluster }),
        }
      );
    },

    confirm: async (
      reportId: string,
      txSignature: string,
      cluster = "devnet"
    ): Promise<ConfirmAttestationResponse> => {
      return apiRequest<ConfirmAttestationResponse>(
        `/reports/${reportId}/attestation/confirm`,
        {
          method: "POST",
          body: JSON.stringify({ tx_signature: txSignature, cluster }),
        }
      );
    },
  },

  // Public Verify
  verify: {
    verifyBundle: async (payload: {
      bundle: Record<string, unknown>;
      report_markdown?: string;
      report_sha256?: string;
      tx_signature?: string;
      cluster?: string;
    }): Promise<PublicVerifyResponse> => {
      return apiRequest<PublicVerifyResponse>("/verify", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  },
};
