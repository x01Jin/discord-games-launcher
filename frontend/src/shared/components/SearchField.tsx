import { useRef } from "react";
import { CloseIcon, SearchIcon } from "./icons";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  onEscape?: () => void;
}

export function SearchField({
  value,
  onChange,
  placeholder = "Search",
  autoFocus = false,
  onEscape,
}: Props) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <div className="group relative flex h-8 w-full items-center rounded-[4px] bg-base">
      <span className="pointer-events-none absolute left-2.5 text-subtle">
        <SearchIcon size={14} />
      </span>
      <input
        ref={ref}
        type="search"
        value={value}
        autoFocus={autoFocus}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            if (value) onChange("");
            else onEscape?.();
            ref.current?.blur();
          }
        }}
        className="h-full w-full bg-transparent pl-8 pr-8 text-[13px] text-ink placeholder:text-faint focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {value ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            onChange("");
            ref.current?.focus();
          }}
          className="absolute right-1.5 flex size-5 items-center justify-center rounded text-subtle hover:bg-hover hover:text-ink"
        >
          <CloseIcon size={12} />
        </button>
      ) : null}
    </div>
  );
}
