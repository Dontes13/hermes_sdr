"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

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
import { api, errorMessage } from "@/lib/api";
import type { WarmingSchedule, WarmingStatus } from "@/lib/types";

// Mirrors quota_for_day() in agent/src/services/warming.py
const WARMING_DAY_MAP: [number, number][] = [
  [1, 5], [2, 8], [3, 10], [4, 13], [5, 16], [6, 19],
  [7, 22], [8, 25], [9, 28], [10, 31], [14, 35], [21, 40],
];

function totalWarmingDays(target: number): number {
  for (const [day, quota] of WARMING_DAY_MAP) {
    if (quota >= target) return day;
  }
  return 21;
}

function WarmingStatusBadge({ status }: { status: WarmingStatus }) {
  const map: Record<WarmingStatus, { label: string; cls: string }> = {
    warming: { label: "Warming", cls: "bg-blue-100 text-blue-700" },
    complete: { label: "Complete", cls: "bg-emerald-100 text-emerald-700" },
    paused: { label: "Paused", cls: "bg-surface-2 text-text-mute" },
  };
  const { label, cls } = map[status] ?? map.paused;
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-mono ${cls}`}>
      {label}
    </span>
  );
}

interface ScheduleRowProps {
  schedule: WarmingSchedule;
  onMutate: () => void;
}

function ScheduleRow({ schedule, onMutate }: ScheduleRowProps) {
  const [limitEdit, setLimitEdit] = useState(String(schedule.target_daily_limit));
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const totalDays = totalWarmingDays(schedule.target_daily_limit);
  const inboxEmail = schedule.inboxes?.email ?? schedule.inbox_id;

  const handleLimitBlur = async () => {
    const parsed = parseInt(limitEdit, 10);
    if (isNaN(parsed) || parsed < 1 || parsed === schedule.target_daily_limit) {
      setLimitEdit(String(schedule.target_daily_limit));
      return;
    }
    setSaving(true);
    try {
      await api.updateWarmingSchedule(schedule.id, { target_daily_limit: parsed });
      toast.success("Limit updated");
      onMutate();
    } catch (e) {
      toast.error(`Update failed: ${errorMessage(e)}`);
      setLimitEdit(String(schedule.target_daily_limit));
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePause = async () => {
    const newStatus = schedule.status === "paused" ? "warming" : "paused";
    setSaving(true);
    try {
      await api.updateWarmingSchedule(schedule.id, { status: newStatus });
      onMutate();
    } catch (e) {
      toast.error(`Update failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.deleteWarmingSchedule(schedule.id);
      toast.success("Removed from warming pool");
      onMutate();
    } catch (e) {
      toast.error(`Remove failed: ${errorMessage(e)}`);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <>
      <tr className="border-b border-border last:border-0">
        <td className="px-4 py-3 font-mono text-sm text-text">{inboxEmail}</td>
        <td className="px-4 py-3">
          <WarmingStatusBadge status={schedule.status} />
        </td>
        <td className="px-4 py-3 font-mono text-sm text-text-dim">
          Day {schedule.current_day} / {totalDays}
        </td>
        <td className="px-4 py-3 font-mono text-sm text-text-dim">
          {schedule.quota_today}
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
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs px-2.5"
              onClick={handleTogglePause}
              disabled={saving || schedule.status === "complete"}
            >
              {schedule.status === "paused" ? "Resume" : "Pause"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs px-2.5 text-red-600 hover:text-red-700 hover:border-red-300"
              onClick={() => setConfirmDelete(true)}
              disabled={deleting}
            >
              Remove
            </Button>
          </div>
        </td>
      </tr>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove from warming pool?</DialogTitle>
            <DialogDescription>
              Remove this inbox from the warming pool? Already-sent warming emails
              are kept for analytics.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDelete(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Removing&hellip;
                </>
              ) : (
                "Remove"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

interface WarmingTableProps {
  schedules: WarmingSchedule[];
  onMutate: () => void;
}

export function WarmingTable({ schedules, onMutate }: WarmingTableProps) {
  return (
    <div className="border border-border bg-surface">
      <div className="border-b border-border px-4 py-2.5">
        <div className="label-sm">Warming pool</div>
        <div className="text-[11px] text-text-mute pt-1 leading-relaxed">
          Each inbox ramps from 5 sends/day to its target over ~3 weeks. Quota
          resets and advances each day the cron runs.
        </div>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Inbox
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Status
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Progress
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Today
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Daily limit
            </th>
            <th className="px-4 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => (
            <ScheduleRow key={s.id} schedule={s} onMutate={onMutate} />
          ))}
          {schedules.length === 0 && (
            <tr>
              <td
                colSpan={6}
                className="px-4 py-8 text-center text-[12px] text-text-mute"
              >
                No inboxes in warming pool. Use the button above to add one.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
