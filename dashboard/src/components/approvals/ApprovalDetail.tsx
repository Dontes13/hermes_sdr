"use client";

import { useEffect, useState } from "react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import {
  Check,
  Loader2,
  Pencil,
  RefreshCw,
  TestTube,
  X,
} from "lucide-react";

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
import { useLead } from "@/lib/hooks/useLead";
import { EmptyState } from "@/components/shared/EmptyState";
import { IntelViewer } from "@/components/shared/IntelViewer";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { HookTierBadge } from "@/components/shared/HookTierBadge";

import { DraftEditor } from "./DraftEditor";
import { HookInfo } from "./HookInfo";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2 } from "lucide-react";
import { formatRelative } from "@/lib/utils";

interface ApprovalDetailProps {
  leadId: string;
  onAfterAction: () => void;
}

type ConfirmAction = "approve" | "regenerate" | "skip" | null;

export function ApprovalDetail({ leadId, onAfterAction }: ApprovalDetailProps) {
  const { data, error, isLoading, mutate } = useLead(leadId);
  const { mutate: globalMutate } = useSWRConfig();
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const [working, setWorking] = useState(false);
  const [recipient, setRecipient] = useState<string>("");

  // Reset recipient to the lead's real email whenever a new lead is selected
  // or the approve dialog reopens.
  useEffect(() => {
    if (data?.lead.email) {
      setRecipient(data.lead.email);
    } else {
      setRecipient("");
    }
  }, [data?.lead.email, confirm]);

  const refreshAll = () => {
    globalMutate("stats");
    globalMutate(
      (key) => typeof key === "string" && key.startsWith("leads"),
      undefined,
      { revalidate: true }
    );
  };

  if (isLoading && !data) {
    return (
      <div className="p-8 space-y-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
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
  const draft = messages
    .filter((m) => m.direction === "outbound" && !m.sent_at)
    .at(-1);

  if (!draft) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="No pending draft"
        description="This lead no longer has a pending draft. It may have been sent, skipped, or regenerated."
      />
    );
  }

  const handleSaveEdit = async (subject: string, body: string) => {
    try {
      await api.editLead(leadId, subject, body);
      toast.success("Draft updated");
      await mutate();
      setEditing(false);
    } catch (e) {
      toast.error(`Save failed: ${errorMessage(e)}`);
    }
  };

  const isTestSend =
    lead.email != null &&
    recipient.trim().length > 0 &&
    recipient.trim().toLowerCase() !== lead.email.toLowerCase();

  const runConfirmed = async () => {
    if (!confirm) return;
    setWorking(true);
    try {
      if (confirm === "approve") {
        const to = recipient.trim();
        if (!to) {
          toast.error("Recipient is required");
          setWorking(false);
          return;
        }
        if (isTestSend) {
          // Route through /api/test-send — recipient overridden, lead state
          // unchanged so the draft stays available for a real send later.
          await api.testSend(leadId, to);
          toast.success(`Test sent to ${to} · lead status unchanged`);
          setConfirm(null);
          // Don't clear selection — user may want to keep iterating.
        } else {
          // Real send to the lead's actual email, flips lead → sent.
          await api.approveLead(leadId);
          toast.success(`Sent to ${to}`);
          refreshAll();
          onAfterAction();
          setConfirm(null);
        }
      } else if (confirm === "regenerate") {
        await api.regenerateLead(leadId);
        toast.success("Draft regenerated");
        await mutate();
        setConfirm(null);
      } else if (confirm === "skip") {
        await api.skipLead(leadId);
        toast.success("Lead marked as dead");
        refreshAll();
        onAfterAction();
        setConfirm(null);
      }
    } catch (e) {
      toast.error(`Action failed: ${errorMessage(e)}`);
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="p-8 space-y-5 overflow-y-auto max-h-screen">
      {/* Header */}
      <div className="pb-1 space-y-1">
        <div className="flex items-center gap-3 flex-wrap">
          <StatusBadge status={lead.status} />
          <HookTierBadge tier={draft.hook_tier_used} showName />
          <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
            Updated {formatRelative(lead.updated_at)}
          </span>
        </div>
        <h2 className="text-xl font-semibold tracking-tight text-text">
          {lead.company}
        </h2>
        <div className="text-xs text-text-dim">
          {lead.owner_name && <span>{lead.owner_name} </span>}
          {lead.email && (
            <span className="font-mono text-text-mute">&lt;{lead.email}&gt;</span>
          )}
          <span className="text-text-mute"> · {lead.city}</span>
        </div>
      </div>

      {/* Draft card */}
      <section className="border border-border bg-surface">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
          <span>Draft</span>
          <span className="text-text-mute/60">· pending approval</span>
        </div>
        <div className="px-5 py-5 space-y-5">
          {editing ? (
            <DraftEditor
              initialSubject={draft.subject ?? ""}
              initialBody={draft.body}
              onCancel={() => setEditing(false)}
              onSave={handleSaveEdit}
            />
          ) : (
            <>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute pb-1">
                  Subject
                </div>
                <div className="text-[15px] text-text font-medium">
                  {draft.subject || <span className="italic text-text-mute">—</span>}
                </div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute pb-1.5">
                  Body
                </div>
                <div className="whitespace-pre-wrap text-sm leading-[1.65] text-text border-l-2 border-border pl-4 py-0.5">
                  {draft.body}
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1 border-t border-border">
                <Button
                  size="sm"
                  onClick={() => setConfirm("approve")}
                  disabled={working}
                >
                  <Check className="h-3.5 w-3.5" /> Approve &amp; send
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditing(true)}
                  disabled={working}
                >
                  <Pencil className="h-3.5 w-3.5" /> Edit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setConfirm("regenerate")}
                  disabled={working}
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirm("skip")}
                  disabled={working}
                  className="ml-auto text-text-mute hover:text-[color:var(--danger)]"
                >
                  <X className="h-3.5 w-3.5" /> Skip
                </Button>
              </div>
            </>
          )}
        </div>
      </section>

      <HookInfo
        tier={draft.hook_tier_used}
        hookText={draft.hook_text}
        rationale={draft.hook_rationale}
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

      {/* Confirmation dialog */}
      <Dialog open={confirm !== null} onOpenChange={(v) => !v && setConfirm(null)}>
        <DialogContent className={confirm === "approve" ? "max-w-md" : "max-w-sm"}>
          <DialogHeader>
            <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
              {confirm === "approve" && (isTestSend ? "Test send" : "Send draft")}
              {confirm === "regenerate" && "Regenerate draft"}
              {confirm === "skip" && "Mark as dead"}
            </DialogTitle>
            <DialogDescription className="text-sm text-text-dim pt-2">
              {confirm === "approve" && (
                <>
                  {isTestSend ? (
                    <>
                      The email will be delivered to the override address below
                      via the test-send endpoint. The lead&apos;s status{" "}
                      <span className="font-mono text-text">will not</span>{" "}
                      change, so you can re-test or approve for real afterwards.
                    </>
                  ) : (
                    <>
                      This sends the drafted email to the real broker and flips
                      the lead to <span className="font-mono text-text">sent</span>.
                      You can&apos;t undo a send.
                    </>
                  )}
                </>
              )}
              {confirm === "regenerate" && (
                <>
                  The current draft will be discarded and a new one generated by
                  Gemini.
                </>
              )}
              {confirm === "skip" && (
                <>
                  This lead will be marked as <span className="font-mono">dead</span>{" "}
                  and excluded from future runs.
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          {confirm === "approve" && (
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <Label className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
                  Recipient
                </Label>
                {isTestSend && (
                  <span
                    className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider"
                    style={{ color: "var(--warn)" }}
                  >
                    <TestTube className="h-3 w-3" />
                    test mode
                  </span>
                )}
              </div>
              <Input
                type="email"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                placeholder={lead.email ?? "you@example.com"}
                className="font-mono text-sm"
                disabled={working}
              />
              {lead.email && (
                <div className="flex items-center justify-between pt-0.5">
                  <span className="font-mono text-[10px] text-text-mute">
                    Real recipient:{" "}
                    <span className="text-text-dim">{lead.email}</span>
                  </span>
                  {isTestSend && (
                    <button
                      type="button"
                      onClick={() => setRecipient(lead.email as string)}
                      className="font-mono text-[10px] uppercase tracking-wider text-text-mute hover:text-text-dim"
                      disabled={working}
                    >
                      reset →
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

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
              variant={confirm === "skip" ? "destructive" : "default"}
              onClick={runConfirmed}
              disabled={working || (confirm === "approve" && !recipient.trim())}
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
