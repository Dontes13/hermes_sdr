"use client";

import { useEffect, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/shared/EmptyState";
import { api, errorMessage } from "@/lib/api";
import { useLeads } from "@/lib/hooks/useLeads";
import { Inbox } from "lucide-react";

export function TestSendCard() {
  const { data: leads, isLoading } = useLeads("drafted");
  const [leadId, setLeadId] = useState<string>("");
  const [to, setTo] = useState<string>("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!leadId && leads && leads.length > 0) {
      setLeadId(leads[0].id);
    }
    if (leadId && leads && !leads.some((l) => l.id === leadId)) {
      setLeadId("");
    }
  }, [leads, leadId]);

  const handleSend = async () => {
    if (!leadId || !to) return;
    setSending(true);
    try {
      const res = await api.testSend(leadId, to);
      toast.success(`Sent "${res.subject}" to ${res.to}`);
    } catch (e) {
      toast.error(`Test send failed: ${errorMessage(e)}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
        <span>Test send</span>
        <span className="text-text-mute/60">· send a draft to your own inbox</span>
      </div>

      {!isLoading && leads && leads.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No drafts to test-send"
          description="Draft one from the Pipeline tab first."
          size="sm"
        />
      ) : (
        <div className="px-5 py-5 space-y-4">
          <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
            <div className="space-y-1 pt-1">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
                Lead
              </Label>
              <div className="text-[11px] text-text-mute leading-relaxed">
                Pick a drafted lead. Only draft status is eligible.
              </div>
            </div>
            <Select value={leadId} onValueChange={setLeadId}>
              <SelectTrigger className="w-full font-mono text-sm">
                <SelectValue placeholder="Select drafted lead…" />
              </SelectTrigger>
              <SelectContent>
                {leads?.map((lead) => (
                  <SelectItem key={lead.id} value={lead.id}>
                    {lead.company} <span className="text-text-mute">· {lead.city}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
            <div className="space-y-1 pt-1">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
                Recipient
              </Label>
              <div className="text-[11px] text-text-mute leading-relaxed">
                The email address the test lands in. Typically your own.
              </div>
            </div>
            <Input
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="you@example.com"
              className="font-mono text-sm"
            />
          </div>

          <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
            <div className="text-[11px] text-text-mute leading-relaxed max-w-lg">
              Test sends do not store thread state. Replies to a test send will
              not be detected by the reply poller. For real outreach, use
              Approve &amp; Send from the Approvals tab.
            </div>
            <Button
              size="sm"
              onClick={handleSend}
              disabled={!leadId || !to || sending}
            >
              {sending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Sending…
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  Send test
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
