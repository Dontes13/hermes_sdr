"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Loader2, MailPlus, Sparkles, Search, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, errorMessage } from "@/lib/api";
import type { Stats } from "@/lib/types";

interface ActionButtonsProps {
  stats: Stats | undefined;
  targetCities: string[];
}

export function ActionButtons({ stats, targetCities }: ActionButtonsProps) {
  const { mutate } = useSWRConfig();
  const [prospectOpen, setProspectOpen] = useState(false);
  const [prospecting, setProspecting] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [polling, setPolling] = useState(false);

  const [prospectCity, setProspectCity] = useState(targetCities[0] ?? "Miami");
  const [prospectCount, setProspectCount] = useState(5);

  const refreshAll = () => {
    mutate("stats");
    mutate(
      (key) => typeof key === "string" && key.startsWith("leads"),
      undefined,
      { revalidate: true }
    );
  };

  const handleProspect = async () => {
    setProspecting(true);
    try {
      const res = await api.runProspect(prospectCity, prospectCount);
      toast.success(
        `Prospected ${res.inserted_ids.length} lead${res.inserted_ids.length === 1 ? "" : "s"} in ${prospectCity}`
      );
      setProspectOpen(false);
      refreshAll();
    } catch (e) {
      toast.error(`Prospect failed: ${errorMessage(e)}`);
    } finally {
      setProspecting(false);
    }
  };

  const handleEnrich = async () => {
    setEnriching(true);
    try {
      const res = await api.runEnrichBatch();
      toast.success(
        `Enriched ${res.enriched}, dead ${res.dead}${res.errors.length ? `, ${res.errors.length} errors` : ""}`
      );
      refreshAll();
    } catch (e) {
      toast.error(`Enrich batch failed: ${errorMessage(e)}`);
    } finally {
      setEnriching(false);
    }
  };

  const handleDraft = async () => {
    setDrafting(true);
    try {
      const res = await api.runDraftBatch();
      toast.success(
        `Drafted ${res.drafted}${res.errors.length ? `, ${res.errors.length} errors` : ""}`
      );
      refreshAll();
    } catch (e) {
      toast.error(`Draft batch failed: ${errorMessage(e)}`);
    } finally {
      setDrafting(false);
    }
  };

  const handlePoll = async () => {
    setPolling(true);
    try {
      const res = await api.runPollReplies();
      toast.success(
        `Checked ${res.checked} · matched ${res.matched} · new ${res.new_replies}${res.unsubscribed ? ` · unsub ${res.unsubscribed}` : ""}`
      );
      refreshAll();
      mutate("replies");
    } catch (e) {
      toast.error(`Poll failed: ${errorMessage(e)}`);
    } finally {
      setPolling(false);
    }
  };

  const newCount = stats?.counts?.new ?? 0;
  const enrichedCount = stats?.counts?.enriched ?? 0;

  return (
    <div className="border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
        <span>Actions</span>
        <span className="text-text-mute/60">· pipeline controls</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 divide-x divide-border">
        <ActionButton
          onClick={() => setProspectOpen(true)}
          icon={Search}
          label="Prospect"
          badge="city"
          loading={false}
          loadingText="Prospecting…"
        />
        <ActionButton
          onClick={handleEnrich}
          icon={Sparkles}
          label="Enrich"
          badge={newCount > 0 ? `${newCount} new` : "idle"}
          disabled={newCount === 0 || enriching}
          loading={enriching}
          loadingText="Enriching…"
        />
        <ActionButton
          onClick={handleDraft}
          icon={MailPlus}
          label="Draft"
          badge={enrichedCount > 0 ? `${enrichedCount} enriched` : "idle"}
          disabled={enrichedCount === 0 || drafting}
          loading={drafting}
          loadingText="Drafting…"
        />
        <ActionButton
          onClick={handlePoll}
          icon={Send}
          label="Poll replies"
          badge="manual"
          disabled={polling}
          loading={polling}
          loadingText="Polling…"
        />
      </div>

      <Dialog open={prospectOpen} onOpenChange={setProspectOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
              Run prospecting
            </DialogTitle>
            <DialogDescription className="text-sm text-text-dim">
              Discover new brokerages via Google Places and insert them as new
              leads.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-[11px] font-mono uppercase tracking-wider text-text-mute">
                City
              </Label>
              <Input
                value={prospectCity}
                onChange={(e) => setProspectCity(e.target.value)}
                placeholder="Miami, Miami Beach, Austin…"
                className="font-mono"
                autoFocus
              />
              {targetCities.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute pt-0.5">
                    quick pick:
                  </span>
                  {targetCities.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setProspectCity(c)}
                      className={
                        c === prospectCity
                          ? "inline-flex items-center border border-[color:var(--accent)] bg-surface-2 px-2 py-0.5 text-xs font-mono text-text"
                          : "inline-flex items-center border border-border bg-surface-2 px-2 py-0.5 text-xs font-mono text-text-dim hover:border-border-strong hover:text-text"
                      }
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-[11px] font-mono uppercase tracking-wider text-text-mute">
                Count
              </Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={prospectCount}
                onChange={(e) =>
                  setProspectCount(
                    Math.min(20, Math.max(1, Number(e.target.value) || 5))
                  )
                }
                className="font-mono"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setProspectOpen(false)}
              disabled={prospecting}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleProspect} disabled={prospecting || !prospectCity}>
              {prospecting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Prospecting…
                </>
              ) : (
                <>Run →</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface ActionButtonCellProps {
  onClick: () => void;
  icon: React.ElementType;
  label: string;
  badge?: string;
  disabled?: boolean;
  loading?: boolean;
  loadingText?: string;
}

function ActionButton({
  onClick,
  icon: Icon,
  label,
  badge,
  disabled,
  loading,
  loadingText,
}: ActionButtonCellProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="group text-left px-4 py-3 transition-colors hover:bg-surface-2 disabled:hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <div className="flex items-center gap-2 text-text-dim group-hover:text-text transition-colors">
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Icon className="h-3.5 w-3.5" strokeWidth={1.6} />
        )}
        <span className="font-mono text-[11px] uppercase tracking-wider font-semibold">
          {loading ? loadingText ?? label : label}
        </span>
      </div>
      {badge && (
        <div className="pl-[22px] pt-0.5 font-mono text-[10px] text-text-mute">
          {badge}
        </div>
      )}
    </button>
  );
}
