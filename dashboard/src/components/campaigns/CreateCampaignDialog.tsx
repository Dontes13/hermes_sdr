"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, errorMessage } from "@/lib/api";
import { estimateCampaignCost, formatUsd } from "@/lib/cost";
import type { CampaignAutonomy } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  targetCities: string[];
}

export function CreateCampaignDialog({ open, onOpenChange, targetCities }: Props) {
  const { mutate } = useSWRConfig();

  const [name, setName] = useState("");
  const [city, setCity] = useState(targetCities[0] ?? "");
  const [target, setTarget] = useState("");
  const [sampleEmail, setSampleEmail] = useState("");
  const [autonomy, setAutonomy] = useState<CampaignAutonomy>("full");
  const [dailySendCap, setDailySendCap] = useState(15);
  const [totalLeadCap, setTotalLeadCap] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setName("");
    setCity(targetCities[0] ?? "");
    setTarget("");
    setSampleEmail("");
    setAutonomy("full");
    setDailySendCap(15);
    setTotalLeadCap("");
  };

  const handleSubmit = async () => {
    if (!name.trim() || !city.trim() || !target.trim()) {
      toast.error("Name, city, and target are required");
      return;
    }
    setSubmitting(true);
    try {
      const campaign = await api.createCampaign({
        name: name.trim(),
        city: city.trim(),
        target: target.trim(),
        sample_email: sampleEmail.trim() || null,
        autonomy,
        daily_send_cap: dailySendCap,
        total_lead_cap: totalLeadCap ? Number(totalLeadCap) : null,
      });
      toast.success(`Campaign "${campaign.name}" created`);
      mutate("campaigns");
      onOpenChange(false);
      reset();
    } catch (e) {
      toast.error(`Create failed: ${errorMessage(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
            New campaign
          </DialogTitle>
          <DialogDescription className="text-sm text-text-dim">
            Hermes will prospect, enrich, draft, and (if autonomy=full) send
            for this (city, target) pair on every cron tick.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto pr-1">
          <Field label="Name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Q2 Miami Coffee Shops"
              autoFocus
              className="font-mono"
            />
          </Field>

          <Field label="City">
            <Input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Miami, Austin, Brooklyn…"
              className="font-mono"
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
                    onClick={() => setCity(c)}
                    className={
                      c === city
                        ? "inline-flex items-center border border-[color:var(--accent)] bg-surface-2 px-2 py-0.5 text-xs font-mono text-text"
                        : "inline-flex items-center border border-border bg-surface-2 px-2 py-0.5 text-xs font-mono text-text-dim hover:border-border-strong hover:text-text"
                    }
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </Field>

          <Field label="Target audience" hint="fed verbatim to Google Places as '{target} in {city}'">
            <Textarea
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              rows={2}
              placeholder='e.g. "small real estate brokerages", "boutique coffee shops", "independent dental practices"'
              className="font-mono text-sm"
            />
          </Field>

          <Field label="Sample email (optional)" hint="tone reference only, hook-tier rules still apply">
            <Textarea
              value={sampleEmail}
              onChange={(e) => setSampleEmail(e.target.value)}
              rows={5}
              placeholder="Paste an email whose voice you want Hermes to match."
              className="font-mono text-sm"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Autonomy">
              <div className="flex border border-border">
                <AutonomyButton
                  active={autonomy === "full"}
                  onClick={() => setAutonomy("full")}
                  label="Full"
                  sub="auto-send"
                />
                <AutonomyButton
                  active={autonomy === "review_drafts"}
                  onClick={() => setAutonomy("review_drafts")}
                  label="Review"
                  sub="drafts only"
                />
              </div>
            </Field>

            <Field label="Daily send cap">
              <Input
                type="number"
                min={1}
                max={500}
                value={dailySendCap}
                onChange={(e) =>
                  setDailySendCap(
                    Math.min(500, Math.max(1, Number(e.target.value) || 15))
                  )
                }
                className="font-mono"
              />
            </Field>
          </div>

          <Field label="Total lead cap (optional)" hint="blank = run until stopped">
            <Input
              type="number"
              min={1}
              max={5000}
              value={totalLeadCap}
              onChange={(e) => setTotalLeadCap(e.target.value)}
              placeholder="e.g. 200"
              className="font-mono"
            />
          </Field>

          <CostEstimate
            totalLeadCap={totalLeadCap ? Number(totalLeadCap) : null}
            dailySendCap={dailySendCap}
          />
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Creating…
              </>
            ) : (
              <>Create →</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-[11px] font-mono uppercase tracking-wider text-text-mute">
        {label}
      </Label>
      {children}
      {hint && (
        <div className="font-mono text-[10px] text-text-mute">{hint}</div>
      )}
    </div>
  );
}

function CostEstimate({
  totalLeadCap,
  dailySendCap,
}: {
  totalLeadCap: number | null;
  dailySendCap: number;
}) {
  const est = estimateCampaignCost(totalLeadCap, dailySendCap);
  return (
    <div className="border border-border bg-surface-2/50 px-3 py-2">
      <div className="flex items-baseline justify-between">
        <Label className="text-[11px] font-mono uppercase tracking-wider text-text-mute">
          Estimated cost
        </Label>
        <span className="font-mono text-[10px] text-text-mute">
          ~{formatUsd(est.perLead)}/lead
        </span>
      </div>
      <div className="flex items-baseline gap-3 pt-1">
        {est.total !== null ? (
          <>
            <div className="text-lg font-semibold text-text tabular">
              {formatUsd(est.total)}
            </div>
            <div className="font-mono text-[10px] text-text-mute">
              to run {totalLeadCap} leads end-to-end
            </div>
          </>
        ) : (
          <>
            <div className="text-lg font-semibold text-text tabular">
              {formatUsd(est.perDay)}
            </div>
            <div className="font-mono text-[10px] text-text-mute">
              per day at full send cap ({dailySendCap}/day)
            </div>
          </>
        )}
      </div>
      <div className="font-mono text-[10px] text-text-mute pt-1.5">
        Rough estimate · Places + Gemini. Excludes AgentMail subscription.
      </div>
    </div>
  );
}

function AutonomyButton({
  active,
  onClick,
  label,
  sub,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  sub: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        (active
          ? "bg-surface-2 text-text border-[color:var(--accent)]"
          : "bg-surface text-text-dim hover:text-text") +
        " flex-1 px-2 py-1.5 text-left border-r last:border-r-0 border-border"
      }
    >
      <div className="font-mono text-[11px] uppercase tracking-wider">
        {label}
      </div>
      <div className="font-mono text-[10px] text-text-mute">{sub}</div>
    </button>
  );
}
