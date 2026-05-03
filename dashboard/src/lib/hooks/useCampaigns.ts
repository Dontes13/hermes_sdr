import useSWR from "swr";
import { api } from "../api";
import type { Campaign, Lead } from "../types";

export function useCampaigns() {
  return useSWR<Campaign[]>("campaigns", () => api.listCampaigns(), {
    refreshInterval: 60_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });
}

export function useCampaign(id: string | undefined) {
  return useSWR<Campaign>(id ? `campaigns/${id}` : null, () =>
    api.getCampaign(id!)
  );
}

export function useCampaignLeads(id: string | undefined) {
  return useSWR<Lead[]>(id ? `campaigns/${id}/leads` : null, () =>
    api.getCampaignLeads(id!)
  );
}
