"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  CheckSquare,
  FlaskConical,
  MessageSquare,
  Users,
  Settings,
  Target,
  Sparkles,
} from "lucide-react";

import { useStats } from "@/lib/hooks/useStats";
import { useCampaigns } from "@/lib/hooks/useCampaigns";
import { cn } from "@/lib/utils";
import { LogoutButton } from "./LogoutButton";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  badgeKey?: "approvals" | "replies" | "campaigns";
}

const NAV: NavItem[] = [
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/campaigns", label: "Campaigns", icon: Target, badgeKey: "campaigns" },
  { href: "/approvals", label: "Approvals", icon: CheckSquare, badgeKey: "approvals" },
  { href: "/replies", label: "Replies", icon: MessageSquare, badgeKey: "replies" },
  { href: "/ab-testing", label: "A/B Testing", icon: FlaskConical },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/chat", label: "Chat", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: stats } = useStats();
  const { data: campaigns } = useCampaigns();

  const badges = {
    approvals: stats?.counts?.drafted ?? 0,
    replies: stats?.reply_drafts_pending ?? 0,
    campaigns: campaigns?.filter((c) => c.status === "active").length ?? 0,
  };

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-surface flex flex-col h-screen sticky top-0">
      {/* Logo + app name */}
      <div className="px-4 pt-5 pb-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-sm font-bold shrink-0"
            style={{ background: "var(--accent)" }}
          >
            H
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-mute leading-none">
              Helios SDR
            </div>
            <div className="text-[13px] font-semibold text-text leading-snug">
              Outbound Cockpit
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5">
        {NAV.map((item) => {
          const active =
            item.href === "/pipeline"
              ? pathname === "/pipeline"
              : pathname.startsWith(item.href);
          const badgeCount = item.badgeKey ? badges[item.badgeKey] : 0;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-2.5 px-2.5 py-1.5 text-sm transition-colors rounded-lg",
                active
                  ? "bg-[color:var(--accent)] text-white"
                  : "text-text-dim hover:bg-surface-2 hover:text-text"
              )}
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={1.6} />
              <span className="flex-1 text-[13px] font-medium">
                {item.label}
              </span>
              {badgeCount > 0 && (
                <span
                  className={cn(
                    "min-w-[18px] h-[18px] px-1 inline-flex items-center justify-center text-[10px] font-medium rounded-full",
                    active
                      ? "bg-white/20 text-white"
                      : item.badgeKey === "replies"
                        ? "bg-[color:var(--accent)]/10 text-[color:var(--accent)]"
                        : "bg-surface-2 text-text-mute"
                  )}
                >
                  {badgeCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User profile + sign out */}
      <div className="border-t border-border p-3 space-y-1">
        <div className="flex items-center gap-3 px-2.5 py-2 rounded-lg">
          <div
            className="h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-semibold shrink-0"
            style={{ background: "var(--accent)" }}
          >
            A
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-medium text-text">Admin</div>
            <div className="text-[11px] text-text-mute truncate">helios-sdr</div>
          </div>
        </div>
        <LogoutButton />
      </div>
    </aside>
  );
}
