export type LeadStatus =
  | "new"
  | "enriched"
  | "drafted"
  | "approved"
  | "sent"
  | "replied"
  | "booked"
  | "dead"
  | "unsubscribed";

export type HookTier = 1 | 2 | 3 | 4 | 5;

export type ReplyIntent =
  | "interested"
  | "question"
  | "objection"
  | "booking"
  | "negative"
  | "other";

export const LEAD_STATUSES: LeadStatus[] = [
  "new",
  "enriched",
  "drafted",
  "approved",
  "sent",
  "replied",
  "booked",
  "dead",
  "unsubscribed",
];

export const HOOK_TIER_NAMES: Record<HookTier, string> = {
  1: "Brand/Slogan",
  2: "Website Intel",
  3: "Reputation",
  4: "Market Context",
  5: "Baseline",
};

export const REPLY_INTENTS: ReplyIntent[] = [
  "interested",
  "question",
  "objection",
  "booking",
  "negative",
  "other",
];

export type LinkedInState =
  | "invite_sent"
  | "connected"
  | "declined"
  | "withdrawn";

export type MessageChannel = "email" | "linkedin_invite" | "linkedin_dm";
export type MessageProvider = "agentmail" | "unipile";

export interface Lead {
  id: string;
  company: string;
  city: string;
  website: string | null;
  email: string | null;
  owner_name: string | null;
  phone: string | null;
  google_rating: number | null;
  google_reviews: number | null;
  intel_json: Record<string, unknown>;
  status: LeadStatus;
  briefing_md: string | null;
  latest_hook_tier: HookTier | null;
  linkedin_url?: string | null;
  linkedin_state?: LinkedInState | null;
  linkedin_followup_eligible_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  lead_id: string;
  direction: "outbound" | "inbound";
  channel?: MessageChannel;
  provider?: MessageProvider;
  subject: string | null;
  body: string;
  hook_tier_used: HookTier | null;
  hook_text: string | null;
  hook_rationale: string | null;
  provider_msg_id: string | null;
  provider_thread_id: string | null;
  sent_at: string | null;
  is_test?: boolean;
  created_at: string;
}

export interface LeadWithMessages {
  lead: Lead;
  messages: Message[];
}

export interface ReplyEntry {
  lead: Lead;
  latest_inbound: Message | null;
  pending_reply_draft: Message | null;
  is_test?: boolean;
}

export interface Stats {
  counts: Record<LeadStatus, number>;
  hook_tiers_sent: Record<string, number>;
  last_run_at: string | null;
  reply_drafts_pending: number;
  sent_today: number;
  sent_week: number;
  inbound_week: number;
  recent_outbound: RecentOutbound[];
  recent_inbound: RecentInbound[];
}

export interface RecentOutbound {
  id: string;
  lead_id: string;
  subject: string | null;
  sent_at: string;
  hook_tier_used: HookTier | null;
}

export interface RecentInbound {
  id: string;
  lead_id: string;
  subject: string | null;
  created_at: string;
}

export interface ConfigMap {
  target_cities?: string;
  calendly_link?: string;
  sender_name?: string;
  sender_title?: string;
  daily_lead_cap?: string;
}

export type CampaignStatus = "active" | "paused" | "completed" | "archived";
export type CampaignAutonomy = "full" | "review_drafts";

export interface CampaignMetrics {
  leads_total: number;
  status_counts: Partial<Record<LeadStatus, number>>;
  sent_total: number;
  sent_today: number;
  replied: number;
  booked: number;
  reply_rate: number;
  book_rate: number;
  sends_last_14_days: number[];
}

export interface Campaign {
  id: string;
  name: string;
  city: string;
  target: string;
  sample_email: string | null;
  status: CampaignStatus;
  autonomy: CampaignAutonomy;
  daily_send_cap: number;
  total_lead_cap: number | null;
  tick_running_at: string | null;
  created_at: string;
  updated_at: string;
  metrics: CampaignMetrics;
}

export type ChatRole = "user" | "assistant" | "tool" | "system" | "summary";

export interface ChatTurn {
  role: ChatRole;
  content?: string;
  name?: string;
  result?: unknown;
  at?: string;
}

export interface PendingAction {
  action_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  created_at: string;
}

export interface ChatSession {
  id: string;
  messages: ChatTurn[];
  pending_action: PendingAction | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionSummary {
  id: string;
  preview: string;
  message_count: number;
  has_pending: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageResponse {
  reply: string;
  pending_action: PendingAction | null;
  messages: ChatTurn[];
}

export interface ChatConfirmResponse {
  reply: string;
  result: Record<string, unknown>;
  messages: ChatTurn[];
}

export interface CampaignTickSummary {
  campaign_id: string;
  name?: string;
  prospected?: number;
  enriched?: number;
  dead?: number;
  drafted?: number;
  sent?: number;
  errors?: string[];
  skipped?: string;
  skipped_global_cap?: boolean;
  marked_completed?: boolean;
}

export const CONFIG_KEYS = [
  "target_cities",
  "calendly_link",
  "sender_name",
  "sender_title",
  "daily_lead_cap",
] as const satisfies readonly (keyof ConfigMap)[];

export type ConfigKey = (typeof CONFIG_KEYS)[number];
