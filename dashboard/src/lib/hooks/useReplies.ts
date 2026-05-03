import useSWR from "swr";
import { api } from "../api";
import type { ReplyEntry } from "../types";

export function useReplies() {
  return useSWR<ReplyEntry[]>("replies", () => api.getReplies(), {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });
}
