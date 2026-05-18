"use client";

import { useState } from "react";
import { Mail, Copy, Check, Loader2 } from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Lead {
  id: string;
  industry: string;
  businessName: string;
  businessType: string;
  location: string;
  context: string;
}

interface EmailResult {
  subject: string;
  body: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const DEFAULT_PROMPT = `You are an expert outreach copywriter for Helios Marketing, a digital marketing agency that builds AI-powered marketing systems for local and regional businesses.

Write a personalized cold outreach email to {BUSINESS_NAME}, a {BUSINESS_TYPE} in {LOCATION}.

Context about their business:
{BUSINESS_CONTEXT}

The email should:
- Open with a personalized hook referencing something specific about their business or industry
- Briefly introduce Helios Marketing and what we specialize in
- Call out 1-2 specific pain points relevant to their business type
- Show concretely how our AI marketing systems could help them
- End with a low-commitment CTA (e.g., a 15-minute call)
- Stay under 200 words for the body — tight and punchy

Format your response exactly as:
Subject: [subject line here]

[email body here]`;

const LEADS: Lead[] = [
  {
    id: "law-firm",
    industry: "Law Firm",
    businessName: "Sterling & Associates Law",
    businessType: "personal injury law firm",
    location: "Austin, TX",
    context:
      "A boutique 4-attorney personal injury firm relying heavily on referrals. They have a dated website, run occasional Google Ads with no real strategy, and have no CRM or follow-up automation in place.",
  },
  {
    id: "restaurant",
    industry: "Restaurant",
    businessName: "Casa Bella Italian Kitchen",
    businessType: "upscale Italian restaurant",
    location: "Nashville, TN",
    context:
      "Open for 6 years, known for ambiance and weekend reservations that fill up fast. They post inconsistently on Instagram, have no email marketing list, and weekday lunch traffic is slow.",
  },
  {
    id: "med-spa",
    industry: "Med Spa",
    businessName: "Glow Aesthetics Med Spa",
    businessType: "medical spa",
    location: "Scottsdale, AZ",
    context:
      "3 providers offering botox, fillers, laser treatments, and IV therapy. Loyal existing clientele but struggle to attract new patients in a competitive market. Run text promos but have no automated follow-up sequence.",
  },
  {
    id: "real-estate",
    industry: "Real Estate",
    businessName: "Pinnacle Properties Group",
    businessType: "luxury real estate agency",
    location: "Miami, FL",
    context:
      "12 agents focused on luxury residential. Generate leads from Zillow but have poor nurture sequences and an inconsistent social presence. No automated review collection system.",
  },
  {
    id: "fitness",
    industry: "Fitness Studio",
    businessName: "Iron & Grace Fitness",
    businessType: "boutique fitness studio",
    location: "Denver, CO",
    context:
      "Strength training and yoga studio with 20-member session capacity. Struggles with member churn, has no referral program, and relies entirely on word-of-mouth. Uses Mindbody for scheduling but has no marketing automation.",
  },
];

// Maps to CSS variables defined in globals.css :root
const INDUSTRY_COLOR: Record<string, string> = {
  "Law Firm":       "var(--tier-2)",  // blue
  Restaurant:       "var(--tier-4)",  // amber
  "Med Spa":        "var(--tier-1)",  // magenta
  "Real Estate":    "var(--tier-3)",  // green
  "Fitness Studio": "var(--info)",    // teal-blue
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function parseEmail(raw: string): EmailResult {
  const lines = raw.trim().split("\n");
  let subject = "";
  let bodyStart = 0;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toLowerCase().startsWith("subject:")) {
      subject = lines[i].replace(/^subject:\s*/i, "").trim();
      bodyStart = i + 1;
      while (bodyStart < lines.length && lines[bodyStart].trim() === "")
        bodyStart++;
      break;
    }
  }
  return { subject, body: lines.slice(bodyStart).join("\n").trim() };
}

async function callGemini(fullPrompt: string, apiKey: string): Promise<string> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: fullPrompt }] }],
        generationConfig: { temperature: 0.85, maxOutputTokens: 2048 },
      }),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as { error?: { message?: string } })?.error?.message ??
        `HTTP ${res.status}`
    );
  }
  const data = await res.json();
  const text: string = data?.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  if (!text) throw new Error("Empty response from Gemini");
  return text;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-2.5 p-4">
      <div className="h-2.5 w-3/4 bg-surface-2" />
      <div className="h-2.5 w-full bg-surface-2" />
      <div className="h-2.5 w-5/6 bg-surface-2" />
      <div className="h-2.5 w-full bg-surface-2" />
      <div className="h-2.5 w-2/3 bg-surface-2" />
      <div className="h-2.5 w-full bg-surface-2" />
      <div className="h-2.5 w-4/5 bg-surface-2" />
      <div className="mt-3 h-2.5 w-full bg-surface-2" />
      <div className="h-2.5 w-3/5 bg-surface-2" />
    </div>
  );
}

interface EmailCardProps {
  lead: Lead;
  result: EmailResult | undefined;
  error: string | undefined;
  isLoading: boolean;
  onCopy: () => Promise<void>;
}

function EmailCard({ lead, result, error, isLoading, onCopy }: EmailCardProps) {
  const [copied, setCopied] = useState(false);
  const color = INDUSTRY_COLOR[lead.industry] ?? "var(--text-mute)";

  async function handleCopy() {
    await onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex flex-col border border-border bg-surface">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">
            {lead.businessName}
          </p>
          <p className="text-[11px] text-text-mute">{lead.location}</p>
        </div>
        <span
          className="label-xs shrink-0 px-1.5 py-0.5"
          style={{
            color,
            background: `color-mix(in oklch, ${color} 14%, transparent)`,
          }}
        >
          {lead.industry}
        </span>
      </div>

      {/* Body */}
      <div className="flex-1">
        {isLoading ? (
          <LoadingSkeleton />
        ) : error ? (
          <div className="m-4 border border-border bg-surface-2 px-3 py-2.5 text-[11px] text-text-mute">
            {error}
          </div>
        ) : result ? (
          <div className="space-y-3 p-4">
            {result.subject && (
              <div className="bg-surface-2 px-3 py-2.5">
                <div className="label-xs mb-1">SUBJECT</div>
                <p className="text-sm font-medium text-text leading-snug">
                  {result.subject}
                </p>
              </div>
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-dim">
              {result.body}
            </p>
          </div>
        ) : null}
      </div>

      {/* Footer */}
      {result && !isLoading && (
        <div className="border-t border-border px-4 py-2.5">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-[11px] text-text-mute transition-colors hover:text-text"
          >
            {copied ? (
              <>
                <Check
                  className="h-3 w-3"
                  style={{ color: "var(--accent)" }}
                />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                Copy email
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AJsLabPage() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [results, setResults] = useState<Record<string, EmailResult>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [generating, setGenerating] = useState(false);
  const [globalError, setGlobalError] = useState("");

  const hasResults = Object.keys(results).length > 0 || loadingIds.size > 0;

  async function handleGenerate() {
    const apiKey = process.env.NEXT_PUBLIC_GEMINI_API_KEY;
    if (!apiKey) {
      setGlobalError(
        "NEXT_PUBLIC_GEMINI_API_KEY is not set. Add it to .env.local and restart."
      );
      return;
    }
    setGlobalError("");
    setResults({});
    setErrors({});
    setGenerating(true);
    setLoadingIds(new Set(LEADS.map((l) => l.id)));

    await Promise.all(
      LEADS.map(async (lead) => {
        const fullPrompt = prompt
          .replace(/\{BUSINESS_NAME\}/g, lead.businessName)
          .replace(/\{BUSINESS_TYPE\}/g, lead.businessType)
          .replace(/\{LOCATION\}/g, lead.location)
          .replace(/\{BUSINESS_CONTEXT\}/g, lead.context);
        try {
          const text = await callGemini(fullPrompt, apiKey);
          setResults((prev) => ({ ...prev, [lead.id]: parseEmail(text) }));
        } catch (e) {
          setErrors((prev) => ({
            ...prev,
            [lead.id]: e instanceof Error ? e.message : "Unknown error",
          }));
        } finally {
          setLoadingIds((prev) => {
            const next = new Set(prev);
            next.delete(lead.id);
            return next;
          });
        }
      })
    );

    setGenerating(false);
  }

  async function copyLead(lead: Lead) {
    const r = results[lead.id];
    if (!r) return;
    await navigator.clipboard.writeText(
      r.subject ? `Subject: ${r.subject}\n\n${r.body}` : r.body
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-6">
        {/* Logo mark */}
        <div
          className="flex h-7 w-7 shrink-0 items-center justify-center text-sm font-bold text-white"
          style={{ background: "var(--accent)" }}
        >
          H
        </div>
        <span className="text-sm font-semibold text-text">Helios SDR</span>
        <span className="text-text-mute">/</span>
        <span className="text-sm font-semibold text-text">AJ&apos;s Lab</span>
        {/* Beta badge */}
        <span
          className="label-xs px-1.5 py-0.5"
          style={{
            color: "var(--accent)",
            background: "color-mix(in oklch, var(--accent) 12%, transparent)",
          }}
        >
          BETA
        </span>
        <span className="ml-auto hidden text-[11px] text-text-mute sm:block">
          Gemini 2.5 Flash · 5 leads
        </span>
      </header>

      {/* Body — sidebar + main */}
      <div className="flex min-h-0 flex-1">
        {/* Left sidebar */}
        <aside className="flex w-80 shrink-0 flex-col overflow-y-auto border-r border-border bg-surface">
          {/* Prompt editor */}
          <div className="border-b border-border">
            <div className="border-b border-border px-4 py-2.5 label-xs">
              SYSTEM PROMPT
            </div>
            <div className="p-4">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={14}
                spellCheck={false}
                className="w-full resize-y border border-border bg-background px-3 py-2.5 text-[13px] leading-relaxed text-text outline-none focus:border-brand"
              />
              <p className="mt-2 text-[11px] leading-relaxed text-text-mute">
                Placeholders:{" "}
                {[
                  "{BUSINESS_NAME}",
                  "{BUSINESS_TYPE}",
                  "{LOCATION}",
                  "{BUSINESS_CONTEXT}",
                ].map((p) => (
                  <code
                    key={p}
                    className="mx-0.5 border border-border bg-surface-2 px-1 py-px font-mono text-[10px] text-text-dim"
                  >
                    {p}
                  </code>
                ))}
              </p>
            </div>
          </div>

          {/* Lead list */}
          <div className="flex-1 border-b border-border">
            <div className="border-b border-border px-4 py-2.5 label-xs">
              SAMPLE LEADS
            </div>
            <ul className="divide-y divide-border">
              {LEADS.map((lead) => {
                const color =
                  INDUSTRY_COLOR[lead.industry] ?? "var(--text-mute)";
                return (
                  <li key={lead.id} className="flex items-start gap-3 px-4 py-3">
                    <span
                      className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: color }}
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text">
                        {lead.businessName}
                      </p>
                      <div className="mt-0.5 flex items-center gap-2">
                        <span className="label-xs" style={{ color }}>
                          {lead.industry}
                        </span>
                        <span className="text-[11px] text-text-mute">
                          {lead.location}
                        </span>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Generate */}
          <div className="p-4 space-y-3">
            {globalError && (
              <p className="border border-border bg-surface-2 px-3 py-2.5 text-[11px] leading-relaxed text-text-mute">
                {globalError}
              </p>
            )}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex w-full items-center justify-center gap-2 bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating&hellip;
                </>
              ) : (
                "Generate 5 Emails"
              )}
            </button>
          </div>
        </aside>

        {/* Right — results */}
        <main className="min-w-0 flex-1 overflow-y-auto bg-background">
          {!hasResults ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <Mail
                className="h-8 w-8 text-text-mute"
                strokeWidth={1.2}
              />
              <p className="text-sm font-medium text-text-dim">
                No emails generated yet
              </p>
              <p className="text-[11px] text-text-mute">
                Edit the prompt on the left, then click Generate.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">
              {LEADS.map((lead) => (
                <EmailCard
                  key={lead.id}
                  lead={lead}
                  result={results[lead.id]}
                  error={errors[lead.id]}
                  isLoading={loadingIds.has(lead.id)}
                  onCopy={() => copyLead(lead)}
                />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
