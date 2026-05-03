import useSWR from "swr";
import { api } from "../api";
import type { LeadWithMessages } from "../types";

export function useLead(id: string | null | undefined) {
  return useSWR<LeadWithMessages>(
    id ? `lead/${id}` : null,
    () => api.getLead(id as string),
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    }
  );
}
