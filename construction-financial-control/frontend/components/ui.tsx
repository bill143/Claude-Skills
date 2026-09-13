"use client";

import { ArrowDownRight, ArrowUpRight, X } from "lucide-react";
import { useEffect } from "react";

/* ---------- Buttons ---------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";
const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white font-medium shadow-[0_0_0_1px_rgba(61,139,253,0.4),0_4px_14px_-6px_rgba(61,139,253,0.6)] hover:brightness-110",
  secondary:
    "bg-elevated border border-border-default hover:border-border-strong text-primary hover:bg-hovered",
  ghost: "bg-transparent hover:bg-hovered text-secondary hover:text-primary",
  danger:
    "bg-danger/10 hover:bg-danger text-danger hover:text-white border border-danger/30 font-medium",
  success:
    "bg-success/10 hover:bg-success text-success hover:text-inverse border border-success/30 font-medium",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
}) {
  const sizing = size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm";
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md transition-all duration-150 active:translate-y-px disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-base ${buttonStyles[variant]} ${sizing} ${className}`}
      {...props}
    />
  );
}

/* ---------- Status badge ---------- */

const badgeTones: Record<string, { cls: string; pulse?: boolean }> = {
  DRAFT: { cls: "bg-border-default/40 text-secondary border-border-strong/40" },
  PRICING: { cls: "bg-info/10 text-info border-info/25", pulse: true },
  SUBMITTED: { cls: "bg-accent/10 text-accent border-accent/25", pulse: true },
  PENDING_APPROVAL: { cls: "bg-amber/10 text-amber border-amber/25", pulse: true },
  PENDING: { cls: "bg-amber/10 text-amber border-amber/25", pulse: true },
  APPROVED: { cls: "bg-success/10 text-success border-success/25" },
  CONVERTED: { cls: "bg-info/10 text-info border-info/25" },
  REJECTED: { cls: "bg-danger/10 text-danger border-danger/25" },
  VOID: { cls: "bg-border-default/40 text-muted border-border-strong/40" },
  CLOSED: { cls: "bg-border-default/40 text-secondary border-border-strong/40" },
  CANCELLED: { cls: "bg-border-default/40 text-muted border-border-strong/40" },
};

export function StatusBadge({ status }: { status: string }) {
  const tone = badgeTones[status] ?? badgeTones.DRAFT;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium tracking-wide ${tone.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${tone.pulse ? "pulse-dot" : ""}`} />
      {status.replace(/_/g, " ")}
    </span>
  );
}

/* ---------- Document-type chip (PCO / OCO / SCO, vendor types) ---------- */

const typeTones: Record<string, string> = {
  PCO: "text-secondary border-border-strong/50 bg-border-default/30",
  OCO: "text-gold border-gold/30 bg-gold/10",
  SCO: "text-info border-info/25 bg-info/10",
  SUBCONTRACTOR: "text-info border-info/25 bg-info/10",
  SUPPLIER: "text-gold border-gold/30 bg-gold/10",
};

export function TypeChip({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex rounded border px-1.5 py-px font-mono text-[10px] font-medium tracking-wider ${
        typeTones[value] ?? typeTones.PCO
      }`}
    >
      {value}
    </span>
  );
}

/* ---------- Page header ---------- */

export function PageHeader({
  kicker,
  title,
  description,
  actions,
}: {
  kicker?: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        {kicker ? (
          <p className="mb-1 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
            {kicker}
          </p>
        ) : null}
        <h1 className="font-display text-[1.6rem] font-bold leading-tight text-primary">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-secondary">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/* ---------- Card ---------- */

export function Card({
  title,
  action,
  children,
  className = "",
  pad = true,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return (
    <section className={`panel overflow-hidden ${className}`}>
      {title ? (
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted">{title}</h2>
          {action}
        </div>
      ) : null}
      <div className={pad ? "p-4" : ""}>{children}</div>
    </section>
  );
}

/* ---------- Delta chip ---------- */

export function Delta({
  value,
  label,
  invert = false,
}: {
  value: number;
  label?: string;
  invert?: boolean;
}) {
  if (Math.abs(value) < 0.005) return null;
  const up = value > 0;
  const good = invert ? !up : up;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1 py-px font-mono text-[11px] tabular-nums ${
        good ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
      }`}
    >
      {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
      {label ?? `${Math.abs(value).toFixed(1)}%`}
    </span>
  );
}

/* ---------- Progress bar ---------- */

const barTones: Record<string, string> = {
  accent: "bg-accent",
  success: "bg-success",
  danger: "bg-danger",
  amber: "bg-amber",
  info: "bg-info",
  muted: "bg-border-strong",
};

export function ProgressBar({
  fraction,
  tone = "accent",
  className = "",
  animate = true,
}: {
  fraction: number;
  tone?: keyof typeof barTones;
  className?: string;
  animate?: boolean;
}) {
  const width = Math.max(0, Math.min(1, fraction)) * 100;
  return (
    <div className={`h-1 overflow-hidden rounded-full bg-inset ${className}`}>
      <div
        className={`h-full rounded-full ${barTones[tone]} ${animate ? "bar-grow" : ""}`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

/* ---------- KPI card ---------- */

export function KpiCard({
  label,
  value,
  sub,
  tone = "default",
  progress,
  progressTone = "accent",
  stagger = 0,
  hero = false,
}: {
  label: string;
  value: string;
  sub?: React.ReactNode;
  tone?: "default" | "success" | "danger" | "amber" | "muted";
  progress?: number;
  progressTone?: keyof typeof barTones;
  stagger?: number;
  hero?: boolean;
}) {
  const valueTone =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-danger"
        : tone === "amber"
          ? "text-amber"
          : tone === "muted"
            ? "text-secondary"
            : "text-primary";
  return (
    <div
      className="panel panel-hover rise p-4"
      style={{ "--stagger": stagger } as React.CSSProperties}
    >
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted">{label}</p>
      <p
        className={`figure mt-2 font-mono ${hero ? "text-3xl" : "text-[1.55rem]"} leading-none ${valueTone}`}
      >
        {value}
      </p>
      {progress !== undefined ? (
        <ProgressBar fraction={progress} tone={progressTone} className="mt-3" />
      ) : null}
      {sub ? <div className="mt-2 text-xs leading-relaxed text-secondary">{sub}</div> : null}
    </div>
  );
}

/* ---------- Segmented control ---------- */

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex rounded-md border border-border-default bg-inset p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
            value === option.value
              ? "bg-elevated text-primary shadow-[inset_0_0_0_1px_var(--border-strong)]"
              : "text-muted hover:text-secondary"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Modal ---------- */

export function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 pt-[8vh] backdrop-blur-[2px]"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={`panel w-full ${wide ? "max-w-3xl" : "max-w-lg"} animate-fade-in-scale shadow-2xl`}
      >
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div>
            <h2 className="font-display text-lg font-semibold text-primary">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-xs text-secondary">{subtitle}</p> : null}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded p-1 text-muted transition-colors hover:bg-hovered hover:text-primary"
          >
            <X size={18} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

/* ---------- Form primitives ---------- */

export function Field({
  label,
  required,
  children,
  hint,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
        {label} {required ? <span className="text-danger">*</span> : null}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-xs leading-relaxed text-muted">{hint}</span> : null}
    </label>
  );
}

export const inputClass =
  "w-full h-9 rounded-md border border-border-default bg-inset px-3 text-sm text-primary " +
  "placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent " +
  "transition-colors";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

/* ---------- States ---------- */

export function SkeletonRows({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4" aria-hidden>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-9 rounded-md" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-default bg-surface/40 py-16 text-center">
      {icon ? (
        <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-lg border border-border-default bg-elevated text-muted">
          {icon}
        </div>
      ) : null}
      <p className="font-display text-lg font-semibold text-primary">{title}</p>
      <p className="max-w-sm text-sm leading-relaxed text-secondary">{body}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
      {error}
    </p>
  );
}

/* ---------- Table helpers ---------- */

export const th =
  "px-3 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.14em] text-muted whitespace-nowrap";
export const thRight = `${th} text-right`;
export const td = "px-3 py-2.5 text-sm whitespace-nowrap";
export const tdMono = `${td} font-mono tabular-nums text-right`;

/** Standard table wrapper: panel chrome + horizontal scroll guard. */
export function TableShell({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`panel overflow-x-auto ${className}`}>
      <table className="w-full">{children}</table>
    </div>
  );
}

/* ---------- Approval chain stepper ---------- */

export function ChainStepper({
  steps,
}: {
  steps: { sequence: number; required_role: string; status: string }[];
}) {
  return (
    <ol className="space-y-0">
      {steps.map((step, index) => {
        const state =
          step.status === "APPROVED"
            ? "done"
            : step.status === "REJECTED"
              ? "rejected"
              : step.status === "PENDING"
                ? "active"
                : "idle";
        const dot =
          state === "done"
            ? "border-success bg-success/20 text-success"
            : state === "rejected"
              ? "border-danger bg-danger/20 text-danger"
              : state === "active"
                ? "border-amber bg-amber/15 text-amber"
                : "border-border-strong bg-elevated text-muted";
        return (
          <li key={step.sequence} className="relative flex items-center gap-3 py-1.5">
            {index < steps.length - 1 ? (
              <span className="absolute left-[11px] top-[26px] h-[calc(100%-14px)] w-px bg-border-default" />
            ) : null}
            <span
              className={`z-10 flex h-[23px] w-[23px] shrink-0 items-center justify-center rounded-full border font-mono text-[10px] ${dot} ${
                state === "active" ? "pulse-dot" : ""
              }`}
            >
              {step.sequence}
            </span>
            <span className="flex-1 text-xs text-secondary">
              {step.required_role.replace(/_/g, " ")}
            </span>
            <StatusBadge status={step.status} />
          </li>
        );
      })}
    </ol>
  );
}
