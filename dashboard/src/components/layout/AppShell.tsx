"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/auth";
import { Sidebar } from "@/components/layout/Sidebar";

const UNSHELLED_ROUTES = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const status = useAuthStore((s) => s.status);
  const noShell = UNSHELLED_ROUTES.includes(pathname);

  useEffect(() => {
    if (!noShell && status === "unauthed") {
      router.replace("/login");
    }
  }, [status, router, noShell]);

  if (noShell) {
    return <>{children}</>;
  }

  if (status === "idle") {
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
