import { useUiStore } from "../store/ui-store";

export function SearchBar({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const total = useUiStore((s) => s.catalogueTotal);
  const showing = useUiStore((s) => s.catalogueShowing);

  return (
    <div className="flex items-center justify-between gap-4">
      <input
        type="search"
        name="game-search"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search for games…"
        aria-label="Search for games"
        className="w-64 rounded-full bg-card px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none"
      />
      <p className="text-xs text-muted whitespace-nowrap">
        Showing {showing} of {total} games in catalogue
      </p>
    </div>
  );
}
