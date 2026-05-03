"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/lib/auth";
import { Sidebar } from "@/components/layout/Sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    if (status === "unauthed") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "idle") {
    // Hydration in progress. Render a skeleton shell that mirrors the real
    // chrome so layout doesn't shift when auth resolves.
    return (
      <div className="flex min-h-screen">
        <div className="w-56 shrink-0 border-r border-border bg-surface" />
        <div className="flex-1 bg-background" />
      </div>
    );
  }

  if (status === "unauthed") {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 bg-background">{children}</main>
    </div>
  );
}
