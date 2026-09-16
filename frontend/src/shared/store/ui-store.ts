import { create } from "zustand";

export type Tab = "catalogue" | "library";
export type ToastKind = "info" | "success" | "error";

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

interface UiState {
  tab: Tab;
  search: string;
  selected: string[];
  statsOpen: boolean;
  toasts: Toast[];
  catalogueTotal: number;
  catalogueShowing: number;
  setTab: (tab: Tab) => void;
  setSearch: (search: string) => void;
  setCatalogueCounts: (total: number, showing: number) => void;
  toggleSelected: (id: string) => void;
  clearSelected: () => void;
  setStatsOpen: (open: boolean) => void;
  pushToast: (message: string, kind?: ToastKind) => void;
  dismissToast: (id: number) => void;
}

let toastId = 0;

/** UI-only state (server state lives in React Query). */
export const useUiStore = create<UiState>((set) => ({
  tab: "catalogue",
  search: "",
  selected: [],
  statsOpen: false,
  toasts: [],
  catalogueTotal: 0,
  catalogueShowing: 0,
  setTab: (tab) => set({ tab }),
  setSearch: (search) => set({ search }),
  setCatalogueCounts: (total, showing) =>
    set({ catalogueTotal: total, catalogueShowing: showing }),
  toggleSelected: (id) =>
    set((s) => ({
      selected: s.selected.includes(id)
        ? s.selected.filter((x) => x !== id)
        : [...s.selected, id],
    })),
  clearSelected: () => set({ selected: [] }),
  setStatsOpen: (open) => set({ statsOpen: open }),
  pushToast: (message, kind = "info") => {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts.slice(-3), { id, message, kind }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
