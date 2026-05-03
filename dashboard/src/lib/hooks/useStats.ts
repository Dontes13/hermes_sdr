import useSWR from "swr";
import { api } from "../api";
import type { Stats } from "../types";

export function useStats() {
  return useSWR<Stats>("stats", () => api.getStats(), {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });
}
