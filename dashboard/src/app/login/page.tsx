"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Terminal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const setToken = useAuthStore((s) => s.setToken);
  const status = useAuthStore((s) => s.status);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorFlash, setErrorFlash] = useState(false);

  useEffect(() => {
    if (status === "authed") {
      router.replace("/pipeline");
    }
  }, [status, router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password) return;
    setSubmitting(true);
    try {
      const { token } = await api.login(password);
      setToken(token);
      router.replace("/pipeline");
    } catch (e) {
      toast.error(`Invalid password: ${errorMessage(e)}`);
      setErrorFlash(true);
      setTimeout(() => setErrorFlash(false), 500);
      setSubmitting(false);
    }
  };

  return (
    <main
      className="relative min-h-screen grid place-items-center px-6 overflow-hidden"
      style={{
        backgroundImage:
          "radial-gradient(ellipse 60% 45% at 50% 38%, color-mix(in oklch, var(--accent) 8%, transparent), transparent 70%)",
      }}
    >
      {/* Subtle grid backdrop — pure CSS, zero network cost */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(var(--text) 1px, transparent 1px), linear-gradient(90deg, var(--text) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="relative w-full max-w-sm">
        <div
          className={cn(
            "border border-border bg-surface transition-shadow duration-200",
            errorFlash && "animate-flash-danger"
          )}
        >
          <div className="flex items-center gap-2 border-b border-border px-4 py-2 label-xs">
            <Terminal className="h-3 w-3" strokeWidth={1.6} />
            <span>auth / helios-sdr</span>
            <span
              className="ml-auto h-1.5 w-1.5 rounded-full"
              style={{
                background: "var(--accent)",
                boxShadow: "var(--accent-glow-soft)",
              }}
            />
          </div>

          <div className="px-6 py-7 space-y-6">
            <div className="space-y-1.5">
              <h1 className="text-lg font-semibold text-text tracking-tight">
                Sign in
              </h1>
              <p className="label-xs">password required</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                placeholder="••••••••"
                className="font-mono"
                disabled={submitting}
              />
              <Button
                type="submit"
                disabled={submitting || !password}
                className="w-full font-mono uppercase text-[11px] tracking-wider"
              >
                {submitting ? "Signing in…" : "Sign in →"}
              </Button>
            </form>
          </div>

          <div className="border-t border-border px-4 py-2.5 bg-surface-2/50 label-xs">
            <span className="text-text-dim">tip:</span> DASHBOARD_PASSWORD from
            your .env
          </div>
        </div>
      </div>
    </main>
  );
}
