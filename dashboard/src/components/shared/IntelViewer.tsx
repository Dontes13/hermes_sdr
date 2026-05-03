"use client";

import { useState } from "react";
import {
  Building2,
  Globe,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Star,
  User,
  ListChecks,
  MapPin,
  AlertTriangle,
} from "lucide-react";
import type { Lead } from "@/lib/types";
import { cn } from "@/lib/utils";

interface IntelViewerProps {
  lead: Lead;
  className?: string;
}

interface SectionProps {
  label: string;
  icon: React.ElementType;
  children: React.ReactNode;
}

function Section({ label, icon: Icon, children }: SectionProps) {
  return (
    <section className="space-y-2">
      <header className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] text-text-mute">
        <Icon className="h-3.5 w-3.5" strokeWidth={1.4} aria-hidden />
        <span>{label}</span>
      </header>
      <div className="space-y-1.5 text-sm">{children}</div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm leading-relaxed">
      <div className="font-mono text-[11px] uppercase tracking-wider text-text-mute pt-[2px]">
        {label}
      </div>
      <div className="text-text">{value}</div>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="inline-flex items-center border border-border bg-surface-2 px-2 py-0.5 text-xs font-mono text-text-dim"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function asString(v: unknown): string | null {
  if (typeof v === "string" && v.trim().length > 0) return v;
  return null;
}
function asNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return null;
}
function asArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string" && x.length > 0);
}

export function IntelViewer({ lead, className }: IntelViewerProps) {
  const [rawOpen, setRawOpen] = useState(false);
  const intel = lead.intel_json ?? {};

  const slogan = asString(intel["slogan"]);
  const valueProp = asString(intel["value_prop"]);
  const specialties = asArray(intel["specialties"]);
  const notableFacts = asArray(intel["notable_facts"]);
  const markets = asArray(intel["markets_served"]);
  const yearFounded = asNumber(intel["year_founded"]);
  const agentCount = asNumber(intel["agent_count"]);
  const scrapeError = asString(intel["scrape_error"]);
  const deadReason = asString(intel["dead_reason"]);
  const currentYear = new Date().getFullYear();

  const hasCompany = !!(markets.length || yearFounded || agentCount || lead.city);
  const hasBrand = !!(slogan || valueProp || specialties.length);
  const hasReputation = lead.google_rating != null || lead.google_reviews != null;
  const hasOwner = !!(lead.owner_name || lead.email || lead.phone);
  const hasWeb = !!(lead.website || scrapeError || deadReason);
  const hasNotable = notableFacts.length > 0;

  return (
    <div className={cn("space-y-6", className)}>
      {hasCompany && (
        <Section label="Company" icon={Building2}>
          <Field label="Name" value={lead.company} />
          <Field
            label="Location"
            value={
              <span>
                {lead.city}
                {markets.length > 0 && (
                  <span className="text-text-dim"> · {markets.join(", ")}</span>
                )}
              </span>
            }
          />
          {yearFounded && (
            <Field
              label="Founded"
              value={
                <span>
                  {yearFounded}{" "}
                  <span className="text-text-dim">
                    ({currentYear - yearFounded} yrs)
                  </span>
                </span>
              }
            />
          )}
          {agentCount != null && (
            <Field label="Agents" value={<span className="metric">{agentCount}</span>} />
          )}
        </Section>
      )}

      {hasBrand && (
        <Section label="Brand" icon={Sparkles}>
          {slogan && <Field label="Slogan" value={<span className="italic">“{slogan}”</span>} />}
          {valueProp && <Field label="Value Prop" value={valueProp} />}
          {specialties.length > 0 && (
            <Field label="Specialties" value={<Chips items={specialties} />} />
          )}
        </Section>
      )}

      {hasReputation && (
        <Section label="Reputation" icon={Star}>
          {lead.google_rating != null && (
            <Field
              label="Google Rating"
              value={
                <span className="metric flex items-center gap-2">
                  <Star
                    className="h-3.5 w-3.5 fill-current"
                    style={{ color: "var(--tier-4)" }}
                  />
                  <span>{lead.google_rating.toFixed(1)}</span>
                  {lead.google_reviews != null && (
                    <span className="text-text-dim">
                      · {lead.google_reviews} reviews
                    </span>
                  )}
                </span>
              }
            />
          )}
        </Section>
      )}

      {hasOwner && (
        <Section label="Contact" icon={User}>
          {lead.owner_name && <Field label="Owner" value={lead.owner_name} />}
          {lead.email && (
            <Field
              label="Email"
              value={<span className="font-mono text-xs">{lead.email}</span>}
            />
          )}
          {lead.phone && (
            <Field
              label="Phone"
              value={<span className="font-mono text-xs">{lead.phone}</span>}
            />
          )}
        </Section>
      )}

      {hasWeb && (
        <Section label="Web Footprint" icon={Globe}>
          {lead.website && (
            <Field
              label="Website"
              value={
                <a
                  href={lead.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand underline underline-offset-2 font-mono text-xs break-all"
                >
                  {lead.website}
                </a>
              }
            />
          )}
          {(scrapeError || deadReason) && (
            <Field
              label="Notes"
              value={
                <span
                  className="inline-flex items-center gap-1.5 text-xs"
                  style={{ color: "var(--danger)" }}
                >
                  <AlertTriangle className="h-3 w-3" />
                  {scrapeError ?? deadReason}
                </span>
              }
            />
          )}
        </Section>
      )}

      {hasNotable && (
        <Section label="Notable Facts" icon={ListChecks}>
          <ul className="list-none space-y-1 font-mono text-xs text-text-dim">
            {notableFacts.map((f, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-text-mute">→</span>
                <span className="text-text leading-relaxed font-sans text-sm">{f}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {!hasCompany && !hasBrand && !hasReputation && !hasOwner && !hasWeb && !hasNotable && (
        <div className="flex items-center gap-2 text-sm text-text-mute">
          <MapPin className="h-4 w-4" />
          <span>No intel captured yet. Run enrichment to populate.</span>
        </div>
      )}

      <div className="pt-2 border-t border-border">
        <button
          type="button"
          onClick={() => setRawOpen((v) => !v)}
          className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-text-mute hover:text-text-dim transition-colors"
        >
          {rawOpen ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          Raw JSON
        </button>
        {rawOpen && (
          <pre className="mt-2 overflow-x-auto border border-border bg-bg/60 p-3 text-[11px] leading-relaxed text-text-dim font-mono">
            {JSON.stringify(intel, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
