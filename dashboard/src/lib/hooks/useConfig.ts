import useSWR from "swr";
import { api } from "../api";
import type { ConfigMap } from "../types";

export function useConfig() {
  return useSWR<ConfigMap>("config", () => api.getConfig(), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}
