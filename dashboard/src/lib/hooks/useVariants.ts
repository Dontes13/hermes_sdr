import useSWR from "swr";
import { api } from "../api";
import type { SubjectVariant } from "../types";

export function useVariants() {
  return useSWR<SubjectVariant[]>("variants", () => api.listVariants(), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}
