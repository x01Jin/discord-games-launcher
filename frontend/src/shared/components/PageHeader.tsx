import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <header className="flex h-[52px] shrink-0 items-center justify-between gap-4 border-b border-line px-5">
      <div className="min-w-0">
        <h1 className="truncate text-[15px] font-semibold leading-5 text-ink">
          {title}
        </h1>
        {subtitle ? (
          <p className="truncate text-[12px] leading-4 text-subtle">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Toolbar({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[44px] shrink-0 items-center gap-3 border-b border-line px-5 py-1.5">
      {children}
    </div>
  );
}
