import useSWR from "swr";
import { api } from "../api";
import type { Inbox } from "../types";

export function useInboxes() {
  return useSWR<Inbox[]>("inboxes", () => api.getInboxes(), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}
