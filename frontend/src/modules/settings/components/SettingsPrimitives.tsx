import type { ReactNode } from "react";
import type { SilentLauncher } from "../../../shared/api-client";
import { Chip } from "../../../shared/components/primitives";

export function Panel({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-[8px] border border-line bg-raised/50">
      <div className="flex items-start justify-between gap-4 px-4 pt-3.5">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
          {description ? (
            <p className="mt-1 text-[12px] leading-[18px] text-subtle">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2 pt-0.5">{actions}</div>
        ) : null}
      </div>
      {children ? <div className="px-4 pb-3.5 pt-2">{children}</div> : null}
    </section>
  );
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-line/70 py-2 first:border-t-0">
      <span className="shrink-0 text-[12px] text-subtle">{label}</span>
      <span className="min-w-0 truncate text-right text-[12px] text-muted">
        {children}
      </span>
    </div>
  );
}

export function LauncherRow({ launcher }: { launcher: SilentLauncher }) {
  return (
    <li className="rounded-[6px] border border-line bg-base/40 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-medium text-ink">{launcher.kind}</span>
        <Chip tone={launcher.patched ? "success" : "neutral"}>
          {launcher.patched ? "Patched" : "Original"}
        </Chip>
      </div>
      <p className="mt-1 truncate text-[11px] text-subtle" title={launcher.location}>
        {launcher.location}
      </p>
      <code className="mt-1 block whitespace-pre-wrap break-words font-mono text-[11px] leading-4 text-subtle">
        {launcher.arguments}
      </code>
    </li>
  );
}
