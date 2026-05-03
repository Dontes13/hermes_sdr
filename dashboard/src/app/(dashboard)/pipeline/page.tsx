"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Inbox, Plus, RefreshCw, TrendingUp, Zap } from "lucide-react";

import { TopBar } from "@/components/layout/TopBar";
import { HookTierChart } from "@/components/pipeline/HookTierChart";
import { PipelineSteps } from "@/components/pipeline/PipelineSteps";
import { PipelineFunnel } from "@/components/pipeline/PipelineFunnel";
import { ActivityFeed } from "@/components/pipeline/ActivityFeed";
import { BentoGrid, BentoCard } from "@/components/shared/BentoGrid";
import { Metric } from "@/components/shared/Metric";
import { Skeleton } from "@/components/ui/skeleton";
import { useStats } from "@/lib/hooks/useStats";
import { useConfig } from "@/lib/hooks/useConfig";
import { formatRelative } from "@/lib/utils";
import { useSWRConfig } from "swr";

export default function PipelinePage() {
  const { data: stats, isLoading } = useStats();
  const { data: config } = useConfig();
  const { mutate } = useSWRConfig();
  const router = useRouter();

  const targetCities = (config?.target_cities ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const replyPending = stats?.reply_drafts_pending ?? 0;
  const sentWeek = stats?.sent_week ?? 0;
  const sentToday = stats?.sent_today ?? 0;
  const inboundWeek = stats?.inbound_week ?? 0;
  const counts = stats?.counts;

  const refreshAll = () => {
    mutate("stats");
    mutate(
      (key) => typeof key === "string" && key.startsWith("leads"),
      undefined,
      { revalidate: true }
    );
  };

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="Pipeline"
        eyebrow="Helios / Overview"
        right={
          <div className="flex items-center gap-3">
            <span className="text-[12px] text-text-mute flex items-center gap-1.5">
              {stats?.last_run_at
                ? `Last updated ${formatRelative(stats.last_run_at)}`
                : "No polls yet"}
              <button
                type="button"
                onClick={refreshAll}
                className="text-text-mute hover:text-text transition-colors"
                title="Refresh"
              >
                <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.6} />
              </button>
            </span>
            <button
              type="button"
              onClick={() => router.push("/campaigns")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[13px] font-medium text-white transition-colors"
              style={{ background: "var(--accent)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--accent-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--accent)")
              }
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={2} />
              New Campaign
            </button>
          </div>
        }
      />

      <div className="flex-1 px-8 py-6 space-y-5">
        <PipelineSteps stats={stats} targetCities={targetCities} />

        {/* Hero row */}
        <BentoGrid gap={4}>
          <BentoCard
            span={5}
            eyebrow="This week"
            action={
              <a
                href="#recent-activity"
                className="label-xs flex items-center gap-1 hover:text-text-dim transition-colors"
                title="Jump to recent activity"
                style={{ color: "var(--accent)" }}
              >
                <TrendingUp
                  className="h-3.5 w-3.5"
                  strokeWidth={1.6}
                />
                View log
              </a>
            }
          >
            {isLoading && !stats ? (
              <HeroSkeleton />
            ) : (
              <div className="space-y-4">
                <Metric
                  value={String(sentWeek).padStart(2, "0")}
                  size="xl"
                  tone={sentWeek > 0 ? "accent" : "mute"}
                  sub="emails sent · last 7 days"
                />
                <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
                  <Metric
                    label="Inbound"
                    value={inboundWeek}
                    size="sm"
                    sub="responses"
                  />
                  <Metric
                    label="Replied"
                    value={counts?.replied ?? 0}
                    size="sm"
                    sub="leads"
                  />
                  <Metric
                    label="Booked"
                    value={counts?.booked ?? 0}
                    size="sm"
                    tone="accent"
                    sub="meetings"
                  />
                </div>
              </div>
            )}
          </BentoCard>

          <BentoCard
            span={4}
            eyebrow="Replies pending"
            action={<Inbox className="h-3.5 w-3.5 text-text-mute" strokeWidth={1.6} />}
            interactive
            className="group"
          >
            <Link
              href="/replies"
              className="flex items-end justify-between h-full"
            >
              <div>
                <div
                  className="metric-xl"
                  style={{
                    color:
                      replyPending > 0
                        ? "var(--accent)"
                        : "var(--text-mute)",
                  }}
                >
                  {String(replyPending).padStart(2, "0")}
                </div>
                <div className="pt-2 label-xs">
                  {replyPending > 0 ? "awaiting approval" : "inbox quiet"}
                </div>
              </div>
              <span className="label-xs flex items-center gap-1 group-hover:text-text-dim transition-colors"
                    style={{ color: "var(--accent)" }}>
                Review <ArrowRight className="h-3 w-3" />
              </span>
            </Link>
          </BentoCard>

          <BentoCard
            span={3}
            eyebrow="Today"
            action={<Zap className="h-3.5 w-3.5 text-text-mute" strokeWidth={1.6} />}
          >
            <div className="space-y-3">
              <Metric
                value={sentToday}
                size="lg"
                tone={sentToday > 0 ? "default" : "mute"}
                sub="sent today"
              />
              <div className="pt-3 border-t border-border">
                <Metric
                  label="Drafts queued"
                  value={counts?.drafted ?? 0}
                  size="sm"
                />
              </div>
            </div>
          </BentoCard>
        </BentoGrid>

        {/* Funnel + Hook tiers */}
        <BentoGrid gap={4}>
          <BentoCard span={7} eyebrow="Pipeline funnel">
            {isLoading && !stats ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <PipelineFunnel
                counts={
                  counts ?? {
                    new: 0,
                    enriched: 0,
                    drafted: 0,
                    approved: 0,
                    sent: 0,
                    replied: 0,
                    booked: 0,
                    dead: 0,
                    unsubscribed: 0,
                  }
                }
              />
            )}
          </BentoCard>

          <BentoCard span={5} eyebrow="Replies by hook tier">
            <HookTierChart tiersSent={stats?.hook_tiers_sent ?? {}} />
          </BentoCard>
        </BentoGrid>

        {/* Activity feed */}
        <div id="recent-activity" className="scroll-mt-24" />
        <BentoGrid gap={4}>
          <BentoCard
            span={12}
            eyebrow="Recent activity"
            action={
              <Link
                href="/leads"
                className="text-[12px] text-text-mute hover:text-text transition-colors"
              >
                View all
              </Link>
            }
          >
            {isLoading && !stats ? (
              <div className="space-y-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : (
              <ActivityFeed
                recentOutbound={stats?.recent_outbound ?? []}
                recentInbound={stats?.recent_inbound ?? []}
              />
            )}
          </BentoCard>
        </BentoGrid>
      </div>
    </div>
  );
}

function HeroSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-12 w-32" />
      <Skeleton className="h-3 w-48" />
      <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    </div>
  );
}
