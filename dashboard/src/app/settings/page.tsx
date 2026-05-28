"use client";

import { TopBar } from "@/components/layout/TopBar";
import { ConfigEditor } from "@/components/settings/ConfigEditor";
import { InboxesEditor } from "@/components/settings/InboxesEditor";
import { TestSendCard } from "@/components/settings/TestSendCard";
import { VariantsEditor } from "@/components/settings/VariantsEditor";
import { Skeleton } from "@/components/ui/skeleton";
import { useConfig } from "@/lib/hooks/useConfig";
import { useSWRConfig } from "swr";

export default function SettingsPage() {
  const { data: config, isLoading } = useConfig();
  const { mutate } = useSWRConfig();

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar
        title="Settings"
        eyebrow="Helios / agent configuration"
        subtitle="Each field saves independently"
      />

      <div className="flex-1 px-8 py-6 max-w-4xl w-full space-y-5">
        {isLoading && !config ? (
          <>
            <Skeleton className="h-56 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-48 w-full" />
          </>
        ) : (
          <>
            <ConfigEditor
              config={config ?? {}}
              onSaved={() => mutate("config")}
              keys={["sender_name", "sender_title"]}
              title="Sender identity"
              description="How your outbound and reply emails introduce themselves. Applies to every campaign."
            />

            <ConfigEditor
              config={config ?? {}}
              onSaved={() => mutate("config")}
              keys={["target_cities"]}
              title="Targeting"
              description="Quick-pick cities shown in campaign and prospecting dialogs. Comma-separated."
            />

            <ConfigEditor
              config={config ?? {}}
              onSaved={() => mutate("config")}
              keys={["daily_lead_cap"]}
              title="Cadence & caps"
              description="Upper bound on leads processed per legacy daily_run. Campaign caps are set per-campaign."
            />

            <ConfigEditor
              config={config ?? {}}
              onSaved={() => mutate("config")}
              keys={["calendly_link"]}
              title="Integrations — Calendly"
              description="Reply agent surfaces this link when an inbound shows booking intent. Booking webhook goes to /webhooks/calendly."
            />

            <TestSendCard />

            <InboxesEditor />

            <VariantsEditor />
          </>
        )}
      </div>
    </div>
  );
}
