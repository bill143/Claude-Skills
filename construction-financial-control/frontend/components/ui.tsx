"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

/* ---------- Buttons ---------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";
const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-accent hover:bg-blue-600 text-white font-medium",
  secondary: "bg-surface border border-border-default hover:border-border-strong text-primary",
  ghost: "bg-transparent hover:bg-hovered text-secondary hover:text-primary",
  danger:
    "bg-danger/10 hover:bg-danger text-danger hover:text-white border border-danger/30 font-medium",
  success:
    "bg-success/10 hover:bg-success text-success hover:text-white border border-success/30 font-medium",
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
      className={`inline-flex items-center justify-center gap-1.5 rounded-md transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-base ${buttonStyles[variant]} ${sizing} ${className}`}
      {...props}
    />
  );
}

/* ---------- Status badge ---------- */

const badgeTones: Record<string, string> = {
  DRAFT: "bg-border-default/40 text-secondary border-border-strong/40",
  PRICING: "bg-info/10 text-info border-info/20",
  SUBMITTED: "bg-accent/10 text-accent border-accent/20",
  PENDING_APPROVAL: "bg-amber/10 text-amber border-amber/20",
  PENDING: "bg-amber/10 text-amber border-amber/20",
  APPROVED: "bg-success/10 text-success border-success/20",
  CONVERTED: "bg-info/10 text-info border-info/20",
  REJECTED: "bg-danger/10 text-danger border-danger/20",
  VOID: "bg-border-default/40 text-muted border-border-strong/40",
  CLOSED: "bg-border-default/40 text-secondary border-border-strong/40",
  CANCELLED: "bg-border-default/40 text-muted border-border-strong/40",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = badgeTones[status] ?? badgeTones.DRAFT;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.replace(/_/g, " ")}
    </span>
  );
}

/* ---------- KPI card ---------- */

export function KpiCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub?: React.ReactNode;
  tone?: "default" | "success" | "danger" | "amber" | "muted";
}) {
  const valueTone =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-danger"
        : tone === "amber"
          ? "text-amber"
          : "text-primary";
  return (
    <div className="rounded-lg border border-border-default bg-surface p-5">
      <p className="text-xs uppercase tracking-widest text-muted">{label}</p>
      <p className={`mt-2 font-mono text-2xl tabular-nums ${valueTone}`}>{value}</p>
      {sub ? <div className="mt-1 text-sm text-secondary">{sub}</div> : null}
    </div>
  );
}

/* ---------- Modal ---------- */

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
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
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-[8vh]"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={`w-full ${wide ? "max-w-3xl" : "max-w-lg"} animate-fade-in-scale rounded-lg border border-border-default bg-surface shadow-2xl`}
      >
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <h2 className="font-display text-lg text-primary">{title}</h2>
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
      <span className="mb-1.5 block text-xs uppercase tracking-wider text-muted">
        {label} {required ? <span className="text-danger">*</span> : null}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

export const inputClass =
  "w-full h-9 rounded-md border border-border-default bg-elevated px-3 text-sm text-primary " +
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
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-default py-14 text-center">
      <p className="font-display text-lg text-primary">{title}</p>
      <p className="max-w-sm text-sm text-secondary">{body}</p>
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
  "px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted whitespace-nowrap";
export const thRight = `${th} text-right`;
export const td = "px-3 py-2 text-sm whitespace-nowrap";
export const tdMono = `${td} font-mono tabular-nums text-right`;
