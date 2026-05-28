import { getToken, useAuthStore } from "./auth";
import type {
  Campaign,
  CampaignAutonomy,
  CampaignStatus,
  CampaignTickSummary,
  ChatConfirmResponse,
  ChatMessageResponse,
  ChatSession,
  ChatSessionSummary,
  ConfigMap,
  Lead,
  LeadStatus,
  LeadWithMessages,
  ReplyEntry,
  ReplyIntent,
  Stats,
  SubjectVariant,
  VariantStats,
} from "./types";

export interface CreateCampaignInput {
  name: string;
  city: string;
  target: string;
  sample_email?: string | null;
  autonomy: CampaignAutonomy;
  daily_send_cap: number;
  total_lead_cap?: number | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor() {
    super("Cannot reach API. Is the backend running?");
    this.name = "NetworkError";
  }
}

interface FetchOpts {
  method?: string;
  body?: unknown;
  skipAuth?: boolean;
}

export async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false } = opts;

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!skipAuth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new NetworkError();
  }

  if (resp.status === 401 && !skipAuth) {
    // Expired/invalid token — clear auth and let the dashboard layout
    // redirect to /login on next render. Still throw so callers abort.
    useAuthStore.getState().logout();
    throw new ApiError(401, "Session expired");
  }

  if (!resp.ok) {
    let message = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      message =
        typeof data?.detail === "string"
          ? data.detail
          : JSON.stringify(data?.detail ?? data);
    } catch {
      // ignore parse failure — keep default message
    }
    throw new ApiError(resp.status, message);
  }

  if (resp.status === 204) {
    return undefined as T;
  }

  return (await resp.json()) as T;
}

export const api = {
  login: (password: string) =>
    apiFetch<{ token: string }>("/auth/login", {
      method: "POST",
      body: { password },
      skipAuth: true,
    }),

  getStats: () => apiFetch<Stats>("/api/stats"),

  getLeads: (status?: LeadStatus, limit: number = 200) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    q.set("limit", String(limit));
    return apiFetch<Lead[]>(`/api/leads?${q.toString()}`);
  },

  getLead: (id: string) => apiFetch<LeadWithMessages>(`/api/leads/${id}`),

  approveLead: (id: string) =>
    apiFetch<{ ok?: boolean } & Record<string, unknown>>(`/api/leads/${id}/approve`, {
      method: "POST",
    }),

  skipLead: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/leads/${id}/skip`, { method: "POST" }),

  regenerateLead: (id: string) =>
    apiFetch<Record<string, unknown>>(`/api/leads/${id}/regenerate`, {
      method: "POST",
    }),

  editLead: (id: string, subject: string, body: string) =>
    apiFetch<Record<string, unknown>>(`/api/leads/${id}/edit`, {
      method: "POST",
      body: { subject, body },
    }),

  briefLead: (id: string) =>
    apiFetch<{ briefing_md: string }>(`/api/leads/${id}/brief`, { method: "POST" }),

  draftLinkedIn: (id: string, kind: "invite" | "dm") =>
    apiFetch<Record<string, unknown>>(`/api/leads/${id}/linkedin/draft`, {
      method: "POST",
      body: { kind },
    }),

  setLinkedInUrl: (id: string, linkedinUrl: string | null) =>
    apiFetch<Lead>(`/api/leads/${id}/linkedin-url`, {
      method: "PUT",
      body: { linkedin_url: linkedinUrl },
    }),

  getReplies: () => apiFetch<ReplyEntry[]>("/api/replies"),

  approveReply: (leadId: string) =>
    apiFetch<{ ok: boolean; message_id?: string }>(
      `/api/replies/${leadId}/approve`,
      { method: "POST" }
    ),

  editReply: (leadId: string, body: string) =>
    apiFetch<{ ok: boolean }>(`/api/replies/${leadId}/edit`, {
      method: "POST",
      body: { body },
    }),

  regenerateReply: (leadId: string) =>
    apiFetch<{ ok: boolean; intent: ReplyIntent }>(
      `/api/replies/${leadId}/regenerate`,
      { method: "POST" }
    ),

  getConfig: () => apiFetch<ConfigMap>("/api/config"),

  setConfig: (key: string, value: string) =>
    apiFetch<{ ok: boolean; key: string; value: string }>("/api/config", {
      method: "POST",
      body: { key, value },
    }),

  runProspect: (city: string, count?: number) =>
    apiFetch<{ inserted_ids: string[] }>("/api/run/prospect", {
      method: "POST",
      body: { city, count },
    }),

  runEnrichBatch: () =>
    apiFetch<{ enriched: number; dead: number; errors: string[] }>(
      "/api/run/enrich-batch",
      { method: "POST" }
    ),

  runDraftBatch: () =>
    apiFetch<{ drafted: number; errors: string[] }>("/api/run/draft-batch", {
      method: "POST",
    }),

  runPollReplies: () =>
    apiFetch<{
      checked: number;
      matched: number;
      unsubscribed: number;
      new_replies: number;
    }>("/api/run/poll-replies", { method: "POST" }),

  testSend: (leadId: string, to: string) =>
    apiFetch<{ sent: boolean; to: string; subject: string }>("/api/test-send", {
      method: "POST",
      body: { lead_id: leadId, to },
    }),

  listCampaigns: () => apiFetch<Campaign[]>("/api/campaigns"),

  getCampaign: (id: string) => apiFetch<Campaign>(`/api/campaigns/${id}`),

  getCampaignLeads: (id: string) =>
    apiFetch<Lead[]>(`/api/campaigns/${id}/leads`),

  createCampaign: (input: CreateCampaignInput) =>
    apiFetch<Campaign>("/api/campaigns", { method: "POST", body: input }),

  updateCampaign: (
    id: string,
    update: {
      status?: CampaignStatus;
      autonomy?: CampaignAutonomy;
      sample_email?: string | null;
    }
  ) =>
    apiFetch<Campaign>(`/api/campaigns/${id}`, {
      method: "PATCH",
      body: update,
    }),

  tickCampaign: (id: string) =>
    apiFetch<CampaignTickSummary>(`/api/campaigns/${id}/tick`, {
      method: "POST",
    }),

  tickAllCampaigns: () =>
    apiFetch<{ results: CampaignTickSummary[] }>("/api/campaigns/tick-all", {
      method: "POST",
    }),

  createChatSession: () =>
    apiFetch<ChatSession>("/api/chat/sessions", { method: "POST" }),

  listChatSessions: () =>
    apiFetch<ChatSessionSummary[]>("/api/chat/sessions"),

  getChatSession: (id: string) => apiFetch<ChatSession>(`/api/chat/${id}`),

  deleteChatSession: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/chat/${id}`, { method: "DELETE" }),

  sendChatMessage: (id: string, message: string) =>
    apiFetch<ChatMessageResponse>(`/api/chat/${id}/message`, {
      method: "POST",
      body: { message },
    }),

  confirmChatAction: (
    id: string,
    actionId: string,
    toolArgs?: Record<string, unknown>
  ) =>
    apiFetch<ChatConfirmResponse>(`/api/chat/${id}/confirm`, {
      method: "POST",
      body: { action_id: actionId, tool_args: toolArgs ?? null },
    }),

  cancelChatAction: (id: string) =>
    apiFetch<{ ok: boolean; had_pending: boolean }>(
      `/api/chat/${id}/cancel`,
      { method: "POST" }
    ),

  getVariantStats: () => apiFetch<VariantStats[]>("/api/variants/stats"),

  listVariants: () => apiFetch<SubjectVariant[]>("/api/variants"),

  createVariant: (data: { name: string; subject_prompt: string; is_active?: boolean }) =>
    apiFetch<SubjectVariant>("/api/variants", { method: "POST", body: data }),

  updateVariant: (
    id: string,
    patch: { name?: string; subject_prompt?: string; is_active?: boolean }
  ) => apiFetch<SubjectVariant>(`/api/variants/${id}`, { method: "PATCH", body: patch }),

  deleteVariant: (id: string) =>
    apiFetch<void>(`/api/variants/${id}`, { method: "DELETE" }),

  previewVariant: (id: string) =>
    apiFetch<{ preview: string }>(`/api/variants/${id}/preview`, { method: "POST" }),
};

/** Human-friendly message for toasts. Catch-all that preserves ApiError and
 * NetworkError wording. */
export function errorMessage(e: unknown): string {
  if (e instanceof NetworkError) return e.message;
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
