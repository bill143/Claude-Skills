"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Kpis, type WbsTree } from "@/lib/api";
import { money, pct, vacTone } from "@/lib/format";
import { useApp } from "@/lib/store";
import { KpiCard, SkeletonRows } from "@/components/ui";

const METHOD_HELP: Record<string, string> = {
  REMAINING_BUDGET:
    "EAC per line = the greater of current budget, committed cost, or actuals. Actuals draw the budget down — they never stack on top of it. Lines with a PM-entered ETC use that instead.",
  CPI: "Earned-value method: EAC = actual + (budget − earned value) ÷ CPI, using the percent complete you set below. Lines without actuals fall back to remaining-budget.",
};

export default function DashboardPage() {
  const { project } = useApp();
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [wbs, setWbs] = useState<WbsTree | null>(null);
  const [method, setMethod] = useState<"REMAINING_BUDGET" | "CPI">("REMAINING_BUDGET");
  const [pctComplete, setPctComplete] = useState(0.5);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!project) return;
    setLoading(true);
    const params = {
      method,
      percent_complete: method === "CPI" ? pctComplete : undefined,
    };
    const [k, tree] = await Promise.all([
      api<Kpis>(`/projects/${project.id}/kpis`, { params }),
      api<WbsTree>(`/projects/${project.id}/wbs`, { params }),
    ]);
    setKpis(k);
    setWbs(tree);
    setLoading(false);
  }, [project, method, pctComplete]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!project) return <SkeletonRows rows={8} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-primary">{project.name}</h1>
          <p className="mt-0.5 text-sm text-secondary">
            {project.owner_name ?? "—"} · Budget control:{" "}
            <span className="font-medium text-primary">{project.budget_control}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex overflow-hidden rounded-md border border-border-default">
            {(["REMAINING_BUDGET", "CPI"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMethod(m)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  method === m
                    ? "bg-accent text-white"
                    : "bg-surface text-secondary hover:text-primary"
                }`}
              >
                {m === "REMAINING_BUDGET" ? "Remaining Budget" : "Earned Value (CPI)"}
              </button>
            ))}
          </div>
          {method === "CPI" ? (
            <label className="flex items-center gap-2 text-xs text-secondary">
              % complete
              <input
                type="range"
                min={5}
                max={100}
                step={5}
                value={pctComplete * 100}
                onChange={(e) => setPctComplete(Number(e.target.value) / 100)}
                className="accent-[var(--accent-primary)]"
              />
              <span className="w-9 font-mono tabular-nums text-primary">
                {Math.round(pctComplete * 100)}%
              </span>
            </label>
          ) : null}
        </div>
      </div>

      <p className="flex items-start gap-2 rounded-md border border-border-subtle bg-surface px-3 py-2 text-xs text-secondary">
        <Info size={14} className="mt-0.5 shrink-0 text-info" />
        {METHOD_HELP[method]}
      </p>

      {loading || !kpis ? (
        <SkeletonRows rows={6} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <KpiCard
              label="Contract Value"
              value={money(kpis.contract_value)}
              sub={
                kpis.approved_changes > 0
                  ? `incl. ${money(kpis.approved_changes)} approved OCOs`
                  : "no approved owner changes yet"
              }
            />
            <KpiCard
              label="Current Budget"
              value={money(kpis.current_budget)}
              sub={`${money(kpis.original_budget)} original ${
                kpis.approved_changes ? `+ ${money(kpis.approved_changes)} changes` : ""
              }`}
            />
            <KpiCard
              label="Committed"
              value={money(kpis.committed)}
              sub="approved POs + approved SCOs"
            />
            <KpiCard
              label="Actual to Date"
              value={money(kpis.actual_to_date)}
              sub={`burn ${money(kpis.burn_rate_30d)} / 30d`}
            />
            <KpiCard label="Forecast at Completion (EAC)" value={money(kpis.eac)} />
            <KpiCard label="Cost to Complete (ETC)" value={money(kpis.etc)} />
            <KpiCard
              label="Variance at Completion (VAC)"
              value={money(kpis.vac)}
              tone={vacTone(kpis.vac)}
              sub={kpis.vac >= 0 ? "under / on budget" : "projected overrun"}
            />
            <KpiCard
              label="Projected Margin"
              value={money(kpis.projected_margin)}
              tone={kpis.projected_margin >= 0 ? "success" : "danger"}
              sub={`${pct(kpis.percent_complete)} complete (cost basis)`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-border-default bg-surface lg:col-span-2">
              <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
                <h2 className="text-sm font-medium text-primary">Budget by CSI Division</h2>
                <Link href="/budget" className="text-xs text-accent hover:underline">
                  Open WBS →
                </Link>
              </div>
              <div className="space-y-3 p-4">
                {wbs?.divisions.map((division) => {
                  const width =
                    wbs.totals.current_budget > 0
                      ? Math.max(
                          2,
                          (division.rollup.current_budget / wbs.totals.current_budget) * 100,
                        )
                      : 0;
                  const spent =
                    division.rollup.current_budget > 0
                      ? Math.min(
                          100,
                          (division.rollup.actual / division.rollup.current_budget) * 100,
                        )
                      : 0;
                  return (
                    <div key={division.division}>
                      <div className="mb-1 flex items-baseline justify-between text-xs">
                        <span className="text-secondary">
                          <span className="font-mono text-muted">{division.division}</span>{" "}
                          {division.title}
                        </span>
                        <span className="font-mono tabular-nums text-primary">
                          {money(division.rollup.current_budget)}
                        </span>
                      </div>
                      <div
                        className="h-2 overflow-hidden rounded-full bg-elevated"
                        style={{ width: `${width}%`, minWidth: "6rem" }}
                        title={`${division.title}: ${spent.toFixed(0)}% spent`}
                      >
                        <div
                          className="h-full rounded-full bg-accent transition-all"
                          style={{ width: `${spent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-border-default bg-surface p-4">
                <p className="text-xs uppercase tracking-widest text-muted">Needs attention</p>
                <div className="mt-3 space-y-2">
                  <Link
                    href="/change-orders"
                    className="flex items-center justify-between rounded-md bg-elevated px-3 py-2.5 transition-colors hover:bg-hovered"
                  >
                    <span className="text-sm text-secondary">Open PCOs</span>
                    <span className="font-mono text-lg tabular-nums text-amber">
                      {kpis.open_pcos}
                    </span>
                  </Link>
                  <Link
                    href="/approvals"
                    className="flex items-center justify-between rounded-md bg-elevated px-3 py-2.5 transition-colors hover:bg-hovered"
                  >
                    <span className="text-sm text-secondary">Pending approvals</span>
                    <span className="font-mono text-lg tabular-nums text-amber">
                      {kpis.pending_approvals}
                    </span>
                  </Link>
                </div>
              </div>
              <div className="rounded-lg border border-border-default bg-surface p-4 text-xs leading-relaxed text-secondary">
                <p className="mb-1 text-[10px] uppercase tracking-widest text-muted">
                  How numbers move
                </p>
                Budget changes only through <b className="text-primary">approved OCOs</b>. Committed
                grows from <b className="text-primary">approved POs / SCOs</b>. Actuals are posted
                cost entries. Click any line in the WBS to see the documents behind it.
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
