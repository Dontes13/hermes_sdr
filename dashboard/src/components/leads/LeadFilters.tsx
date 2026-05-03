"use client";

import { X } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { LEAD_STATUSES, type HookTier, type LeadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const ALL = "__all__";

export interface LeadFiltersState {
  status: LeadStatus | null;
  city: string | null;
  hookTier: HookTier | null;
  search: string;
}

interface LeadFiltersProps {
  filters: LeadFiltersState;
  setFilters: (updater: (prev: LeadFiltersState) => LeadFiltersState) => void;
  cities: string[];
}

export function LeadFilters({ filters, setFilters, cities }: LeadFiltersProps) {
  const active =
    filters.status !== null ||
    filters.city !== null ||
    filters.hookTier !== null ||
    filters.search.length > 0;

  const clearAll = () =>
    setFilters(() => ({ status: null, city: null, hookTier: null, search: "" }));

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2.5 px-8 py-3 border-b border-border bg-surface/60"
      )}
    >
      <FilterLabel>filters</FilterLabel>

      <Select
        value={filters.status ?? ALL}
        onValueChange={(v) =>
          setFilters((p) => ({ ...p, status: v === ALL ? null : (v as LeadStatus) }))
        }
      >
        <SelectTrigger className="w-[140px] h-8 font-mono text-xs">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All statuses</SelectItem>
          {LEAD_STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.city ?? ALL}
        onValueChange={(v) =>
          setFilters((p) => ({ ...p, city: v === ALL ? null : v }))
        }
      >
        <SelectTrigger className="w-[140px] h-8 font-mono text-xs">
          <SelectValue placeholder="City" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All cities</SelectItem>
          {cities.map((c) => (
            <SelectItem key={c} value={c}>
              {c}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.hookTier != null ? String(filters.hookTier) : ALL}
        onValueChange={(v) =>
          setFilters((p) => ({
            ...p,
            hookTier: v === ALL ? null : (Number(v) as HookTier),
          }))
        }
      >
        <SelectTrigger className="w-[120px] h-8 font-mono text-xs">
          <SelectValue placeholder="Hook" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All tiers</SelectItem>
          {[1, 2, 3, 4, 5].map((t) => (
            <SelectItem key={t} value={String(t)}>
              T{t}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Input
        value={filters.search}
        onChange={(e) => setFilters((p) => ({ ...p, search: e.target.value }))}
        placeholder="Search company or owner…"
        className="h-8 w-[240px] font-mono text-xs"
      />

      {active && (
        <Button
          size="sm"
          variant="ghost"
          onClick={clearAll}
          className="h-8 text-text-mute hover:text-text"
        >
          <X className="h-3.5 w-3.5" /> Clear
        </Button>
      )}
    </div>
  );
}

function FilterLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute pr-1">
      {children}
    </span>
  );
}
