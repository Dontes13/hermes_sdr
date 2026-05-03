import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ReplyIntent } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * `hook_rationale` is overloaded: cold outbound stores Gemini's reasoning
 * prose, but reply drafts store the literal `reply_intent=<intent>` string
 * (see agent/src/functions/draft_reply.py). Never render it raw on reply
 * drafts — always parse with this helper first.
 */
export function parseReplyIntent(rationale: string | null | undefined): ReplyIntent | null {
  if (!rationale) return null;
  const m = rationale.match(/^reply_intent=(\w+)$/);
  if (!m) return null;
  const intent = m[1] as ReplyIntent;
  return intent;
}

/** Format ISO timestamp as "X min ago" / "X hr ago" / "X days ago". */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 0) return "just now";
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  const yr = Math.floor(mo / 12);
  return `${yr}y ago`;
}

/** Format ISO timestamp as "Apr 15, 14:32". */
export function formatShortDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Format ISO timestamp as "Apr 15 2026". */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Truncate a string to max chars, adding an ellipsis if cut. */
export function truncate(s: string | null | undefined, max: number): string {
  if (!s) return "";
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + "…";
}

/** Pad/format an integer count with leading zeros to a given width. Used for
 * the terminal-style stat blocks. */
export function padCount(n: number, width: number = 2): string {
  return String(n).padStart(width, "0");
}
