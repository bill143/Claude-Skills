"use client";

/** Typed fetch client for the CFCS API (same-origin; Next proxies /api/v1). */

const TOKEN_KEY = "cfcs_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode */
  }
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  formData?: FormData;
  /** Attach an Idempotency-Key header (money-moving calls). */
  idempotent?: boolean;
  params?: Record<string, string | number | boolean | undefined>;
};

export async function api<T = unknown>(path: string, options: Options = {}): Promise<T> {
  const { method = "GET", body, formData, idempotent, params } = options;
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const query = params
    ? "?" +
      Object.entries(params)
        .filter(([, value]) => value !== undefined && value !== "")
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
        .join("&")
    : "";

  const response = await fetch(`/api/v1${path}${query}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (response.status === 401 && typeof window !== "undefined") {
    setToken(null);
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams({ username: email, password });
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!response.ok) {
    let detail = "Login failed";
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, detail);
  }
  const data = (await response.json()) as { access_token: string };
  setToken(data.access_token);
}

/* ---- Shared API types ---- */

export type User = { id: number; email: string; full_name: string; role: string };

export type Project = {
  id: number;
  code: string;
  name: string;
  owner_name: string | null;
  original_contract_value: number;
  budget_control: "STOP" | "WARN" | "IGNORE";
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
};

export type LineMetrics = {
  id: number;
  cost_code: string;
  division: string;
  description: string;
  category: string;
  manual_etc: number | null;
  original_budget: number;
  approved_changes: number;
  current_budget: number;
  committed: number;
  actual: number;
  etc: number;
  eac: number;
  vac: number;
  method: string;
};

export type Rollup = {
  original_budget: number;
  approved_changes: number;
  current_budget: number;
  committed: number;
  actual: number;
  etc: number;
  eac: number;
  vac: number;
};

export type WbsSection = { code: string; title: string; rollup: Rollup; lines: LineMetrics[] };
export type WbsDivision = { division: string; title: string; rollup: Rollup; sections: WbsSection[] };
export type WbsTree = { project_id: number; method: string; divisions: WbsDivision[]; totals: Rollup };

export type Kpis = {
  project_id: number;
  project_code: string;
  contract_value: number;
  original_budget: number;
  approved_changes: number;
  current_budget: number;
  committed: number;
  actual_to_date: number;
  etc: number;
  eac: number;
  vac: number;
  projected_margin: number;
  burn_rate_30d: number;
  percent_complete: number;
  method: string;
  open_pcos: number;
  pending_approvals: number;
};

export type ChangeOrderLine = {
  id: number;
  budget_line_id: number;
  description: string;
  quantity: number;
  unit_cost: number;
  amount: number;
};

export type ChangeOrder = {
  id: number;
  project_id: number;
  number: string;
  co_type: "PCO" | "OCO" | "SCO";
  status: string;
  title: string;
  description: string | null;
  vendor_id: number | null;
  origin_pco_id: number | null;
  schedule_impact_days: number;
  total_amount: number;
  lines: ChangeOrderLine[];
  created_at: string;
  allowed_actions: string[];
};

export type PurchaseOrder = {
  id: number;
  project_id: number;
  number: string;
  vendor_id: number;
  status: string;
  source_change_order_id: number | null;
  total_amount: number;
  lines: ChangeOrderLine[];
  created_at: string;
};

export type Vendor = {
  id: number;
  name: string;
  vendor_type: string;
  trade: string | null;
  contact_email: string | null;
  is_active: boolean;
};

export type ApprovalRequest = {
  id: number;
  entity_type: string;
  entity_id: number;
  sequence: number;
  required_role: string;
  status: string;
  comment: string | null;
  decided_at: string | null;
  created_at: string;
};

export type BudgetLine = {
  id: number;
  project_id: number;
  cost_code: string;
  description: string;
  category: string;
  original_budget: number;
  manual_etc: number | null;
};

export type CostCode = { code: string; title: string; division: string; level: number };

export type ImportPreview = {
  filename: string;
  rows_parsed: number;
  rows_new: number;
  rows_duplicate: number;
  rows_invalid: number;
  total_amount_new: number;
  rows: {
    code: string;
    division: string;
    description: string;
    category: string;
    amount: number;
    in_library: boolean;
    exists_in_project: boolean;
    merged_rows: number;
  }[];
  invalid: { row: number; code: string; error: string }[];
};
