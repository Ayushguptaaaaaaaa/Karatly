import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { PeriodType, User } from "./api/types";

// ---- auth: localStorage when "remember me", else sessionStorage ----------------------
const hybrid: StateStorage = {
  getItem: (name) => {
    try {
      return localStorage.getItem(name) ?? sessionStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name, value) => {
    try {
      const remember = JSON.parse(value)?.state?.remember;
      (remember ? localStorage : sessionStorage).setItem(name, value);
      (remember ? sessionStorage : localStorage).removeItem(name);
    } catch {
      /* storage unavailable */
    }
  },
  removeItem: (name) => {
    try {
      localStorage.removeItem(name);
      sessionStorage.removeItem(name);
    } catch {
      /* ignore */
    }
  },
};

interface AuthState {
  token: string | null;
  expiresAt: string | null;
  user: User | null;
  remember: boolean;
  setAuth: (token: string, expiresAt: string, user: User, remember: boolean) => void;
  clear: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      expiresAt: null,
      user: null,
      remember: true,
      setAuth: (token, expiresAt, user, remember) => set({ token, expiresAt, user, remember }),
      clear: () => set({ token: null, expiresAt: null, user: null }),
    }),
    { name: "jaa.auth", storage: createJSONStorage(() => hybrid) },
  ),
);

export function isOwner(): boolean {
  return useAuth.getState().user?.role === "OWNER";
}

// ---- period shared by dashboard / stock / reports / insights ------------------------
interface PeriodState {
  period_type: PeriodType;
  anchor: string | null; // null = current
  setPeriod: (t: PeriodType, anchor: string | null) => void;
}

export const usePeriod = create<PeriodState>()((set) => ({
  period_type: "month",
  anchor: null,
  setPeriod: (period_type, anchor) => set({ period_type, anchor }),
}));

// ---- UI prefs ------------------------------------------------------------------------
interface UiState {
  navCollapsed: boolean;
  designView: "table" | "cards";
  live: "connecting" | "connected" | "offline";
  lastUpdatedAt: number | null;
  quickStockOpen: boolean;
  quickStockMode: "IN" | "OUT";
  quickStockDesignId: number | null;
  insightsSeenRunId: number | null;
  toggleNav: () => void;
  setDesignView: (v: "table" | "cards") => void;
  setLive: (s: UiState["live"]) => void;
  touch: () => void;
  openQuickStock: (mode?: "IN" | "OUT", designId?: number | null) => void;
  closeQuickStock: () => void;
  setInsightsSeen: (id: number) => void;
}

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      navCollapsed: false,
      designView: "table",
      live: "connecting",
      lastUpdatedAt: null,
      quickStockOpen: false,
      quickStockMode: "OUT",
      quickStockDesignId: null,
      insightsSeenRunId: null,
      toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),
      setDesignView: (designView) => set({ designView }),
      setLive: (live) => set({ live }),
      touch: () => set({ lastUpdatedAt: Date.now() }),
      openQuickStock: (mode = "OUT", designId = null) =>
        set({ quickStockOpen: true, quickStockMode: mode, quickStockDesignId: designId }),
      closeQuickStock: () => set({ quickStockOpen: false, quickStockDesignId: null }),
      setInsightsSeen: (id) => set({ insightsSeenRunId: id }),
    }),
    {
      name: "jaa.ui",
      partialize: (s) => ({ navCollapsed: s.navCollapsed, designView: s.designView, insightsSeenRunId: s.insightsSeenRunId }),
    },
  ),
);
