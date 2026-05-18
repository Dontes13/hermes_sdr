"use client";

import Link from "next/link";
import { use, useMemo, useState } from "react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import {
  ArrowLeft,
  Loader2,
  Pause,
  Play,
  Archive,
  Zap,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { BentoGrid, BentoCard } from "@/components/shared/BentoGrid";
import { Metric } from "@/components/shared/Metric";
import { PipelineFunnel } from "@/components/pipeline/PipelineFunnel";
import { useCampaign, useCampaignLeads } from "@/lib/hooks/useCampaigns";
import { api, errorMessage } from "@/lib/api";
import { costPerLead, formatUsd } from "@/lib/cost";
import type { CampaignStatus, Lead, LeadStatus } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

const STATUS_COLORS: Record<CampaignStatus, string> = {
  active: "text-[color:var(--accent)] border-[color:var(--accent)]",
  paused: "text-[color:var(--warn)] border-[color:var(--warn)]",
  completed: "text-text-dim border-border-strong",
  archived: "text-text-mute border-border",
};

const LEAD_FILTER_OPTIONS: ("all" | LeadStatus)[] = [
  "all",
  "new",
  "enriched",
  "drafted",
  "sent",
  "replied",
  "booked",
  "dead",
];

export default function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: campaign, isLoading, mutate: mutateCampaign } = useCampaign(id);
  const { data: leads } = useCampaignLeads(id);
  const { mutate } = useSWRConfig();
  const [busy, setBusy] = useState<string | null>(null);
  const [sampleOpen, setSampleOpen] = useState(false);
  const [leadFilter, setLeadFilter] = useState<"all" | LeadStatus>("all");

  const filteredLeads = useMemo(() => {
    if (!leads) return [];
    if (leadFilter === "all") return leads;
    return leads.filter((l) => l.status === leadFilter);
  }, [leads, leadFilter]);

  if (isLoading || !campaign) {
    return (
      <div className="p-8 label-xs">Loading…</div>
    );
  }

  const m = campaign.metrics;

  const setStatus = async (next: CampaignStatus) => {
    setBusy(next);
    try {
      await api.updateCampaign(id, { status: next });
      toast.success(`Campaign ${next}`);
      mutateCampaign();
      mutate("campaigns");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const handleTick = async () => {
    setBusy("tick");
    try {
      const res = await api.tickCampaign(id);
      if (res.skipped) {
        toast.info(`Skipped: ${res.skipped}`);
      } else {
        toast.success(
          `prospected ${res.prospected ?? 0} · enriched ${res.enriched ?? 0} · drafted ${res.drafted ?? 0} · sent ${res.sent ?? 0}`
        );
      }
      mutateCampaign();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const todayProgress =
    campaign.daily_send_cap > 0 ? m.sent_today / campaign.daily_send_cap : 0;
  const budgetSpent = m.leads_total * costPerLead();
  const budgetRemaining =
    campaign.total_lead_cap !== null
      ? Math.max(0, (campaign.total_lead_cap - m.leads_total) * costPerLead())
      : null;
  const budgetTotal =
    campaign.total_lead_cap !== null
      ? campaign.total_lead_cap * costPerLead()
      : null;

  return (
    <div className="flex flex-col min-h-screen">
      {/* Sticky header */}
      <div className="sticky top-0 z-20 bg-bg/90 backdrop-blur border-b border-border">
        <div className="px-8 pt-4 pb-2">
          <Link
            href="/campaigns"
            className="inline-flex items-center gap-1 label-xs hover:text-text-dim transition-colors"
          >
            <ArrowLeft className="h-3 w-3" /> Campaigns
          </Link>
        </div>
        <div className="px-8 pb-4 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-text tracking-tight truncate">
                {campaign.name}
              </h1>
              <span
                className={
                  "label-xs px-1.5 py-0.5 border " +
                  STATUS_COLORS[campaign.status]
                }
              >
                {campaign.status}
              </span>
              <span className="label-xs px-1.5 py-0.5 border border-border text-text-mute">
                {campaign.autonomy === "full" ? "auto-send" : "review drafts"}
              </span>
            </div>
            <div className="label-xs pt-1.5">
              {campaign.city} · {campaign.target}
            </div>
          </div>

          <div className="flex gap-1.5 shrink-0">
            <Button
              size="sm"
              variant="outline"
              onClick={handleTick}
              disabled={busy === "tick"}
            >
              {busy === "tick" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5" strokeWidth={1.6} />
              )}
              Tick now
            </Button>
            {campaign.status === "active" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setStatus("paused")}
                disabled={!!busy}
              >
                <Pause className="h-3.5 w-3.5" strokeWidth={1.8} /> Pause
              </Button>
            ) : campaign.status === "paused" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setStatus("active")}
                disabled={!!busy}
              >
                <Play className="h-3.5 w-3.5" strokeWidth={1.8} /> Resume
              </Button>
            ) : null}
            {campaign.status !== "archived" && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setStatus("archived")}
                disabled={!!busy}
              >
                <Archive className="h-3.5 w-3.5" strokeWidth={1.8} /> Archive
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 px-8 py-6 space-y-5">
        {/* Row 1 — funnel + budget */}
        <BentoGrid gap={4}>
          <BentoCard span={8} eyebrow="Campaign funnel">
            <PipelineFunnel counts={m.status_counts as Record<LeadStatus, number>} />
          </BentoCard>

          <BentoCard span={4} eyebrow="Budget">
            <div className="space-y-4">
              <Metric
                value={formatUsd(budgetSpent)}
                size="lg"
                tone={budgetSpent > 0 ? "default" : "mute"}
                sub="spent · estimate"
              />
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
                {budgetRemaining !== null ? (
                  <Metric
                    label="Remaining"
                    value={formatUsd(budgetRemaining)}
                    size="sm"
                    sub={`of ${formatUsd(budgetTotal!)}`}
                  />
                ) : (
                  <Metric
                    label="Per day"
                    value={formatUsd(campaign.daily_send_cap * costPerLead())}
                    size="sm"
                    sub="at cap"
                  />
                )}
                <Metric
                  label="Per lead"
                  value={formatUsd(costPerLead())}
                  size="sm"
                />
              </div>
            </div>
          </BentoCard>
        </BentoGrid>

        {/* Row 2 — today + response + meta */}
        <BentoGrid gap={4}>
          <BentoCard span={4} eyebrow="Today">
            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <span className="metric-lg">
                  {m.sent_today}
                  <span className="metric-sm text-text-mute ml-1">
                    /{campaign.daily_send_cap}
                  </span>
                </span>
                <span className="label-xs">sent</span>
              </div>
              <div className="h-1.5 bg-surface-2">
                <div
                  className="h-full transition-[width]"
                  style={{
                    width: `${Math.min(100, todayProgress * 100)}%`,
                    background: "var(--accent)",
                  }}
                />
              </div>
              <div className="label-xs pt-1">
                {todayProgress >= 1
                  ? "cap reached · paused until tomorrow"
                  : `${Math.round((1 - todayProgress) * campaign.daily_send_cap)} remaining today`}
              </div>
            </div>
          </BentoCard>

          <BentoCard span={4} eyebrow="Response">
            <div className="grid grid-cols-2 gap-3">
              <Metric
                label="Reply rate"
                value={pct(m.reply_rate)}
                size="md"
                tone={m.reply_rate > 0 ? "accent" : "mute"}
                sub={`${m.replied} replied`}
              />
              <Metric
                label="Book rate"
                value={pct(m.book_rate)}
                size="md"
                tone={m.book_rate > 0 ? "accent" : "mute"}
                sub={`${m.booked} booked`}
              />
            </div>
          </BentoCard>

          <BentoCard span={4} eyebrow="Meta">
            <dl className="space-y-1.5 text-sm">
              <MetaRow label="City" value={campaign.city} />
              <MetaRow label="Target" value={campaign.target} />
              <MetaRow
                label="Total cap"
                value={campaign.total_lead_cap ?? "unlimited"}
              />
              <MetaRow
                label="Created"
                value={formatRelative(campaign.created_at)}
              />
              <MetaRow
                label="Autonomy"
                value={
                  campaign.autonomy === "full" ? "auto-send" : "review drafts"
                }
              />
            </dl>
          </BentoCard>
        </BentoGrid>

        {/* Sample email — collapsible */}
        {campaign.sample_email && (
          <BentoCard
            eyebrow="Sample email"
            span={12}
            action={
              <button
                type="button"
                onClick={() => setSampleOpen((v) => !v)}
                className="label-xs flex items-center gap-1 hover:text-text-dim transition-colors"
              >
                {sampleOpen ? "Hide" : "Show"}
                {sampleOpen ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>
            }
            bodyClassName={sampleOpen ? "p-0" : "p-0"}
          >
            {sampleOpen ? (
              <pre className="p-4 whitespace-pre-wrap font-mono text-sm text-text-dim max-h-80 overflow-auto">
                {campaign.sample_email}
              </pre>
            ) : (
              <div className="px-4 py-3 label-xs">
                {campaign.sample_email.length} characters · click Show to expand
              </div>
            )}
          </BentoCard>
        )}

        {/* Leads list */}
        <BentoCard
          eyebrow="Leads"
          title={<span className="label-sm">({leads?.length ?? 0})</span>}
          span={12}
          bodyClassName="p-0"
        >
          {/* Filter chip row */}
          <div className="px-4 py-2.5 border-b border-border flex gap-1.5 flex-wrap">
            {LEAD_FILTER_OPTIONS.map((opt) => {
              const count =
                opt === "all"
                  ? leads?.length ?? 0
                  : (m.status_counts as Partial<Record<LeadStatus, number>>)[
                      opt
                    ] ?? 0;
              const active = leadFilter === opt;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setLeadFilter(opt)}
                  className={
                    "label-xs px-2 py-1 border transition-colors " +
                    (active
                      ? "border-[color:var(--accent)] text-text bg-surface-2"
                      : "border-border text-text-mute hover:text-text-dim hover:border-border-strong")
                  }
                >
                  {opt} · {count}
                </button>
              );
            })}
          </div>

          {filteredLeads.length > 0 ? (
            <div className="divide-y divide-border">
              {filteredLeads.map((l) => (
                <LeadRow key={l.id} lead={l} />
              ))}
            </div>
          ) : (
            <div className="p-6 text-center label-xs">
              {leadFilter === "all"
                ? "No leads yet. Tick the campaign to prospect."
                : `No leads with status "${leadFilter}"`}
            </div>
          )}
        </BentoCard>
      </div>
    </div>
  );
}

function MetaRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="label-xs">{label}</dt>
      <dd className="text-text text-xs truncate">{value}</dd>
    </div>
  );
}

function LeadRow({ lead: l }: { lead: Lead }) {
  return (
    <Link
      href={`/leads/${l.id}`}
      className="block px-4 py-2.5 hover:bg-surface-2/50 transition-colors"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm text-text truncate">{l.company}</div>
          <div className="label-xs pt-0.5 truncate">
            {l.email ?? "no email"} · {l.city}
          </div>
        </div>
        <span className="label-xs border border-border px-1.5 py-0.5 text-text-dim shrink-0">
          {l.status}
        </span>
      </div>
    </Link>
  );
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}
