import { useUiStore } from "../store/ui-store";
import type { Tab } from "../store/ui-store";

const TABS: { id: Tab; label: string }[] = [
  { id: "catalogue", label: "Catalogue" },
  { id: "library", label: "My library" },
];

export function Tabs() {
  const tab = useUiStore((s) => s.tab);
  const setTab = useUiStore((s) => s.setTab);

  return (
    <nav
      aria-label="Main views"
      className="mt-5 flex items-center justify-center gap-10"
    >
      {TABS.map((t) => {
        const active = tab === t.id;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => setTab(t.id)}
            className={`relative pb-2 text-sm font-semibold tracking-[0.14em] uppercase ${
              active ? "text-peri" : "text-muted hover:text-white"
            }`}
          >
            {t.label}
            <span
              aria-hidden="true"
              className={`absolute inset-x-0 -bottom-px h-0.5 rounded-full ${
                active ? "bg-peri" : "bg-transparent"
              }`}
            />
          </button>
        );
      })}
    </nav>
  );
}
