"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import {
  ArrowUpRight,
  Check,
  Loader2,
  RefreshCw,
  Save,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
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
import { parseReplyIntent } from "@/lib/utils";
import type { ReplyEntry } from "@/lib/types";

import { EmptyState } from "@/components/shared/EmptyState";
import { ThreadView } from "@/components/shared/ThreadView";
import { IntentBadge } from "@/components/shared/IntentBadge";
import { HookTierBadge } from "@/components/shared/HookTierBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";

interface ReplyDetailProps {
  entry: ReplyEntry;
  onAfterAction: () => void;
}

type ConfirmAction = "approve" | "regenerate" | "dismiss" | null;

export function ReplyDetail({ entry, onAfterAction }: ReplyDetailProps) {
  const leadId = entry.lead.id;
  const { data, isLoading, mutate } = useLead(leadId);
  const { mutate: globalMutate } = useSWRConfig();
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const [working, setWorking] = useState(false);
  const [body, setBody] = useState(entry.pending_reply_draft?.body ?? "");
  const [saving, setSaving] = useState(false);

  // Keep local body in sync when detail refetches.
  useEffect(() => {
    if (!data) return;
    const draft = data.messages
      .filter((m) => m.direction === "outbound" && !m.sent_at)
      .at(-1);
    setBody(draft?.body ?? "");
  }, [data]);

  if (isLoading && !data) {
    return (
      <div className="p-8 space-y-6">
        <Skeleton className="h-6 w-60" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        icon={X}
        title="Couldn't load thread"
      />
    );
  }

  const { lead, messages } = data;
  const draft = messages
    .filter((m) => m.direction === "outbound" && !m.sent_at)
    .at(-1);
  const originalCold = messages.find(
    (m) => m.direction === "outbound" && m.hook_tier_used != null
  );

  const intent = parseReplyIntent(draft?.hook_rationale);
  const dirty = draft ? body !== draft.body : false;

  const refreshLists = () => {
    globalMutate("stats");
    globalMutate("replies");
    globalMutate(
      (key) => typeof key === "string" && key.startsWith("leads"),
      undefined,
      { revalidate: true }
    );
  };

  const handleSaveEdit = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await api.editReply(leadId, body);
      toast.success("Reply draft saved");
      await mutate();
    } catch (e) {
      toast.error(`Save failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const runConfirmed = async () => {
    if (!confirm) return;
    setWorking(true);
    try {
      if (confirm === "approve") {
        // Persist pending edits first so the server sends what the user sees.
        if (dirty) {
          await api.editReply(leadId, body);
        }
        await api.approveReply(leadId);
        toast.success(`Reply sent to ${lead.email}`);
        refreshLists();
        onAfterAction();
      } else if (confirm === "regenerate") {
        const res = await api.regenerateReply(leadId);
        toast.success(`Regenerated (intent: ${res.intent})`);
        await mutate();
        globalMutate("replies");
      } else if (confirm === "dismiss") {
        await api.skipLead(leadId);
        toast.success("Lead marked as dead");
        refreshLists();
        onAfterAction();
      }
      setConfirm(null);
    } catch (e) {
      toast.error(`Action failed: ${errorMessage(e)}`);
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Lead context strip */}
      <div className="border-b border-border bg-surface/60 px-8 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <StatusBadge status={lead.status} />
              {originalCold?.hook_tier_used != null && (
                <HookTierBadge tier={originalCold.hook_tier_used} showName />
              )}
              {intent && <IntentBadge intent={intent} />}
            </div>
            <h2 className="text-lg font-semibold tracking-tight text-text truncate">
              {lead.company}
            </h2>
            <div className="text-xs text-text-dim truncate">
              {lead.owner_name && <span>{lead.owner_name} </span>}
              {lead.email && (
                <span className="font-mono text-text-mute">&lt;{lead.email}&gt;</span>
              )}
              <span className="text-text-mute"> · {lead.city}</span>
            </div>
          </div>
          <Link
            href={`/leads/${lead.id}`}
            className="font-mono text-[10px] uppercase tracking-wider text-text-mute hover:text-text-dim flex items-center gap-1 shrink-0"
          >
            Full lead <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      {/* Thread (scrollable) */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <ThreadView
          messages={messages.filter((m) => !(m.direction === "outbound" && !m.sent_at))}
        />
      </div>

      {/* Reply editor (sticky footer) */}
      <div className="border-t border-border bg-surface">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
          <span>Reply</span>
          {draft ? (
            <>
              <span className="text-text-mute/60">· AI drafted</span>
              {dirty && (
                <span className="ml-auto text-[color:var(--warn)]">
                  unsaved changes
                </span>
              )}
            </>
          ) : (
            <span className="text-text-mute/60">· no draft</span>
          )}
        </div>
        <div className="px-5 py-4 space-y-3">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={6}
            placeholder={
              draft
                ? "Reply draft — edit freely"
                : "No AI draft yet. Click Regenerate to generate one."
            }
            disabled={!draft}
            className="font-mono text-sm leading-relaxed resize-y"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-2">
              {draft && (
                <>
                  <Button
                    size="sm"
                    onClick={() => setConfirm("approve")}
                    disabled={working || saving}
                  >
                    <Check className="h-3.5 w-3.5" /> Approve &amp; send
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleSaveEdit}
                    disabled={!dirty || saving || working}
                  >
                    {saving ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Saving…
                      </>
                    ) : (
                      <>
                        <Save className="h-3.5 w-3.5" />
                        Save draft
                      </>
                    )}
                  </Button>
                </>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirm("regenerate")}
                disabled={working}
              >
                <RefreshCw className="h-3.5 w-3.5" /> Regenerate
              </Button>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirm("dismiss")}
              disabled={working}
              className="text-text-mute hover:text-[color:var(--danger)]"
            >
              <X className="h-3.5 w-3.5" /> Mark as handled (dead)
            </Button>
          </div>
        </div>
      </div>

      {/* Confirmation */}
      <Dialog open={confirm !== null} onOpenChange={(v) => !v && setConfirm(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
              {confirm === "approve" && "Send reply"}
              {confirm === "regenerate" && "Regenerate reply"}
              {confirm === "dismiss" && "Mark as handled"}
            </DialogTitle>
            <DialogDescription className="text-sm text-text-dim pt-2">
              {confirm === "approve" && lead.email && (
                <>
                  This will send the reply to{" "}
                  <span className="font-mono text-text">{lead.email}</span>.
                  {dirty && " Your unsaved edits will be saved first."}
                </>
              )}
              {confirm === "regenerate" && (
                <>
                  The current reply draft will be discarded and a new one
                  generated from the latest inbound message.
                </>
              )}
              {confirm === "dismiss" && (
                <>
                  This marks the lead as <span className="font-mono">dead</span>.
                  The thread will disappear from the Replies tab. Use this when
                  you&apos;ve replied elsewhere or the conversation no longer
                  needs Helios attention.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirm(null)}
              disabled={working}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant={confirm === "dismiss" ? "destructive" : "default"}
              onClick={runConfirmed}
              disabled={working}
            >
              {working ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Working…
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
