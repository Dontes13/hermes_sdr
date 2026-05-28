"use client";

import { useState } from "react";
import { Flame, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";

import { TopBar } from "@/components/layout/TopBar";
import { WarmingTable } from "@/components/warming/WarmingTable";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import { useInboxes } from "@/lib/hooks/useInboxes";
import { useWarmingSchedules } from "@/lib/hooks/useWarmingSchedules";

export default function WarmingPage() {
  const { data: schedules, isLoading, mutate } = useWarmingSchedules();
  const { data: inboxes } = useInboxes();

  const [showAdd, setShowAdd] = useState(false);
  const [addInboxId, setAddInboxId] = useState("");
  const [addLimit, setAddLimit] = useState("40");
  const [adding, setAdding] = useState(false);

  const [showRunConfirm, setShowRunConfirm] = useState(false);
  const [running, setRunning] = useState(false);

  const poolInboxIds = new Set((schedules ?? []).map((s) => s.inbox_id));
  const availableInboxes = (inboxes ?? []).filter(
    (i) => i.is_active && !poolInboxIds.has(i.id)
  );

  const handleAddOpen = () => {
    setAddInboxId(availableInboxes[0]?.id ?? "");
    setAddLimit("40");
    setShowAdd(true);
  };

  const handleAddSubmit = async () => {
    const parsed = parseInt(addLimit, 10);
    if (!addInboxId || isNaN(parsed) || parsed < 1) return;
    setAdding(true);
    try {
      await api.createWarmingSchedule(addInboxId, parsed);
      toast.success("Inbox added to warming pool");
      mutate();
      setShowAdd(false);
    } catch (e) {
      toast.error(`Failed: ${errorMessage(e)}`);
    } finally {
      setAdding(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const result = await api.runWarmingNow();
      toast.success(
        `Cycle complete — ${result.total_sends} send${result.total_sends === 1 ? "" : "s"} across ${result.schedules_processed} schedule${result.schedules_processed === 1 ? "" : "s"}` +
          (result.errors > 0 ? `, ${result.errors} error${result.errors === 1 ? "" : "s"}` : "")
      );
      mutate();
    } catch (e) {
      toast.error(`Run failed: ${errorMessage(e)}`);
    } finally {
      setRunning(false);
      setShowRunConfirm(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="Email Warming"
        eyebrow="Helios / infrastructure"
        subtitle="Gradually ramps new inboxes to full send volume so they don't get flagged as spam. Internal infrastructure — never visible to leads."
      />

      <div className="flex-1 px-8 py-6 max-w-4xl w-full space-y-5">
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleAddOpen}
            disabled={availableInboxes.length === 0 && (inboxes ?? []).length > 0}
          >
            <Plus className="h-3.5 w-3.5" />
            Add inbox to warming pool
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowRunConfirm(true)}
            disabled={(schedules ?? []).filter((s) => s.status === "warming").length === 0}
          >
            <Flame className="h-3.5 w-3.5" />
            Run cycle now
          </Button>
        </div>

        {isLoading && !schedules ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <WarmingTable schedules={schedules ?? []} onMutate={mutate} />
        )}
      </div>

      {/* Add inbox dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add inbox to warming pool</DialogTitle>
            <DialogDescription>
              The inbox will start at 5 sends/day and ramp to the target limit
              over ~3 weeks.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
                Inbox
              </Label>
              {availableInboxes.length === 0 ? (
                <p className="text-[12px] text-text-mute">
                  All active inboxes are already in the pool, or no inboxes are
                  configured yet.
                </p>
              ) : (
                <select
                  value={addInboxId}
                  onChange={(e) => setAddInboxId(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {availableInboxes.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.email}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="space-y-1.5">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
                Target daily limit
              </Label>
              <Input
                value={addLimit}
                onChange={(e) => setAddLimit(e.target.value)}
                type="number"
                min={1}
                className="w-24 font-mono text-sm"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAdd(false)}
              disabled={adding}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddSubmit}
              disabled={adding || !addInboxId || availableInboxes.length === 0}
            >
              {adding ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Adding&hellip;
                </>
              ) : (
                "Add to pool"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run now confirmation dialog */}
      <Dialog open={showRunConfirm} onOpenChange={setShowRunConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Run warming cycle now?</DialogTitle>
            <DialogDescription>
              This will send warming emails immediately, ignoring the daily cron
              schedule. Continue?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRunConfirm(false)}
              disabled={running}
            >
              Cancel
            </Button>
            <Button onClick={handleRunNow} disabled={running}>
              {running ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Running&hellip;
                </>
              ) : (
                "Run now"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
