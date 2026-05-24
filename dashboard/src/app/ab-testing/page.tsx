"use client";

import { TopBar } from "@/components/layout/TopBar";
import { VariantResultsTable } from "@/components/ab-testing/VariantResultsTable";

export default function AbTestingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="A/B Testing"
        eyebrow="Helios / Experiments"
        subtitle="Subject line variant performance"
      />

      <div className="flex-1 px-8 py-6 max-w-4xl w-full space-y-5">
        <VariantResultsTable />

        <p className="text-[11px] text-text-mute leading-relaxed">
          Statistical significance is not computed. With small sample sizes, treat these
          numbers as directional only. Wait for at least ~50 sends per variant before
          drawing conclusions.
        </p>
      </div>
    </div>
  );
}
