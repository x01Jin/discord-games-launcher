import { create } from "zustand";

export type Page = "quests" | "running" | "catalogue" | "library" | "settings";
export type ToastKind = "info" | "success" | "error";

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

const PAGE_KEY = "dcgl.page";
const PAGES: Page[] = ["quests", "running", "catalogue", "library", "settings"];

function initialPage(): Page {
  try {
    const saved = localStorage.getItem(PAGE_KEY);
    if (saved && PAGES.includes(saved as Page)) return saved as Page;
  } catch {
    /* storage is optional */
  }
  return "quests";
}

interface UiState {
  page: Page;
  search: string;
  selected: string[];
  showFinished: boolean;
  toasts: Toast[];
  setPage: (page: Page) => void;
  setSearch: (search: string) => void;
  toggleSelected: (id: string) => void;
  clearSelected: () => void;
  setShowFinished: (show: boolean) => void;
  pushToast: (message: string, kind?: ToastKind) => void;
  dismissToast: (id: number) => void;
}

let toastId = 0;

/** UI-only state. Server state lives in React Query. */
export const useUiStore = create<UiState>((set, get) => ({
  page: initialPage(),
  search: "",
  selected: [],
  showFinished: false,
  toasts: [],

  setPage: (page) => {
    try {
      localStorage.setItem(PAGE_KEY, page);
    } catch {
      /* storage is optional */
    }
    set({ page });
  },

  setSearch: (search) => set({ search }),

  toggleSelected: (id) =>
    set((state) => ({
      selected: state.selected.includes(id)
        ? state.selected.filter((existing) => existing !== id)
        : [...state.selected, id],
    })),

  clearSelected: () => set({ selected: [] }),

  setShowFinished: (showFinished) => set({ showFinished }),

  pushToast: (message, kind = "info") => {
    const id = (toastId += 1);
    // Three at a time is enough to read; older ones fall off the top.
    set((state) => ({ toasts: [...state.toasts.slice(-2), { id, message, kind }] }));
    window.setTimeout(() => {
      if (get().toasts.some((toast) => toast.id === id)) {
        set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }));
      }
    }, 5000);
  },

  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}));
