"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Users } from "lucide-react";

import { TopBar } from "@/components/layout/TopBar";
import { LeadFilters, type LeadFiltersState } from "@/components/leads/LeadFilters";
import { LeadsTable } from "@/components/leads/LeadsTable";
import { EmptyState } from "@/components/shared/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { useLeads } from "@/lib/hooks/useLeads";
import { useConfig } from "@/lib/hooks/useConfig";
import type { LeadStatus } from "@/lib/types";
import { LEAD_STATUSES } from "@/lib/types";

export default function LeadsPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-60 w-full" />
        </div>
      }
    >
      <LeadsPageInner />
    </Suspense>
  );
}

function LeadsPageInner() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") as LeadStatus | null;
  const validInitialStatus =
    initialStatus && LEAD_STATUSES.includes(initialStatus) ? initialStatus : null;

  const { data: leads, isLoading } = useLeads(undefined, 200);
  const { data: config } = useConfig();

  const [filters, setFilters] = useState<LeadFiltersState>({
    status: validInitialStatus,
    city: null,
    hookTier: null,
    search: "",
    icpOnly: false,
  });

  // Combine configured cities with distinct cities found in leads.
  const cities = useMemo(() => {
    const set = new Set<string>();
    (config?.target_cities ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((c) => set.add(c));
    leads?.forEach((l) => {
      if (l.city) set.add(l.city);
    });
    return Array.from(set).sort();
  }, [config, leads]);

  const filtered = useMemo(() => {
    if (!leads) return [];
    const search = filters.search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (filters.status && lead.status !== filters.status) return false;
      if (filters.city && lead.city !== filters.city) return false;
      if (filters.hookTier != null && lead.latest_hook_tier !== filters.hookTier) {
        return false;
      }
      if (filters.icpOnly && (lead.icp_score == null || lead.icp_score < 40)) {
        return false;
      }
      if (search) {
        const hay =
          `${lead.company} ${lead.owner_name ?? ""} ${lead.email ?? ""}`.toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });
  }, [leads, filters]);

  const activeFiltersCount = [
    filters.status,
    filters.city,
    filters.hookTier,
    filters.search.length > 0 ? filters.search : null,
    filters.icpOnly ? true : null,
  ].filter(Boolean).length;

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="Leads"
        eyebrow="Helios / all prospects"
        subtitle={
          isLoading && !leads
            ? "Loading…"
            : `${filtered.length} of ${leads?.length ?? 0} lead${(leads?.length ?? 0) === 1 ? "" : "s"}${activeFiltersCount > 0 ? ` · ${activeFiltersCount} filter${activeFiltersCount === 1 ? "" : "s"} active` : ""}`
        }
      />

      <LeadFilters filters={filters} setFilters={setFilters} cities={cities} />

      <div className="flex-1 px-8 pb-8 pt-4">
        {isLoading && !leads ? (
          <div className="border border-border bg-surface">
            <div className="border-b border-border px-4 py-2.5 flex gap-6">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-14 ml-auto" />
            </div>
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="border-b border-border px-4 py-3 flex items-center gap-6"
              >
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-16 ml-auto" />
              </div>
            ))}
          </div>
        ) : !filtered.length ? (
          <div className="border border-border bg-surface">
            <EmptyState
              icon={Users}
              size="md"
              title="No leads match"
              description={
                activeFiltersCount > 0
                  ? "Try clearing or adjusting filters above. The result set is empty with your current criteria."
                  : "Run a campaign from /campaigns, or hit Prospect from the Pipeline tab, to add leads."
              }
            />
          </div>
        ) : (
          <div className="border border-border bg-surface">
            <LeadsTable leads={filtered} />
          </div>
        )}
      </div>
    </div>
  );
}
