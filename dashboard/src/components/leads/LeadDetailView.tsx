"use client";

import { useState } from "react";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  FileText,
  Linkedin,
  Loader2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";

import { api, errorMessage } from "@/lib/api";
import { useLead } from "@/lib/hooks/useLead";
import { formatRelative, formatShortDate } from "@/lib/utils";

import { EmptyState } from "@/components/shared/EmptyState";
import { IntelViewer } from "@/components/shared/IntelViewer";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { HookTierBadge } from "@/components/shared/HookTierBadge";
import { ThreadView } from "@/components/shared/ThreadView";
import { BriefingModal } from "@/components/shared/BriefingModal";

interface LeadDetailViewProps {
  leadId: string;
}

export function LeadDetailView({ leadId }: LeadDetailViewProps) {
  const { data, error, isLoading, mutate } = useLead(leadId);
  const { mutate: globalMutate } = useSWRConfig();

  const [briefingOpen, setBriefingOpen] = useState(false);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [currentBriefing, setCurrentBriefing] = useState<string | null>(null);
  const [skipConfirm, setSkipConfirm] = useState(false);
  const [skipping, setSkipping] = useState(false);

  if (isLoading && !data) {
    return (
      <div className="p-8 space-y-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <EmptyState
        icon={X}
        title="Couldn't load lead"
        description={errorMessage(error) || "Unknown error"}
      />
    );
  }

  const { lead, messages } = data;
  const canBrief = lead.status === "replied" || lead.status === "booked";
  const canSkip = lead.status !== "dead" && lead.status !== "unsubscribed";
  const pendingDraft = messages
    .filter((m) => m.direction === "outbound" && !m.sent_at)
    .at(-1);

  const handleOpenBriefing = async () => {
    // If cached briefing exists on the lead, open with it and don't regenerate.
    if (lead.briefing_md) {
      setCurrentBriefing(lead.briefing_md);
      setBriefingOpen(true);
      return;
    }
    setBriefingLoading(true);
    try {
      const { briefing_md } = await api.briefLead(leadId);
      setCurrentBriefing(briefing_md);
      setBriefingOpen(true);
      // brief() flips replied→booked as a side effect — refresh lead + stats
      // so the status pill updates without a page reload.
      await mutate();
      globalMutate("stats");
    } catch (e) {
      toast.error(`Briefing failed: ${errorMessage(e)}`);
    } finally {
      setBriefingLoading(false);
    }
  };

  const handleSkip = async () => {
    setSkipping(true);
    try {
      await api.skipLead(leadId);
      toast.success("Lead marked as dead");
      await mutate();
      globalMutate("stats");
      globalMutate(
        (key) => typeof key === "string" && key.startsWith("leads"),
        undefined,
        { revalidate: true }
      );
      setSkipConfirm(false);
    } catch (e) {
      toast.error(`Failed: ${errorMessage(e)}`);
    } finally {
      setSkipping(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-8 py-6 space-y-7">
      {/* Header */}
      <div>
        <Link
          href="/leads"
          className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-text-mute hover:text-text-dim"
        >
          <ArrowLeft className="h-3 w-3" />
          <span>All leads</span>
        </Link>

        <div className="pt-3 flex items-start justify-between gap-6 flex-wrap">
          <div className="space-y-1.5 min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-text">
              {lead.company}
            </h1>
            <div className="flex items-center gap-3 flex-wrap">
              <StatusBadge status={lead.status} size="md" />
              {lead.latest_hook_tier != null && (
                <HookTierBadge tier={lead.latest_hook_tier} showName size="md" />
              )}
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
                {lead.city}
              </span>
            </div>
            <div className="text-sm text-text-dim pt-1">
              {lead.owner_name && <span>{lead.owner_name} </span>}
              {lead.email && (
                <span className="font-mono text-xs text-text-mute">
                  &lt;{lead.email}&gt;
                </span>
              )}
              {lead.phone && (
                <span className="font-mono text-xs text-text-mute">
                  {lead.owner_name || lead.email ? " · " : ""}
                  {lead.phone}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 shrink-0">
            <Button
              size="sm"
              variant={canBrief ? "default" : "outline"}
              onClick={handleOpenBriefing}
              disabled={briefingLoading || !canBrief}
              title={
                canBrief
                  ? undefined
                  : "Available once this lead has replied or is booked"
              }
            >
              {briefingLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…
                </>
              ) : (
                <>
                  <FileText className="h-3.5 w-3.5" /> Pre-call briefing
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSkipConfirm(true)}
              disabled={!canSkip || skipping}
              className="text-text-mute hover:text-[color:var(--danger)]"
            >
              <X className="h-3.5 w-3.5" /> Mark as dead
            </Button>
          </div>
        </div>

        <div className="pt-3 flex items-center gap-4 text-[10px] font-mono uppercase tracking-wider text-text-mute">
          <span>Created {formatShortDate(lead.created_at)}</span>
          <span>·</span>
          <span>Updated {formatRelative(lead.updated_at)}</span>
        </div>
      </div>

      {/* LinkedIn channel */}
      <LinkedInPanel
        leadId={leadId}
        linkedinUrl={lead.linkedin_url ?? null}
        linkedinState={lead.linkedin_state ?? null}
        eligibleAt={lead.linkedin_followup_eligible_at ?? null}
        onChange={() => mutate()}
      />

      {/* Intel */}
      <section className="border border-border bg-surface">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
          <span>Client intel</span>
        </div>
        <div className="px-5 py-5">
          <IntelViewer lead={lead} />
        </div>
      </section>

      {/* Messages */}
      <section className="border border-border bg-surface">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
          <span>Conversation</span>
          <span className="text-text-mute/60">
            · {messages.length} message{messages.length === 1 ? "" : "s"}
          </span>
        </div>
        <div className="px-5 py-5">
          {messages.length === 0 ? (
            <div className="text-sm text-text-mute">
              No messages yet. Draft one from the Pipeline tab.
            </div>
          ) : (
            <ThreadView
              messages={messages.filter(
                (m) => !(m.direction === "outbound" && !m.sent_at)
              )}
              pendingDraft={pendingDraft ?? null}
            />
          )}
        </div>
      </section>

      {/* Raw JSON collapsible */}
      <RawJsonSection lead={lead.intel_json} />

      {/* Briefing modal */}
      <BriefingModal
        open={briefingOpen}
        onClose={() => setBriefingOpen(false)}
        leadId={leadId}
        company={lead.company}
        briefing={currentBriefing ?? lead.briefing_md}
        onRegenerate={(md) => {
          setCurrentBriefing(md);
          mutate();
          globalMutate("stats");
        }}
      />

      {/* Skip confirmation */}
      <Dialog open={skipConfirm} onOpenChange={(v) => !v && setSkipConfirm(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
              Mark as dead
            </DialogTitle>
            <DialogDescription className="text-sm text-text-dim pt-2">
              This lead will be marked as <span className="font-mono">dead</span> and
              excluded from future batches.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSkipConfirm(false)}
              disabled={skipping}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleSkip}
              disabled={skipping}
            >
              {skipping ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Working…
                </>
              ) : (
                <>Confirm →</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface LinkedInPanelProps {
  leadId: string;
  linkedinUrl: string | null;
  linkedinState: string | null;
  eligibleAt: string | null;
  onChange: () => void;
}

function LinkedInPanel({
  leadId,
  linkedinUrl,
  linkedinState,
  eligibleAt,
  onChange,
}: LinkedInPanelProps) {
  const [editing, setEditing] = useState(false);
  const [draftUrl, setDraftUrl] = useState(linkedinUrl ?? "");
  const [busy, setBusy] = useState<null | "save" | "invite" | "dm">(null);

  const stateLabel = linkedinState
    ? linkedinState.replace("_", " ").toUpperCase()
    : "—";

  const canDraftInvite = !!linkedinUrl && linkedinState == null;
  const canDraftDm = linkedinState === "connected";

  const save = async () => {
    setBusy("save");
    try {
      await api.setLinkedInUrl(leadId, draftUrl.trim() || null);
      toast.success("LinkedIn URL saved");
      setEditing(false);
      onChange();
    } catch (e) {
      toast.error(`Save failed: ${errorMessage(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const draft = async (kind: "invite" | "dm") => {
    setBusy(kind);
    try {
      await api.draftLinkedIn(leadId, kind);
      toast.success(
        kind === "invite"
          ? "LinkedIn invite draft created — review in /approvals"
          : "LinkedIn DM draft created — review in /approvals"
      );
      onChange();
    } catch (e) {
      toast.error(`Draft failed: ${errorMessage(e)}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
        <Linkedin className="h-3 w-3" />
        <span>LinkedIn channel</span>
        <span className="ml-auto text-text-mute/80">
          state: <span className="text-text-dim">{stateLabel}</span>
        </span>
      </div>
      <div className="px-5 py-5 space-y-3">
        {editing ? (
          <div className="flex items-center gap-2">
            <input
              type="url"
              value={draftUrl}
              onChange={(e) => setDraftUrl(e.target.value)}
              placeholder="https://linkedin.com/in/…"
              className="flex-1 bg-background border border-border px-3 py-1.5 text-sm font-mono text-text"
              autoFocus
            />
            <Button size="sm" onClick={save} disabled={busy === "save"}>
              {busy === "save" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraftUrl(linkedinUrl ?? "");
                setEditing(false);
              }}
              disabled={busy === "save"}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            {linkedinUrl ? (
              <a
                href={linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-xs text-text-dim underline truncate"
              >
                {linkedinUrl}
              </a>
            ) : (
              <span className="font-mono text-xs text-text-mute">
                No LinkedIn URL on file
              </span>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setEditing(true)}
              className="ml-auto text-text-mute"
            >
              {linkedinUrl ? "Edit" : "Add URL"}
            </Button>
          </div>
        )}

        {eligibleAt && linkedinState == null && linkedinUrl && (
          <div className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
            Eligible for follow-up after {formatShortDate(eligibleAt)}
          </div>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() => draft("invite")}
            disabled={!canDraftInvite || busy !== null}
            title={
              !linkedinUrl
                ? "Add a LinkedIn URL first"
                : linkedinState != null
                  ? `Already in state '${linkedinState}'`
                  : undefined
            }
          >
            {busy === "invite" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Linkedin className="h-3.5 w-3.5" />
            )}
            Draft invite
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => draft("dm")}
            disabled={!canDraftDm || busy !== null}
            title={
              canDraftDm ? undefined : "DM requires linkedin_state='connected'"
            }
          >
            {busy === "dm" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Linkedin className="h-3.5 w-3.5" />
            )}
            Draft DM
          </Button>
        </div>
      </div>
    </section>
  );
}

function RawJsonSection({ lead }: { lead: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="border border-border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute hover:text-text-dim"
      >
        <span className="flex items-center gap-2">
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span>Raw intel JSON</span>
        </span>
        <span>{open ? "hide" : "show"}</span>
      </button>
      {open && (
        <pre className="overflow-x-auto p-4 text-[11px] leading-relaxed text-text-dim font-mono">
          {JSON.stringify(lead, null, 2)}
        </pre>
      )}
    </section>
  );
}
