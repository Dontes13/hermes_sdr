"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { api, errorMessage } from "@/lib/api";
import { useInboxes } from "@/lib/hooks/useInboxes";
import type { Inbox } from "@/lib/types";

function StatusBadge({ status }: { status: Inbox["status"] }) {
  const label = status === "ok" ? "OK" : status === "warning" ? "Warning" : "Blocked";
  const cls =
    status === "ok"
      ? "bg-green-100 text-green-700"
      : status === "warning"
      ? "bg-yellow-100 text-yellow-700"
      : "bg-red-100 text-red-700";

  const badge = (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-mono ${cls}`}>
      {label}
    </span>
  );

  if (status !== "blocked") return badge;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help">{badge}</span>
        </TooltipTrigger>
        <TooltipContent>Daily send limit reached. Resets at midnight UTC.</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ProgressBar({ pct, status }: { pct: number; status: Inbox["status"] }) {
  const fill =
    status === "blocked"
      ? "bg-red-500"
      : status === "warning"
      ? "bg-yellow-400"
      : "bg-green-500";
  return (
    <div className="w-28 bg-muted rounded-full h-1.5">
      <div
        className={`h-1.5 rounded-full ${fill}`}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

function InboxRow({ inbox, onMutate }: { inbox: Inbox; onMutate: () => void }) {
  const [limitEdit, setLimitEdit] = useState(String(inbox.daily_send_limit));
  const [saving, setSaving] = useState(false);

  const handleLimitBlur = async () => {
    const parsed = parseInt(limitEdit, 10);
    if (isNaN(parsed) || parsed < 1 || parsed === inbox.daily_send_limit) {
      setLimitEdit(String(inbox.daily_send_limit));
      return;
    }
    setSaving(true);
    try {
      await api.updateInbox(inbox.id, { daily_send_limit: parsed });
      toast.success("Limit updated");
      onMutate();
    } catch (e) {
      toast.error(`Update failed: ${errorMessage(e)}`);
      setLimitEdit(String(inbox.daily_send_limit));
    } finally {
      setSaving(false);
    }
  };

  const handleActiveToggle = async () => {
    try {
      await api.updateInbox(inbox.id, { is_active: !inbox.is_active });
      onMutate();
    } catch (e) {
      toast.error(`Update failed: ${errorMessage(e)}`);
    }
  };

  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3 font-mono text-sm">{inbox.email}</td>
      <td className="px-4 py-3">
        <div className="space-y-1">
          <ProgressBar pct={inbox.utilization_pct} status={inbox.status} />
          <div className="text-[11px] text-text-mute font-mono">
            {inbox.sent_today} / {inbox.daily_send_limit}
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={inbox.status} />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Input
            value={limitEdit}
            onChange={(e) => setLimitEdit(e.target.value)}
            onBlur={handleLimitBlur}
            className="w-16 h-7 text-sm font-mono px-2"
            type="number"
            min={1}
            disabled={saving}
          />
          {saving && <Loader2 className="h-3 w-3 animate-spin text-text-mute" />}
        </div>
      </td>
      <td className="px-4 py-3">
        <label className="flex items-center gap-2 cursor-pointer w-fit">
          <input
            type="checkbox"
            checked={inbox.is_active}
            onChange={handleActiveToggle}
            className="h-3.5 w-3.5 accent-primary cursor-pointer"
          />
          <span className="text-[11px] text-text-mute">
            {inbox.is_active ? "Active" : "Inactive"}
          </span>
        </label>
      </td>
    </tr>
  );
}

function NewInboxRow({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState("");
  const [agentmailId, setAgentmailId] = useState("");
  const [limit, setLimit] = useState("40");
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    const parsed = parseInt(limit, 10);
    if (!email.trim() || !agentmailId.trim() || isNaN(parsed) || parsed < 1) {
      toast.error("Email, AgentMail ID, and a valid limit are required");
      return;
    }
    setSaving(true);
    try {
      await api.createInbox({
        email: email.trim(),
        agentmail_inbox_id: agentmailId.trim(),
        daily_send_limit: parsed,
      });
      toast.success("Inbox added");
      onCreated();
    } catch (e) {
      toast.error(`Create failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="px-5 py-4 space-y-3 bg-surface/50">
      <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            Email
          </Label>
          <div className="text-[11px] text-text-mute">Inbox email address.</div>
        </div>
        <Input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="outreach@yourdomain.com"
          className="font-mono text-sm"
          autoFocus
        />
      </div>
      <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            AgentMail inbox ID
          </Label>
          <div className="text-[11px] text-text-mute">The ID from the AgentMail dashboard.</div>
        </div>
        <Input
          value={agentmailId}
          onChange={(e) => setAgentmailId(e.target.value)}
          placeholder="inbox_xxxxxxxx"
          className="font-mono text-sm"
        />
      </div>
      <div className="grid grid-cols-[200px_1fr] gap-4 items-center">
        <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
          Daily send limit
        </Label>
        <Input
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          type="number"
          min={1}
          className="w-24 font-mono text-sm"
        />
      </div>
      <div className="flex gap-2 justify-end">
        <Button size="sm" variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleCreate} disabled={saving || !email.trim() || !agentmailId.trim()}>
          {saving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Adding…
            </>
          ) : (
            <>
              <Plus className="h-3.5 w-3.5" />
              Add inbox
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

export function InboxesEditor() {
  const { data: inboxes, mutate } = useInboxes();
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="border border-border bg-surface">
      <div className="border-b border-border px-4 py-2.5">
        <div className="label-sm">Send inboxes</div>
        <div className="text-[11px] text-text-mute pt-1 leading-relaxed">
          Daily send limits and utilization per inbox. Counts reset at midnight UTC.
          Sends are blocked when an inbox reaches 100% utilization.
        </div>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Email
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Progress
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Status
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Daily limit
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Active
            </th>
          </tr>
        </thead>
        <tbody>
          {(inboxes ?? []).map((inbox) => (
            <InboxRow key={inbox.id} inbox={inbox} onMutate={mutate} />
          ))}
          {inboxes !== undefined && inboxes.length === 0 && (
            <tr>
              <td
                colSpan={5}
                className="px-4 py-4 text-[11px] text-text-mute text-center"
              >
                No inboxes configured. Add one below.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {showNew && (
        <div className="border-t border-border">
          <NewInboxRow
            onCreated={() => {
              setShowNew(false);
              mutate();
            }}
            onCancel={() => setShowNew(false)}
          />
        </div>
      )}

      {!showNew && (
        <div className="px-4 py-3 border-t border-border">
          <Button size="sm" variant="outline" onClick={() => setShowNew(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add inbox
          </Button>
        </div>
      )}
    </div>
  );
}
