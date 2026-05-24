import useSWR from "swr";
import { api } from "../api";
import type { VariantStats } from "../types";

export function useVariantStats() {
  return useSWR<VariantStats[]>("variant-stats", () => api.getVariantStats(), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}
