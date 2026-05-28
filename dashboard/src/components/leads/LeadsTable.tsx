"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Star } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Lead } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";
import { HookTierBadge } from "@/components/shared/HookTierBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";

interface LeadsTableProps {
  leads: Lead[];
}

type SortField = "company" | "updated_at" | "icp_score";
type SortDir = "asc" | "desc";

function IcpDot({ score }: { score: number | null }) {
  if (score == null) return <span className="inline-block h-2 w-2 rounded-full bg-text-mute/40" />;
  if (score >= 70) return <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />;
  if (score >= 40) return <span className="inline-block h-2 w-2 rounded-full bg-amber-400" />;
  return <span className="inline-block h-2 w-2 rounded-full bg-red-500" />;
}

const VERTICAL_LABELS: Record<string, string> = {
  real_estate: "Real estate",
  restaurant: "Restaurant",
  other: "Other",
};

function VerticalBadge({ vertical }: { vertical: Lead["vertical"] }) {
  if (!vertical) return <span className="text-text-mute">—</span>;
  return (
    <span className="inline-block rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-text-dim">
      {VERTICAL_LABELS[vertical] ?? vertical}
    </span>
  );
}

export function LeadsTable({ leads }: LeadsTableProps) {
  const router = useRouter();
  const [sortField, setSortField] = useState<SortField>("icp_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const arr = [...leads];
    arr.sort((a, b) => {
      let cmp = 0;
      if (sortField === "company") {
        cmp = a.company.localeCompare(b.company);
      } else if (sortField === "icp_score") {
        // Nulls always last regardless of direction
        if (a.icp_score == null && b.icp_score == null) cmp = 0;
        else if (a.icp_score == null) cmp = 1;
        else if (b.icp_score == null) cmp = -1;
        else cmp = a.icp_score - b.icp_score;
      } else {
        cmp = a.updated_at.localeCompare(b.updated_at);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [leads, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "company" ? "asc" : "desc");
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-b border-border hover:bg-transparent">
          <TableHead className="w-[80px] text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            Hook
          </TableHead>
          <TableHead>
            <SortButton
              label="Company"
              active={sortField === "company"}
              dir={sortDir}
              onClick={() => toggleSort("company")}
            />
          </TableHead>
          <TableHead className="text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            City
          </TableHead>
          <TableHead className="text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            Status
          </TableHead>
          <TableHead className="text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            Owner / Email
          </TableHead>
          <TableHead className="text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            Rating
          </TableHead>
          <TableHead className="w-[72px]">
            <SortButton
              label="ICP"
              active={sortField === "icp_score"}
              dir={sortDir}
              onClick={() => toggleSort("icp_score")}
            />
          </TableHead>
          <TableHead className="w-[100px] text-[10px] font-mono uppercase tracking-[0.15em] text-text-mute">
            Vertical
          </TableHead>
          <TableHead>
            <SortButton
              label="Last activity"
              active={sortField === "updated_at"}
              dir={sortDir}
              onClick={() => toggleSort("updated_at")}
            />
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((lead) => (
          <TableRow
            key={lead.id}
            className="cursor-pointer border-b border-border transition-colors hover:bg-surface-2/60"
            onClick={() => router.push(`/leads/${lead.id}`)}
          >
            <TableCell className="py-2.5">
              <HookTierBadge tier={lead.latest_hook_tier} />
            </TableCell>
            <TableCell className="py-2.5 font-medium text-text">
              {lead.company}
            </TableCell>
            <TableCell className="py-2.5 text-text-dim font-mono text-xs">
              {lead.city}
            </TableCell>
            <TableCell className="py-2.5">
              <StatusBadge status={lead.status} />
            </TableCell>
            <TableCell className="py-2.5 max-w-[240px] truncate">
              <div className="text-xs text-text-dim truncate">
                {lead.owner_name && <span>{lead.owner_name} </span>}
                {lead.email && (
                  <span className="font-mono text-text-mute">
                    &lt;{lead.email}&gt;
                  </span>
                )}
                {!lead.owner_name && !lead.email && (
                  <span className="text-text-mute">—</span>
                )}
              </div>
            </TableCell>
            <TableCell className="py-2.5">
              {lead.google_rating != null ? (
                <span className="inline-flex items-center gap-1 font-mono text-xs text-text-dim">
                  <Star
                    className="h-3 w-3 fill-current"
                    style={{ color: "var(--tier-4)" }}
                  />
                  <span className="tabular">{lead.google_rating.toFixed(1)}</span>
                  {lead.google_reviews != null && (
                    <span className="text-text-mute">
                      · {lead.google_reviews}
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-text-mute">—</span>
              )}
            </TableCell>
            <TableCell className="py-2.5" onClick={(e) => e.stopPropagation()}>
              <IcpCell score={lead.icp_score} reasons={lead.icp_score_reasons} />
            </TableCell>
            <TableCell className="py-2.5">
              <VerticalBadge vertical={lead.vertical} />
            </TableCell>
            <TableCell className="py-2.5 font-mono text-xs text-text-dim">
              {formatRelative(lead.updated_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

interface IcpCellProps {
  score: number | null;
  reasons: Record<string, number> | null;
}

function IcpCell({ score, reasons }: IcpCellProps) {
  const cell = (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs">
      <span className={cn(score == null ? "text-text-mute" : "text-text-dim")}>
        {score ?? "—"}
      </span>
      <IcpDot score={score} />
    </span>
  );

  if (!reasons || Object.keys(reasons).length === 0) return cell;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{cell}</TooltipTrigger>
      <TooltipContent side="left" className="max-w-[220px]">
        <ul className="space-y-0.5">
          {Object.entries(reasons).map(([key, val]) => (
            <li key={key} className="flex justify-between gap-4 font-mono text-[11px]">
              <span className="text-background/70">{key.replace(/_/g, " ")}</span>
              <span className="text-background font-medium">+{val}</span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}

interface SortButtonProps {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}

function SortButton({ label, active, dir, onClick }: SortButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.15em]",
        active ? "text-text" : "text-text-mute hover:text-text-dim"
      )}
    >
      <span>{label}</span>
      {active ? (
        dir === "asc" ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      ) : (
        <ArrowDown className="h-3 w-3 opacity-0 group-hover:opacity-50" />
      )}
    </button>
  );
}
