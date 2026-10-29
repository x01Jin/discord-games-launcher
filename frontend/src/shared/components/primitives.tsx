import type { ButtonHTMLAttributes, ReactNode } from "react";
import { CheckIcon, SpinnerIcon } from "./icons";

/* --------------------------------------------------------------------------
 * Button
 * ----------------------------------------------------------------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";
type ButtonSize = "sm" | "md";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover active:bg-accent-press",
  secondary:
    "bg-active/60 text-ink hover:bg-active border border-line-strong",
  ghost: "bg-transparent text-muted hover:bg-hover hover:text-ink",
  danger: "bg-danger text-white hover:bg-danger-hover",
  success: "bg-success text-white hover:brightness-110",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-[12px] gap-1.5 rounded-[4px]",
  md: "h-8 px-3 text-[13px] gap-1.5 rounded-[4px]",
};

export function Button({
  variant = "secondary",
  size = "md",
  busy = false,
  icon,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  busy?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={[
        "inline-flex select-none items-center justify-center font-medium",
        "transition-colors duration-100 disabled:opacity-50",
        SIZES[size],
        VARIANTS[variant],
        className,
      ].join(" ")}
      {...rest}
    >
      {busy ? <SpinnerIcon size={14} /> : icon}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  size = 30,
  active = false,
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  size?: number;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      style={{ width: size, height: size }}
      className={[
        "inline-flex shrink-0 items-center justify-center rounded-[4px]",
        "text-subtle transition-colors duration-100",
        active ? "bg-active text-ink" : "hover:bg-hover hover:text-ink",
        "disabled:opacity-40 disabled:hover:bg-transparent",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------------------------
 * Chip / status dot
 * ----------------------------------------------------------------------- */

type ChipTone = "neutral" | "accent" | "success" | "warning" | "danger" | "orb";

const CHIP_TONES: Record<ChipTone, string> = {
  neutral: "bg-white/[0.07] text-muted",
  accent: "bg-accent/20 text-[#b8bdff]",
  success: "bg-success/15 text-[#57d98a]",
  warning: "bg-warning/15 text-[#f5c451]",
  danger: "bg-danger/15 text-[#ff8f8f]",
  orb: "bg-warning/12 text-warning",
};

export function Chip({
  tone = "neutral",
  icon,
  children,
  title,
}: {
  tone?: ChipTone;
  icon?: ReactNode;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={[
        "inline-flex shrink-0 items-center gap-1 rounded-[4px] px-1.5 py-0.5",
        "text-[11px] font-semibold leading-4 whitespace-nowrap",
        CHIP_TONES[tone],
      ].join(" ")}
    >
      {icon}
      {children}
    </span>
  );
}

export function StatusDot({
  tone = "neutral",
  pulse = false,
}: {
  tone?: "neutral" | "success" | "warning" | "danger";
  pulse?: boolean;
}) {
  const color =
    tone === "success"
      ? "bg-success"
      : tone === "warning"
        ? "bg-warning"
        : tone === "danger"
          ? "bg-danger"
          : "bg-faint";
  return (
    <span
      aria-hidden="true"
      className={"inline-block size-2 shrink-0 rounded-full " + color}
      style={pulse ? { animation: "dcgl-pulse 2s ease-in-out infinite" } : undefined}
    />
  );
}

/* --------------------------------------------------------------------------
 * Progress
 * ----------------------------------------------------------------------- */

export function ProgressBar({
  value,
  tone = "accent",
  label,
}: {
  value: number;
  tone?: "accent" | "success" | "warning";
  label?: string;
}) {
  const pct = Math.max(0, Math.min(100, value * 100));
  const fill =
    tone === "success" ? "bg-success" : tone === "warning" ? "bg-warning" : "bg-accent";
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
      className="h-1 w-full overflow-hidden rounded-full bg-white/10"
    >
      <div
        className={"h-full rounded-full transition-[width] duration-300 " + fill}
        style={{ width: pct + "%" }}
      />
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Switch
 * ----------------------------------------------------------------------- */

export function Switch({
  checked,
  onChange,
  label,
  hideLabel = false,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  /** The label is still exposed to assistive tech, just not drawn. */
  hideLabel?: boolean;
}) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-2 text-[12px] text-muted">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={
          "relative h-4 w-7 shrink-0 rounded-full transition-colors duration-150 " +
          (checked ? "bg-accent" : "bg-white/15 hover:bg-white/20")
        }
      >
        <span
          className={
            "absolute top-0.5 size-3 rounded-full bg-white transition-[left] duration-150 " +
            (checked ? "left-3.5" : "left-0.5")
          }
        />
      </button>
      {hideLabel ? <span className="sr-only">{label}</span> : label}
    </label>
  );
}

/* --------------------------------------------------------------------------
 * Checkbox
 * ----------------------------------------------------------------------- */

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
  className = "",
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onChange(!checked);
      }}
      className={[
        "inline-flex size-4 shrink-0 items-center justify-center rounded-[3px] border transition-colors duration-100",
        checked
          ? "border-accent bg-accent text-white"
          : "border-line-strong bg-transparent text-transparent hover:border-muted hover:text-muted/40",
        "disabled:cursor-default disabled:opacity-40",
        className,
      ].join(" ")}
    >
      <CheckIcon size={11} strokeWidth={3} />
    </button>
  );
}

/* --------------------------------------------------------------------------
 * Placeholders and empty states
 * ----------------------------------------------------------------------- */

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={"animate-pulse rounded-[4px] bg-white/[0.06] " + className}
      style={{ animation: "dcgl-pulse 1.6s ease-in-out infinite" }}
    />
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      {icon ? <div className="text-faint">{icon}</div> : null}
      <div className="space-y-1">
        <p className="text-[14px] font-semibold text-ink">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-[13px] leading-5 text-subtle">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Layout helpers
 * ----------------------------------------------------------------------- */

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="px-2 pb-1 pt-4 text-[11px] font-bold uppercase tracking-[0.02em] text-subtle">
      {children}
    </p>
  );
}

export function Divider({ className = "" }: { className?: string }) {
  return <div className={"h-px w-full bg-line " + className} />;
}
