"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { login } from "@/lib/api";
import { Button, ErrorNote, Field, Input } from "@/components/ui";

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
      <div className="hidden flex-1 flex-col justify-between border-r border-border-subtle bg-surface p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent font-display text-sm font-bold text-white">
            CF
          </div>
          <p className="font-display text-lg font-bold text-primary">CFCS</p>
        </div>
        <div className="max-w-md">
          <h1 className="font-display text-4xl font-bold leading-tight text-primary">
            Construction
            <br />
            Financial Control
          </h1>
          <p className="mt-4 text-secondary">
            Budget forecasting on a CSI MasterFormat WBS, the PCO → OCO / SCO change-order
            pipeline, PO commitments with budget control, and threshold-based approvals — all on a
            tamper-evident audit ledger.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4">
            {[
              ["3,401", "CSI cost codes"],
              ["EAC / ETC", "live forecasting"],
              ["SHA-256", "audit chain"],
            ].map(([value, label]) => (
              <div key={label} className="rounded-lg border border-border-default bg-elevated p-3">
                <p className="font-mono text-sm text-accent">{value}</p>
                <p className="mt-0.5 text-xs text-muted">{label}</p>
              </div>
            ))}
          </div>
        </div>
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <ShieldCheck size={14} /> Role-based access · Append-only audit ledger
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4">
          <div className="mb-6">
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
            Demo: pm@example.com / exec@example.com · ChangeMe123!
          </p>
        </form>
      </div>
    </div>
  );
}
