"use client";

import Link from "next/link";
import { useState } from "react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import {
  Loader2,
  Plus,
  Pause,
  Play,
  Archive,
  Zap,
  Target,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { TopBar } from "@/components/layout/TopBar";
import { Sparkline } from "@/components/shared/Sparkline";
import { Metric } from "@/components/shared/Metric";
import { EmptyState } from "@/components/shared/EmptyState";
import { useCampaigns } from "@/lib/hooks/useCampaigns";
import { useConfig } from "@/lib/hooks/useConfig";
import { api, errorMessage } from "@/lib/api";
import type { Campaign, CampaignStatus } from "@/lib/types";
import { CreateCampaignDialog } from "@/components/campaigns/CreateCampaignDialog";

const STATUS_COLORS: Record<CampaignStatus, string> = {
  active: "text-[color:var(--accent)] border-[color:var(--accent)]",
  paused: "text-[color:var(--warn)] border-[color:var(--warn)]",
  completed: "text-text-dim border-border-strong",
  archived: "text-text-mute border-border",
};

export default function CampaignsPage() {
  const { data: campaigns, isLoading } = useCampaigns();
  const { data: config } = useConfig();
  const { mutate } = useSWRConfig();
  const [open, setOpen] = useState(false);
  const [tickingAll, setTickingAll] = useState(false);

  const targetCities =
    config?.target_cities
      ?.split(",")
      .map((c) => c.trim())
      .filter(Boolean) ?? [];

  const handleTickAll = async () => {
    setTickingAll(true);
    try {
      const res = await api.tickAllCampaigns();
      const totals = res.results.reduce(
        (acc, r) => ({
          prospected: acc.prospected + (r.prospected ?? 0),
          enriched: acc.enriched + (r.enriched ?? 0),
          drafted: acc.drafted + (r.drafted ?? 0),
          sent: acc.sent + (r.sent ?? 0),
        }),
        { prospected: 0, enriched: 0, drafted: 0, sent: 0 }
      );
      toast.success(
        `Ticked ${res.results.length} · prospected ${totals.prospected} · enriched ${totals.enriched} · drafted ${totals.drafted} · sent ${totals.sent}`
      );
      mutate("campaigns");
    } catch (e) {
      toast.error(`Tick failed: ${errorMessage(e)}`);
    } finally {
      setTickingAll(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="Campaigns"
        eyebrow="Helios / autonomous pipelines"
        subtitle={
          campaigns
            ? `${campaigns.filter((c) => c.status === "active").length} active · ${campaigns.length} total`
            : undefined
        }
        right={
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={handleTickAll}
              disabled={tickingAll}
            >
              {tickingAll ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5" strokeWidth={1.6} />
              )}
              Tick all
            </Button>
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="h-3.5 w-3.5" strokeWidth={1.8} />
              New campaign
            </Button>
          </>
        }
      />

      <div className="flex-1 px-8 py-6">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="border border-border bg-surface h-56 animate-pulse"
              />
            ))}
          </div>
        ) : campaigns && campaigns.length > 0 ? (
          <div className="stagger grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {campaigns.map((c, i) => (
              <div
                key={c.id}
                style={{ ["--i" as string]: i } as React.CSSProperties}
              >
                <CampaignCard campaign={c} />
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-border bg-surface">
            <EmptyState
              icon={Target}
              size="md"
              title="No campaigns yet"
              description="Create a campaign to let Hermes run end-to-end against a target audience without supervision. You can also ask the assistant in /chat to set one up."
              action={{
                label: "Create campaign",
                onClick: () => setOpen(true),
              }}
            />
            <div className="border-t border-border px-6 py-3 flex items-center justify-center gap-2 label-xs">
              <Sparkles
                className="h-3 w-3"
                style={{ color: "var(--accent)" }}
              />
              Or ask in{" "}
              <Link
                href="/chat"
                className="text-text-dim hover:text-[color:var(--accent)] transition-colors"
              >
                /chat
              </Link>
            </div>
          </div>
        )}
      </div>

      <CreateCampaignDialog
        open={open}
        onOpenChange={setOpen}
        targetCities={targetCities}
      />
    </div>
  );
}

function CampaignCard({ campaign: c }: { campaign: Campaign }) {
  const { mutate } = useSWRConfig();
  const [busy, setBusy] = useState(false);
  const m = c.metrics;

  const progress =
    c.total_lead_cap && c.total_lead_cap > 0
      ? Math.min(1, m.leads_total / c.total_lead_cap)
      : null;

  const update = async (next: CampaignStatus, e?: React.MouseEvent) => {
    e?.preventDefault();
    e?.stopPropagation();
    setBusy(true);
    try {
      await api.updateCampaign(c.id, { status: next });
      toast.success(`Campaign ${next}`);
      mutate("campaigns");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Link
      href={`/campaigns/${c.id}`}
      className="group relative block border border-border bg-surface hover:bg-surface-elevated hover:border-border-strong transition-[background,border-color] duration-[var(--dur-med)] overflow-hidden"
    >
      {/* Header row */}
      <div className="px-4 pt-4 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-text truncate">
              {c.name}
            </h3>
          </div>
          <div className="label-xs pt-1 truncate">
            {c.city} · {c.target}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={
              "label-xs px-1.5 py-0.5 border " + STATUS_COLORS[c.status]
            }
          >
            {c.status}
          </span>
          {c.autonomy === "review_drafts" && (
            <span className="label-xs border border-border px-1.5 py-0.5 text-text-mute">
              review
            </span>
          )}
        </div>
      </div>

      {/* Sparkline — sends per day, last 14 */}
      <div className="px-4 pt-4">
        <div className="flex items-center justify-between pb-1">
          <span className="label-xs">Sends · 14d</span>
          <span className="metric-sm text-text-dim">{m.sent_total}</span>
        </div>
        <Sparkline
          data={m.sends_last_14_days ?? []}
          width={280}
          height={28}
          className="w-full h-7"
        />
      </div>

      {/* Metric strip */}
      <div className="px-4 py-4 grid grid-cols-3 gap-3 border-t border-border mt-4">
        <Metric
          label="Today"
          value={`${m.sent_today}/${c.daily_send_cap}`}
          size="sm"
        />
        <Metric
          label="Reply"
          value={pct(m.reply_rate)}
          size="sm"
          tone={m.reply_rate > 0 ? "accent" : "mute"}
        />
        <Metric
          label="Book"
          value={pct(m.book_rate)}
          size="sm"
          tone={m.book_rate > 0 ? "accent" : "mute"}
        />
      </div>

      {/* Progress bar or spacer */}
      {progress !== null ? (
        <div className="h-1 w-full bg-surface-2">
          <div
            className="h-full transition-[width] duration-[var(--dur-slow)]"
            style={{
              width: `${progress * 100}%`,
              background:
                "linear-gradient(to right, var(--accent), color-mix(in oklch, var(--accent) 60%, var(--bg)))",
            }}
          />
        </div>
      ) : (
        <div className="h-1 w-full bg-surface-2" />
      )}

      {/* Hover action tray */}
      <div
        className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-[var(--dur-fast)]"
        onClick={(e) => e.preventDefault()}
      >
        {c.status === "active" && (
          <Button
            size="icon-xs"
            variant="outline"
            disabled={busy}
            onClick={(e) => update("paused", e)}
            title="Pause"
          >
            <Pause className="h-3 w-3" strokeWidth={1.8} />
          </Button>
        )}
        {c.status === "paused" && (
          <Button
            size="icon-xs"
            variant="outline"
            disabled={busy}
            onClick={(e) => update("active", e)}
            title="Resume"
          >
            <Play className="h-3 w-3" strokeWidth={1.8} />
          </Button>
        )}
        {c.status !== "archived" && (
          <Button
            size="icon-xs"
            variant="outline"
            disabled={busy}
            onClick={(e) => update("archived", e)}
            title="Archive"
          >
            <Archive className="h-3 w-3" strokeWidth={1.8} />
          </Button>
        )}
      </div>
    </Link>
  );
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}
