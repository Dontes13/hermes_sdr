import useSWR from "swr";
import { api } from "../api";
import type { Lead, LeadStatus } from "../types";

export function useLeads(status?: LeadStatus, limit: number = 200) {
  const key = status ? `leads?status=${status}&limit=${limit}` : `leads?limit=${limit}`;
  return useSWR<Lead[]>(key, () => api.getLeads(status, limit), {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });
}
