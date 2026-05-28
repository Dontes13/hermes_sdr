import useSWR from "swr";
import { api } from "../api";
import type { WarmingSchedule } from "../types";

export function useWarmingSchedules() {
  return useSWR<WarmingSchedule[]>("warming-schedules", () => api.getWarmingSchedules(), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}
