"use client";

import { useState } from "react";
import { Copy, RefreshCw, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

interface BriefingModalProps {
  open: boolean;
  onClose: () => void;
  leadId: string;
  company: string;
  briefing: string | null;
  onRegenerate?: (newBriefing: string) => void;
}

export function BriefingModal({
  open,
  onClose,
  leadId,
  company,
  briefing,
  onRegenerate,
}: BriefingModalProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [current, setCurrent] = useState(briefing);

  // Keep local copy fresh when parent passes new briefing
  if (briefing !== null && briefing !== current && !regenerating) {
    setCurrent(briefing);
  }

  const handleCopy = async () => {
    if (!current) return;
    try {
      await navigator.clipboard.writeText(current);
      toast.success("Briefing copied to clipboard");
    } catch (e) {
      toast.error(`Copy failed: ${errorMessage(e)}`);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const { briefing_md } = await api.briefLead(leadId);
      setCurrent(briefing_md);
      onRegenerate?.(briefing_md);
      toast.success("Briefing regenerated");
    } catch (e) {
      toast.error(`Failed to regenerate: ${errorMessage(e)}`);
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-mono uppercase tracking-wider text-xs text-text-dim">
            Pre-call briefing
          </DialogTitle>
          <div className="text-lg font-semibold text-text pt-0.5">{company}</div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto border-y border-border bg-bg/40 px-6 py-5">
          {current ? (
            <div className="prose-terminal">
              <ReactMarkdown>{current}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-text-mute font-mono uppercase tracking-wider">
              No briefing generated yet.
            </div>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              disabled={!current}
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRegenerate}
              disabled={regenerating}
            >
              <RefreshCw
                className={
                  regenerating ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"
                }
              />
              {regenerating ? "Regenerating…" : "Regenerate"}
            </Button>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
