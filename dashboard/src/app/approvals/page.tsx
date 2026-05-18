"use client";

import { useEffect, useState } from "react";
import { Inbox } from "lucide-react";

import { TopBar } from "@/components/layout/TopBar";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";
import { ApprovalDetail } from "@/components/approvals/ApprovalDetail";
import { EmptyState } from "@/components/shared/EmptyState";
import { SplitPane } from "@/components/shared/SplitPane";
import { Skeleton } from "@/components/ui/skeleton";
import { useLeads } from "@/lib/hooks/useLeads";

export default function ApprovalsPage() {
  const { data: leads, isLoading } = useLeads("drafted");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // When the list updates and our selection is no longer present, clear it.
  useEffect(() => {
    if (!leads) return;
    if (selectedId && !leads.some((l) => l.id === selectedId)) {
      setSelectedId(null);
    }
  }, [leads, selectedId]);

  // Auto-select the first lead on initial load if none is selected.
  useEffect(() => {
    if (!selectedId && leads && leads.length > 0) {
      setSelectedId(leads[0].id);
    }
  }, [leads, selectedId]);

  const count = leads?.length ?? 0;

  return (
    <div className="flex flex-col h-screen">
      <TopBar
        title="Approvals"
        eyebrow="Helios / outbound queue"
        subtitle={
          isLoading && !leads
            ? "Loading…"
            : count === 0
              ? "Inbox is empty"
              : `${count} draft${count === 1 ? "" : "s"} awaiting approval`
        }
      />

      <SplitPane
        sidebar={
          isLoading && !leads ? (
            <div className="p-4 space-y-4">
              {[...Array(4)].map((_, i) => (
                <SidebarSkeleton key={i} />
              ))}
            </div>
          ) : count === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No drafts"
              description="Run drafting from the Pipeline tab to generate more."
              size="sm"
            />
          ) : (
            <div className="overflow-y-auto flex-1">
              {leads!.map((lead) => (
                <ApprovalCard
                  key={lead.id}
                  lead={lead}
                  selected={selectedId === lead.id}
                  onClick={() => setSelectedId(lead.id)}
                />
              ))}
            </div>
          )
        }
        detail={
          selectedId ? (
            <ApprovalDetail
              key={selectedId}
              leadId={selectedId}
              onAfterAction={() => setSelectedId(null)}
            />
          ) : (
            <EmptyState
              icon={Inbox}
              title="Select a draft"
              description="Pick a drafted lead from the list to review the draft, the hook rationale, and the client intel."
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
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-10" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  );
}
