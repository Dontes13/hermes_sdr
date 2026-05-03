import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AuthStatus = "idle" | "authed" | "unauthed";

interface AuthState {
  token: string | null;
  status: AuthStatus;
  setToken: (t: string | null) => void;
  logout: () => void;
  _hydrated: boolean;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      status: "idle",
      _hydrated: false,
      setToken: (t) => set({ token: t, status: t ? "authed" : "unauthed" }),
      logout: () => set({ token: null, status: "unauthed" }),
      setHydrated: () => set({ _hydrated: true }),
    }),
    {
      name: "helios_auth",
      partialize: (s) => ({ token: s.token }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.status = state.token ? "authed" : "unauthed";
          state.setHydrated();
        }
      },
    }
  )
);

/** Synchronously read the current token for the API client. */
export function getToken(): string | null {
  return useAuthStore.getState().token;
}
