"use client";

import { useEffect, useState } from "react";
import { MessageSquare } from "lucide-react";

import { TopBar } from "@/components/layout/TopBar";
import { ReplyCard } from "@/components/replies/ReplyCard";
import { ReplyDetail } from "@/components/replies/ReplyDetail";
import { EmptyState } from "@/components/shared/EmptyState";
import { SplitPane } from "@/components/shared/SplitPane";
import { Skeleton } from "@/components/ui/skeleton";
import { useReplies } from "@/lib/hooks/useReplies";

export default function RepliesPage() {
  const { data: entries, isLoading } = useReplies();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!entries) return;
    if (selectedId && !entries.some((e) => e.lead.id === selectedId)) {
      setSelectedId(null);
    }
  }, [entries, selectedId]);

  useEffect(() => {
    if (!selectedId && entries && entries.length > 0) {
      setSelectedId(entries[0].lead.id);
    }
  }, [entries, selectedId]);

  const count = entries?.length ?? 0;
  const selectedEntry = entries?.find((e) => e.lead.id === selectedId) ?? null;

  return (
    <div className="flex flex-col h-screen">
      <TopBar
        title="Replies"
        eyebrow="Helios / inbound triage"
        subtitle={
          isLoading && !entries
            ? "Loading…"
            : count === 0
              ? "No replies to triage"
              : `${count} thread${count === 1 ? "" : "s"} awaiting reply`
        }
      />

      <SplitPane
        sidebar={
          isLoading && !entries ? (
            <div className="p-4 space-y-4">
              {[...Array(4)].map((_, i) => (
                <SidebarSkeleton key={i} />
              ))}
            </div>
          ) : count === 0 ? (
            <EmptyState
              icon={MessageSquare}
              title="No replies"
              description="Run Poll replies from the Pipeline tab to check for new inbound mail."
              size="sm"
            />
          ) : (
            <div className="overflow-y-auto flex-1">
              {entries!.map((entry) => (
                <ReplyCard
                  key={entry.lead.id}
                  entry={entry}
                  selected={selectedId === entry.lead.id}
                  onClick={() => setSelectedId(entry.lead.id)}
                />
              ))}
            </div>
          )
        }
        detail={
          selectedEntry ? (
            <ReplyDetail
              key={selectedEntry.lead.id}
              entry={selectedEntry}
              onAfterAction={() => setSelectedId(null)}
            />
          ) : (
            <EmptyState
              icon={MessageSquare}
              title="Select a reply"
              description="Pick a thread from the list to see the full conversation and the AI-drafted response."
            />
          )
        }
      />
    </div>
  );
}

function SidebarSkeleton() {
  return (
    <div className="space-y-2 border-b border-border pb-4">
      <div className="flex items-center gap-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-14" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-3 w-full" />
    </div>
  );
}
