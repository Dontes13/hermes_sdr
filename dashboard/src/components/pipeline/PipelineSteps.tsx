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
import { cn } from "@/lib/utils";
import type { Stats } from "@/lib/types";

interface PipelineStepsProps {
  stats: Stats | undefined;
  targetCities: string[];
}

const STEPS = [
  { key: "prospect", icon: Search, title: "Prospect", description: "Find new leads" },
  { key: "enrich", icon: Sparkles, title: "Enrich", description: "Add context" },
  { key: "draft", icon: MailPlus, title: "Draft", description: "Create emails" },
  { key: "poll", icon: Send, title: "Poll Replies", description: "Check responses" },
] as const;

export function PipelineSteps({ stats, targetCities }: PipelineStepsProps) {
  const { mutate } = useSWRConfig();
  const [prospectOpen, setProspectOpen] = useState(false);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
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

  const setLoad = (key: string, val: boolean) =>
    setLoading((prev) => ({ ...prev, [key]: val }));

  const handleProspect = async () => {
    setLoad("prospect", true);
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
      setLoad("prospect", false);
    }
  };

  const handleEnrich = async () => {
    setLoad("enrich", true);
    try {
      const res = await api.runEnrichBatch();
      toast.success(
        `Enriched ${res.enriched}, dead ${res.dead}${res.errors.length ? `, ${res.errors.length} errors` : ""}`
      );
      refreshAll();
    } catch (e) {
      toast.error(`Enrich batch failed: ${errorMessage(e)}`);
    } finally {
      setLoad("enrich", false);
    }
  };

  const handleDraft = async () => {
    setLoad("draft", true);
    try {
      const res = await api.runDraftBatch();
      toast.success(
        `Drafted ${res.drafted}${res.errors.length ? `, ${res.errors.length} errors` : ""}`
      );
      refreshAll();
    } catch (e) {
      toast.error(`Draft batch failed: ${errorMessage(e)}`);
    } finally {
      setLoad("draft", false);
    }
  };

  const handlePoll = async () => {
    setLoad("poll", true);
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
      setLoad("poll", false);
    }
  };

  const newCount = stats?.counts?.new ?? 0;
  const enrichedCount = stats?.counts?.enriched ?? 0;

  const isDisabled: Record<string, boolean> = {
    prospect: false,
    enrich: newCount === 0,
    draft: enrichedCount === 0,
    poll: false,
  };

  const handlers: Record<string, () => void> = {
    prospect: () => setProspectOpen(true),
    enrich: handleEnrich,
    draft: handleDraft,
    poll: handlePoll,
  };

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STEPS.map((step) => {
          const Icon = step.icon;
          const isLoading = loading[step.key] ?? false;
          const disabled = isDisabled[step.key] || isLoading;
          const active = !isDisabled[step.key];

          return (
            <button
              key={step.key}
              type="button"
              onClick={handlers[step.key]}
              disabled={disabled}
              className={cn(
                "flex flex-col gap-3 p-4 rounded-xl border border-border bg-surface text-left",
                "hover:border-[color:var(--accent)] hover:shadow-md",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-all duration-[var(--dur-med)]"
              )}
            >
              <div
                className="h-9 w-9 rounded-lg flex items-center justify-center"
                style={{ background: active ? "var(--accent)" : "var(--surface-2)" }}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                ) : (
                  <Icon
                    className="h-4 w-4"
                    strokeWidth={1.8}
                    style={{ color: active ? "white" : "var(--text-mute)" }}
                  />
                )}
              </div>
              <div>
                <div className="text-[14px] font-semibold text-text">
                  {isLoading ? `${step.title}…` : step.title}
                </div>
                <div className="text-[12px] text-text-mute mt-0.5">
                  {step.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <Dialog open={prospectOpen} onOpenChange={setProspectOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Run prospecting</DialogTitle>
            <DialogDescription>
              Discover new brokerages via Google Places and insert them as new leads.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>City</Label>
              <Input
                value={prospectCity}
                onChange={(e) => setProspectCity(e.target.value)}
                placeholder="Miami, Miami Beach, Austin…"
                autoFocus
              />
              {targetCities.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="text-[10px] text-text-mute pt-0.5">quick pick:</span>
                  {targetCities.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setProspectCity(c)}
                      className={cn(
                        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs transition-colors",
                        c === prospectCity
                          ? "border-[color:var(--accent)] bg-[color:var(--accent)]/5 text-text"
                          : "border-border bg-surface-2 text-text-dim hover:border-border-strong hover:text-text"
                      )}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Count</Label>
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
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setProspectOpen(false)}
              disabled={loading.prospect}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleProspect}
              disabled={loading.prospect || !prospectCity}
            >
              {loading.prospect ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Prospecting…
                </>
              ) : (
                "Run →"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
