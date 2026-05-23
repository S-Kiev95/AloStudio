import { create } from "zustand";

/**
 * Client/UI state (the Vuex/Pinia equivalent). Server state lives in
 * TanStack Query — keep this for ephemeral UI only (sidebar, modals,
 * active account, theme).
 */
type UiState = {
  sidebarOpen: boolean;
  activeAccountId: number | null;
  setSidebarOpen: (open: boolean) => void;
  setActiveAccountId: (id: number | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  activeAccountId: null,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveAccountId: (id) => set({ activeAccountId: id }),
}));
