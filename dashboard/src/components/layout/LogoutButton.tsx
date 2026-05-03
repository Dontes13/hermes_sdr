"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth";

export function LogoutButton() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <button
      type="button"
      onClick={handleLogout}
      className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[12px] text-text-mute hover:text-text transition-colors rounded-lg hover:bg-surface-2"
    >
      <LogOut className="h-3 w-3" strokeWidth={1.6} />
      <span>Sign out</span>
    </button>
  );
}
