"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { login } from "@/lib/api";
import { Button, ErrorNote, Field, Input } from "@/components/ui";

const STATS: [string, string][] = [
  ["3,401", "CSI cost codes"],
  ["EAC / ETC", "live forecasting"],
  ["SHA-256", "audit chain"],
];

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div
        className="relative hidden flex-1 flex-col justify-between overflow-hidden border-r border-border-subtle bg-surface p-10 lg:flex"
        style={{
          backgroundImage:
            "radial-gradient(800px 400px at 20% 0%, rgba(61,139,253,0.10), transparent 60%), " +
            "radial-gradient(600px 400px at 90% 100%, rgba(56,197,221,0.06), transparent 55%), " +
            "linear-gradient(var(--border-subtle) 1px, transparent 1px), " +
            "linear-gradient(90deg, var(--border-subtle) 1px, transparent 1px)",
          backgroundSize: "auto, auto, 44px 44px, 44px 44px",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-gradient-to-br from-accent to-info font-display text-sm font-bold text-white shadow-[0_0_20px_-2px_var(--glow-accent)]">
            CF
          </div>
          <div>
            <p className="font-display text-lg font-bold leading-tight text-primary">CFCS</p>
            <p className="text-[9px] uppercase tracking-[0.24em] text-muted">Financial Control</p>
          </div>
        </div>
        <div className="max-w-md">
          <p className="rise mb-4 inline-flex items-center gap-1.5 rounded-full border border-border-default bg-elevated px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-success" /> Construction cost command
            center
          </p>
          <h1
            className="rise font-display text-[2.6rem] font-bold leading-[1.08] text-primary"
            style={{ "--stagger": 1 } as React.CSSProperties}
          >
            Every dollar,
            <br />
            forecast and
            <br />
            <span className="bg-gradient-to-r from-accent to-info bg-clip-text text-transparent">
              accounted for.
            </span>
          </h1>
          <p
            className="rise mt-4 leading-relaxed text-secondary"
            style={{ "--stagger": 2 } as React.CSSProperties}
          >
            Budget forecasting on a CSI MasterFormat WBS, the PCO → OCO / SCO change-order
            pipeline, PO commitments with budget control, and threshold-based approvals — all on a
            tamper-evident audit ledger.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-3">
            {STATS.map(([value, label], index) => (
              <div
                key={label}
                className="panel rise p-3"
                style={{ "--stagger": 3 + index } as React.CSSProperties}
              >
                <p className="figure font-mono text-sm text-accent">{value}</p>
                <p className="mt-0.5 text-[11px] text-muted">{label}</p>
              </div>
            ))}
          </div>
        </div>
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <ShieldCheck size={14} className="text-success" /> Role-based access · Append-only audit
          ledger
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="panel space-y-4 p-6">
            <div className="mb-2">
              <h2 className="font-display text-2xl font-bold text-primary">Sign in</h2>
              <p className="mt-1 text-sm text-secondary">Use your CFCS account credentials.</p>
            </div>
            <Field label="Email" required>
              <Input
                type="email"
                autoComplete="username"
                placeholder="pm@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Password" required>
              <Input
                type="password"
                autoComplete="current-password"
                placeholder="••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <ErrorNote error={error} />
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={busy || !email || !password}
            >
              {busy ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-xs text-muted">
              Demo accounts are created by scripts/seed.py
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
