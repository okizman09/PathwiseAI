/**
 * Pathwise AI — Frontend API Client
 * Connects the frontend directly to the FastAPI backend with /api/v1 prefix and signed links.
 */
import { supabase } from "./supabase";

export interface ToolPromptStyle {
  technique: string;
  format: string;
  rules: string[];
  example: string;
}

export interface ToolShortCard {
  id: number;
  name: string;
  go_path: string;
  category: string;
  domain?: string | null;
  ecosystem?: string | null;
  kind?: string | null;
  model_id?: string | null;
  api_snippet?: string | null;
  jobs: string[];
  input_types: string[];
  output_types: string[];
  pricing: string;
  pricing_model?: string;
  has_free_tier?: boolean | null;
  free_tier_summary?: string | null;
  free_tier_limits?: string | null;
  starting_price_monthly_usd?: number | null;
  commercial_use_on_free?: boolean | null;
  credit_card_required?: boolean | null;
  best_for: string;
  not_for?: string | null;
  prompt_style: ToolPromptStyle;
  why_chosen?: string | null;
  logo_url?: string | null;
  logo_source?: string | null;
  og_image_url?: string | null;
  is_pick?: boolean;
  warnings?: string[];
}

export interface ToolSourceItem {
  url: string;
  fetched_at?: string;
  ok: boolean;
  error?: string | null;
}

export interface TaxonomyDomain {
  slug: string;
  label: string;
  jobs: string[];
}

export interface TaxonomyJob {
  slug: string;
  label: string;
  domain: string;
}

export interface TaxonomyPayload {
  domains: TaxonomyDomain[];
  jobs: TaxonomyJob[];
  domain_labels: Record<string, string>;
  job_labels: Record<string, string>;
}

export interface ToolRecheckData {
  category?: string;
  jobs?: string[];
  input_types?: string[];
  output_types?: string[];
  pricing?: string;
  best_for?: string;
  not_for?: string;
  prompt_style?: ToolPromptStyle;
  research_notes?: string;
  sources?: ToolSourceItem[];
}

export interface ToolEvidenceItem {
  source_url: string;
  quote: string;
  checked?: boolean | string | null;
}

export interface ToolEvidenceMap {
  pricing_model?: ToolEvidenceItem | null;
  has_free_tier?: ToolEvidenceItem | null;
  free_tier_summary?: ToolEvidenceItem | null;
  starting_price_monthly_usd?: ToolEvidenceItem | null;
  credit_card_required?: ToolEvidenceItem | null;
  commercial_use_on_free?: ToolEvidenceItem | null;
  watermark_on_free?: ToolEvidenceItem | null;
  skill_level?: ToolEvidenceItem | null;
  platforms?: ToolEvidenceItem | null;
  [key: string]: ToolEvidenceItem | null | undefined;
}

export interface ToolResponse extends ToolShortCard {
  url?: string;
  affiliate_url?: string | null;
  docs_url?: string | null;
  domain?: string | null;
  tagline?: string | null;
  summary?: string | null;
  how_it_helps?: string | null;
  pros?: string[];
  cons?: string[];
  not_for?: string | null;
  pricing_model?: string;
  has_free_tier?: boolean | null;
  free_tier_summary?: string | null;
  free_tier_limits?: string | null;
  starting_price_monthly_usd?: number | null;
  pricing_notes?: string | null;
  credit_card_required?: boolean | null;
  watermark_on_free?: boolean | null;
  commercial_use_on_free?: boolean | null;
  pricing_url?: string | null;
  pricing_checked_at?: string | null;
  platforms?: string[];
  skill_level?: string;
  logo_url?: string | null;
  logo_source?: string | null;
  og_image_url?: string | null;
  evidence?: ToolEvidenceMap | null;
  review_flags?: string[];
  official_domains?: string[];
  is_pick?: boolean;
  verified_by?: string | null;
  verified_at?: string | null;
  verified_badge?: string | null;
  status: "draft" | "researched" | "verified" | "hidden";
  link_status?: string;
  link_checked_at?: string | null;
  used_in_workflows_count?: number | null;
  sources?: ToolSourceItem[] | null;
  research_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ToolMetricResponse {
  tool_id: number;
  name: string;
  domain: string | null;
  total_feedbacks: number;
  worked_count: number;
  partly_count: number;
  didnt_count: number;
  success_rate_percent: number | null;
  used_in_workflows: number;
}

export interface CardImportResult {
  name: string;
  status: "created" | "updated" | "rejected" | "error";
  tool_id?: number | null;
  flags: string[];
  error?: string | null;
}

export interface CardImportResponse {
  created: number;
  updated: number;
  rejected: number;
  missing_tools: string[];
  results: CardImportResult[];
}

export interface ProductBrief {
  what_being_made: string;
  purpose: string;
  target_audience: string;
  constraints: string[];
  must_haves: string[];
  nice_to_haves: string[];
  assumptions: string[];
  skill_level: "beginner" | "intermediate" | "advanced" | "unknown";
  budget_preference: "free_only" | "low" | "flexible" | "unknown";
  needs_commercial_use: "yes" | "no" | "unknown";
  detected_domains?: string[];
  product_name?: string | null;
}

export interface InterviewAnswer {
  question: string;
  answer: string;
}

export interface InterviewQuestionResponse {
  type: "question";
  question: string;
  options: string[];
  allow_custom_text: boolean;
}

export interface InterviewReadyResponse {
  type: "ready";
  brief: ProductBrief;
}

export type InterviewResponse = InterviewQuestionResponse | InterviewReadyResponse;

export interface CostSummary {
  mode: "free" | "may_cost";
  estimated_monthly_usd?: number | null;
  notes: string[];
  pricing_complete?: boolean;
}

export interface WorkflowStep {
  step_id: string;
  step_number: number;
  kind?: "tool" | "no_tool";
  job: string;
  why_step?: string;
  primary_tool?: ToolShortCard | null;
  alternatives?: ToolShortCard[];
  prompt?: string | null;
  content_type?: "prompt" | "steps" | null;
  action_steps?: string[] | null;
  technique?: string | null;
  output_expected?: string | null;
  why_tool?: string | null;
  learn_note?: string | null;
  handoff_note?: string | null;
  status?: string;
  free_tier_note?: string | null;
  warnings?: string[];
  can_run?: boolean;
}

export interface WorkflowResponse {
  id: number;
  workflow_id?: string;
  title?: string;
  brief: ProductBrief;
  cost_summary?: CostSummary;
  steps: WorkflowStep[];
  created_at?: string;
}

export interface StepActionRequest {
  workflow_id?: string | number;
  step_id?: string;
  step: WorkflowStep;
  action: "regenerate" | "switch_tool" | "finished";
  payload?: string;
  feedback_result?: "worked" | "partly" | "didnt";
  brief?: ProductBrief;
  steps?: WorkflowStep[];
}

export interface StepActionResponse {
  workflow_id?: string;
  step: WorkflowStep;
  next_step?: WorkflowStep | null;
  action: string;
  message: string;
}

export interface StepRunResponse {
  run_id: number;
  step_id: string;
  model_id: string;
  status: string;
  output_text: string;
  error_code?: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
}

export interface WorkflowListResponse {
  id: number;
  title: string;
  created_at: string;
}

export interface WorkflowPatchRequest {
  title?: string;
  archive?: boolean;
}

export interface QuotaUsageResponse {
  kind: string;
  limit: number;
  used: number;
  resets_at: string;
  email_verified?: boolean;
}

export interface AdminToolCreateRequest {
  name: string;
  url?: string | undefined;
  docs_url?: string | undefined;
  affiliate_url?: string | null | undefined;
  category?: string | undefined;
  pricing?: string | undefined;
  best_for?: string | undefined;
  not_for?: string | undefined;
  jobs?: string[] | undefined;
  prompt_style?: ToolPromptStyle | undefined;
}

export interface AuthUserResponse {
  id: number | string;
  email: string;
  role: "admin" | "creator" | "user";
  email_verified?: boolean;
  created_at?: string;
}

export interface DailyLimitDetails {
  code: "daily_limit";
  kind: "workflow" | "interview_turn" | "step_action";
  limit: number;
  used: number;
  resets_at: string;
}

export class DailyLimitError extends Error {
  details: DailyLimitDetails;
  constructor(details: DailyLimitDetails) {
    super(`Daily limit reached for ${details.kind}. Resets at ${details.resets_at}`);
    this.name = "DailyLimitError";
    this.details = details;
  }
}

export class NotInBetaError extends Error {
  constructor(message: string = "Pathwise is currently in invite-only private beta.") {
    super(message);
    this.name = "NotInBetaError";
  }
}

export interface ToolListFilter {
  category?: string;
  domain?: string;
  ecosystem?: string;
}

export const getApiBaseUrl = (): string => {
  const envUrl = (import.meta as any).env?.VITE_API_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim().length > 0) {
    let clean = envUrl.trim().replace(/\/+$/, "");
    if (clean.endsWith("/api/v1")) {
      clean = clean.slice(0, -"/api/v1".length).replace(/\/+$/, "");
    }
    return clean;
  }
  if (typeof window !== "undefined") {
    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      return "https://pathwise-ai-qkf1.onrender.com";
    }
  } else if (typeof process !== "undefined" && process.env?.["NODE_ENV"] === "production") {
    return "https://pathwise-ai-qkf1.onrender.com";
  }
  return "http://localhost:8000";
};

export const API_BASE_URL = getApiBaseUrl();

async function getAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  try {
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token || null;
  } catch {
    return null;
  }
}

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  if (path.startsWith("/api/v1/api/v1")) {
    path = path.replace(/^\/api\/v1/, "");
  }
  const isRootRoute = path === "/health" || path.startsWith("/go");
  const fullPath = isRootRoute ? path : (path.startsWith("/api/v1") ? path : `/api/v1${path}`);
  const baseUrl = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
  const url = `${baseUrl}${fullPath}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  // Inject JWT Bearer token if not explicitly provided
  const token = await getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson?.code === "daily_limit") {
        throw new DailyLimitError(errJson);
      }
      if (errJson?.detail?.code === "daily_limit") {
        throw new DailyLimitError(errJson.detail);
      }
      if (errJson?.code === "not_in_beta" || errJson?.detail?.code === "not_in_beta") {
        throw new NotInBetaError(
          errJson?.message ||
            errJson?.detail?.message ||
            "Pathwise is currently in private beta. Your account has not been granted access yet."
        );
      }
      if (errJson?.message) {
        errorDetail = errJson.message;
      } else if (errJson?.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch (e) {
      if (e instanceof DailyLimitError) throw e;
      const errText = await response.text().catch(() => "");
      if (errText) errorDetail = errText;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  /**
   * Health check endpoint (root)
   */
  async checkHealth(): Promise<{ status: string; latencyMs: number }> {
    const start = performance.now();
    const data = await apiFetch<{ status: string }>("/health");
    const latencyMs = Math.round(performance.now() - start);
    return { status: data.status, latencyMs };
  },

  /**
   * Authentication: Get current user profile from backend
   */
  async getMe(): Promise<AuthUserResponse> {
    return apiFetch<AuthUserResponse>("/me");
  },

  /**
   * Quota: Get remaining limits for the user
   */
  async getUsage(): Promise<Record<string, QuotaUsageResponse>> {
    return apiFetch<Record<string, QuotaUsageResponse>>("/usage");
  },

  /**
   * Public tools directory (verified only)
   */
  async getTools(filter?: ToolListFilter | string): Promise<ToolResponse[]> {
    if (typeof filter === "string") {
      const query = filter && filter !== "all" ? `?category=${encodeURIComponent(filter)}` : "";
      return apiFetch<ToolResponse[]>(`/tools${query}`);
    }
    const params = new URLSearchParams();
    if (filter?.category && filter.category !== "all") params.append("category", filter.category);
    if (filter?.domain && filter.domain !== "all") params.append("domain", filter.domain);
    if (filter?.ecosystem && filter.ecosystem !== "all") params.append("ecosystem", filter.ecosystem);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return apiFetch<ToolResponse[]>(`/tools${qs}`);
  },

  /**
   * Interview turn: provides user goal + prior answers, returns next question or ready brief
   */
  async submitInterview(goal: string, answers: InterviewAnswer[] = []): Promise<InterviewResponse> {
    return apiFetch<InterviewResponse>("/interview", {
      method: "POST",
      body: JSON.stringify({ goal, answers }),
    });
  },

  /**
   * Generate variable 1-6 step workflow for locked product brief
   */
  async generateWorkflow(brief: ProductBrief): Promise<WorkflowResponse> {
    return apiFetch<WorkflowResponse>("/workflows", {
      method: "POST",
      body: JSON.stringify({ brief }),
    });
  },

  /**
   * Obtain signed click tracking URL for a step tool
   */
  async openLink(workflowId: number | string, stepId: string, toolId?: number): Promise<{ go_url: string }> {
    return apiFetch<{ go_url: string }>(`/workflows/${workflowId}/steps/${stepId}/open-link`, {
      method: "POST",
      body: JSON.stringify(toolId ? { tool_id: toolId } : {}),
    });
  },

  /**
   * Recheck step for newly added tools
   */
  async recheckStep(workflowId: number | string, stepId: string): Promise<StepActionResponse> {
    return apiFetch<StepActionResponse>(`/workflows/${workflowId}/steps/${stepId}/recheck`, {
      method: "POST",
    });
  },

  /**
   * Update a step: regenerate prompt, switch tool, or record finished note
   */
  async updateStep(req: StepActionRequest): Promise<StepActionResponse> {
    const workflowId = req.workflow_id;
    const stepId = req.step_id;
    const action = req.action;
    let url = `/workflows/${workflowId}/steps/${stepId}`;
    if (action === "regenerate") url += "/regenerate";
    else if (action === "switch_tool") url += "/switch-tool";
    else if (action === "finished") url += "/finish";

    let body: any = {};
    if (action === "regenerate") body = { feedback: req.payload };
    else if (action === "switch_tool") body = { tool_id: parseInt(req.payload || "0", 10) };
    else if (action === "finished") body = { note: req.payload || "", feedback_result: req.feedback_result };

    return apiFetch<StepActionResponse>(url, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /**
   * Run a prompt step live on its verified catalog model (T9)
   */
  async runStep(
    workflowId: number | string,
    stepId: string,
    prompt?: string,
  ): Promise<StepRunResponse> {
    return apiFetch<StepRunResponse>(
      `/workflows/${workflowId}/steps/${stepId}/run`,
      {
        method: "POST",
        body: JSON.stringify(prompt ? { prompt } : {}),
      },
    );
  },

  /**
   * Submit or update step feedback (Slice C7)
   */
  async submitStepFeedback(
    workflowId: number | string,
    stepId: string,
    data: { result: "worked" | "partly" | "didnt"; note?: string }
  ): Promise<any> {
    return apiFetch<any>(`/workflows/${workflowId}/steps/${stepId}/feedback`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * History: list workflows
   */
  async getWorkflows(skip = 0, limit = 50): Promise<WorkflowListResponse[]> {
    return apiFetch<WorkflowListResponse[]>(`/workflows?skip=${skip}&limit=${limit}`);
  },

  /**
   * History: get a single workflow
   */
  async getWorkflow(id: number): Promise<WorkflowResponse> {
    return apiFetch<WorkflowResponse>(`/workflows/${id}`);
  },

  /**
   * History: update a workflow
   */
  async updateWorkflow(id: number, req: WorkflowPatchRequest): Promise<void> {
    return apiFetch<void>(`/workflows/${id}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    });
  },

  /**
   * History: delete a workflow
   */
  async deleteWorkflow(id: number): Promise<void> {
    return apiFetch<void>(`/workflows/${id}`, {
      method: "DELETE",
    });
  },

  /**
   * Admin: List all tools
   */
  async getAdminTools(status?: string, category?: string): Promise<ToolResponse[]> {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (category && category !== "all") params.append("category", category);
    const queryString = params.toString() ? `?${params.toString()}` : "";

    return apiFetch<ToolResponse[]>(`/admin/tools${queryString}`);
  },

  /**
   * Admin: Import cards batch (Catalog v3)
   */
  async importCards(cards: any[], expected?: string[]): Promise<CardImportResponse> {
    return apiFetch<CardImportResponse>("/admin/tools/import-cards", {
      method: "POST",
      body: JSON.stringify({ cards, expected }),
    });
  },

  /**
   * Admin: Add new tool (docs_url triggers Gemini draft extraction)
   */
  async createAdminTool(tool: AdminToolCreateRequest): Promise<ToolResponse> {
    return apiFetch<ToolResponse>("/admin/tools", {
      method: "POST",
      body: JSON.stringify(tool),
    });
  },

  /**
   * Admin: Update tool or change status to verified
   */
  async updateAdminTool(
    toolId: number,
    toolUpdate: Partial<ToolResponse>
  ): Promise<ToolResponse> {
    return apiFetch<ToolResponse>(`/admin/tools/${toolId}`, {
      method: "PATCH",
      body: JSON.stringify(toolUpdate),
    });
  },

  /**
   * Admin: Delete tool from catalog
   */
  async deleteAdminTool(toolId: number): Promise<void> {
    return apiFetch<void>(`/admin/tools/${toolId}`, {
      method: "DELETE",
    });
  },

  /**
   * Admin: List stale verified tools (>30 days since pricing checked)
   */
  async getAdminStaleTools(): Promise<ToolResponse[]> {
    return apiFetch<ToolResponse[]>("/admin/tools/stale");
  },

  /**
   * Admin: Recheck tool via fresh card JSON showing diff, or automated extraction
   */
  async recheckAdminTool(toolId: number, card?: any, apply: boolean = false): Promise<any> {
    return apiFetch<any>(`/admin/tools/${toolId}/recheck`, {
      method: "POST",
      body: JSON.stringify({ card, apply }),
    });
  },

  /**
   * Admin: Run background/manual link reachability health check
   */
  async checkAllAdminLinks(): Promise<{ checked: number; dead: number; hidden: number; ok: number }> {
    return apiFetch<{ checked: number; dead: number; hidden: number; ok: number }>("/admin/jobs/check-links", {
      method: "POST",
    });
  },

  /**
   * Admin: List usage signals and per-tool success rates
   */
  async getAdminToolMetrics(): Promise<ToolMetricResponse[]> {
    return apiFetch<ToolMetricResponse[]>("/admin/tools/metrics");
  },

  /**
   * Admin: Fetch tool logo automatically (discovery + fallback)
   */
  async fetchToolLogo(toolId: number): Promise<ToolResponse> {
    return apiFetch<ToolResponse>(`/admin/tools/${toolId}/fetch-logo`, {
      method: "POST",
    });
  },

  /**
   * Admin: Paste direct logo URL (downloaded server-side and stored)
   */
  async pasteToolLogoUrl(toolId: number, url: string): Promise<ToolResponse> {
    return apiFetch<ToolResponse>(`/admin/tools/${toolId}/paste-logo-url`, {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  },

  /**
   * Admin: Upload logo file (max 1 MB, PNG/JPG/WebP/SVG/ICO)
   */
  async uploadToolLogo(toolId: number, file: File): Promise<ToolResponse> {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<ToolResponse>(`/admin/tools/${toolId}/upload-logo`, {
      method: "POST",
      body: formData,
    });
  },

  /**
   * Public / Admin: Retrieve taxonomy domains and jobs definition
   */
  async getTaxonomy(): Promise<TaxonomyPayload> {
    return apiFetch<TaxonomyPayload>("/taxonomy");
  },

  /**
   * User: Permanently delete account and all associated data
   */
  async deleteAccount(): Promise<{ status: string; message: string }> {
    return apiFetch<{ status: string; message: string }>("/me", {
      method: "DELETE",
    });
  },
};
