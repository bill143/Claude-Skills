"use client";

import { AlertTriangle, ArrowRight, CheckSquare, Info } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Kpis, type WbsTree } from "@/lib/api";
import { money, pct, vacTone } from "@/lib/format";
import { useApp } from "@/lib/store";
import { Card, KpiCard, PageHeader, Segmented, SkeletonRows } from "@/components/ui";

const METHOD_HELP: Record<string, string> = {
  REMAINING_BUDGET:
    "EAC per line = the greater of current budget, committed cost, or actuals. Actuals draw the budget down — they never stack on top of it. Lines with a PM-entered ETC use that instead.",
  CPI: "Earned-value method: EAC = actual + (budget − earned value) ÷ CPI, using the percent complete you set. Lines without actuals fall back to remaining-budget.",
};

/* Shared-scale horizontal bars with a budget reference line. */
function ForecastBullet({ kpis }: { kpis: Kpis }) {
  const scale = Math.max(kpis.current_budget, kpis.eac, kpis.committed, kpis.actual_to_date, 1);
  const budgetAt = (kpis.current_budget / scale) * 100;
  const rows: { label: string; value: number; tone: string }[] = [
    { label: "Current budget", value: kpis.current_budget, tone: "bg-accent" },
    { label: "Committed", value: kpis.committed, tone: "bg-info" },
    { label: "Actual to date", value: kpis.actual_to_date, tone: "bg-amber" },
    {
      label: "Forecast (EAC)",
      value: kpis.eac,
      tone: kpis.eac > kpis.current_budget + 0.005 ? "bg-danger" : "bg-success",
    },
  ];
  return (
    <div className="space-y-4 py-1">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-3">
          <span className="w-[8.5rem] shrink-0 text-right text-[11px] uppercase tracking-wider text-muted">
            {row.label}
          </span>
          <div className="relative h-3 flex-1">
            <div className="absolute inset-0 rounded-sm bg-inset" />
            <div
              className={`bar-grow absolute inset-y-0 left-0 rounded-sm ${row.tone}`}
              style={{ width: `${Math.max(0.5, (row.value / scale) * 100)}%`, opacity: 0.85 }}
            />
            <div
              className="absolute -inset-y-1 z-10 w-px border-l border-dashed border-border-strong"
              style={{ left: `${budgetAt}%` }}
              aria-hidden
            />
          </div>
          <span className="figure w-28 shrink-0 text-right font-mono text-xs text-primary">
            {money(row.value)}
          </span>
        </div>
      ))}
      <p className="pl-[9.25rem] text-[10px] text-muted">
        Dashed line = current budget. A forecast bar past it is a projected overrun.
      </p>
    </div>
  );
}

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

  const overBudget = kpis ? kpis.eac > kpis.current_budget + 0.005 : false;

  return (
    <div className="space-y-5">
      <PageHeader
        kicker={`${project.code}${project.owner_name ? ` · ${project.owner_name}` : ""}`}
        title={project.name}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <Segmented
              value={method}
              onChange={setMethod}
              options={[
                { value: "REMAINING_BUDGET", label: "Remaining Budget" },
                { value: "CPI", label: "Earned Value (CPI)" },
              ]}
            />
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
        }
      />

      {loading || !kpis ? (
        <SkeletonRows rows={6} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <KpiCard
              stagger={0}
              label="Contract Value"
              value={money(kpis.contract_value)}
              sub={
                kpis.approved_changes > 0
                  ? `incl. ${money(kpis.approved_changes)} approved OCOs`
                  : "no approved owner changes yet"
              }
            />
            <KpiCard
              stagger={1}
              label="Current Budget"
              value={money(kpis.current_budget)}
              progress={kpis.current_budget ? kpis.committed / kpis.current_budget : 0}
              progressTone="info"
              sub={`${pct(kpis.current_budget ? kpis.committed / kpis.current_budget : 0)} committed`}
            />
            <KpiCard
              stagger={2}
              label="Committed"
              value={money(kpis.committed)}
              sub="approved POs + approved SCOs"
            />
            <KpiCard
              stagger={3}
              label="Actual to Date"
              value={money(kpis.actual_to_date)}
              progress={kpis.current_budget ? kpis.actual_to_date / kpis.current_budget : 0}
              progressTone={
                kpis.actual_to_date > kpis.current_budget ? "danger" : "amber"
              }
              sub={`burn ${money(kpis.burn_rate_30d)} / 30d`}
            />
          </div>

          {/* Forecast hero */}
          <div
            className="panel rise overflow-hidden"
            style={{ "--stagger": 4 } as React.CSSProperties}
          >
            <div className="grid lg:grid-cols-[19rem_1fr]">
              <div className="space-y-4 border-b border-border-subtle p-5 lg:border-b-0 lg:border-r">
                <div>
                  <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted">
                    Forecast at Completion
                  </p>
                  <p
                    className={`figure mt-1.5 font-mono text-4xl leading-none ${
                      overBudget ? "text-danger" : "text-primary"
                    }`}
                  >
                    {money(kpis.eac)}
                  </p>
                  <p className="mt-2 text-xs text-secondary">
                    {pct(kpis.percent_complete)} complete on a cost basis
                  </p>
                </div>
                <dl className="space-y-2 border-t border-border-subtle pt-4">
                  {(
                    [
                      ["Cost to Complete (ETC)", money(kpis.etc), "text-primary"],
                      [
                        "Variance at Completion",
                        money(kpis.vac),
                        `text-${vacTone(kpis.vac)}`,
                      ],
                      [
                        "Projected Margin",
                        money(kpis.projected_margin),
                        kpis.projected_margin >= 0 ? "text-success" : "text-danger",
                      ],
                    ] as const
                  ).map(([label, value, toneCls]) => (
                    <div key={label} className="flex items-baseline justify-between gap-3">
                      <dt className="text-xs text-secondary">{label}</dt>
                      <dd className={`figure font-mono text-sm ${toneCls}`}>{value}</dd>
                    </div>
                  ))}
                </dl>
                <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-muted">
                  <Info size={12} className="mt-0.5 shrink-0 text-info" />
                  {METHOD_HELP[method]}
                </p>
              </div>
              <div className="flex items-center p-5">
                <div className="w-full">
                  <ForecastBullet kpis={kpis} />
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card
              title="Budget by CSI Division"
              className="rise lg:col-span-2"
              action={
                <Link
                  href="/budget"
                  className="flex items-center gap-1 text-xs text-accent hover:underline"
                >
                  Open WBS <ArrowRight size={12} />
                </Link>
              }
            >
              <div className="space-y-3.5">
                {wbs?.divisions.map((division) => {
                  const budget = division.rollup.current_budget;
                  const largest = Math.max(
                    ...wbs.divisions.map((d) => d.rollup.current_budget),
                    1,
                  );
                  const width = Math.max(3, (budget / largest) * 100);
                  const spentFrac = budget > 0 ? division.rollup.actual / budget : 0;
                  const committedFrac = budget > 0 ? division.rollup.committed / budget : 0;
                  return (
                    <div key={division.division}>
                      <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
                        <span className="flex min-w-0 items-baseline gap-2">
                          <span className="shrink-0 rounded border border-border-default bg-elevated px-1 font-mono text-[10px] text-amber">
                            {division.division}
                          </span>
                          <span className="truncate text-secondary">{division.title}</span>
                        </span>
                        <span className="flex shrink-0 items-baseline gap-2">
                          <span className="text-[10px] text-muted">
                            {pct(Math.min(1, spentFrac))} spent
                          </span>
                          <span className="figure font-mono tabular-nums text-primary">
                            {money(budget)}
                          </span>
                        </span>
                      </div>
                      <div
                        className="relative h-2.5 overflow-hidden rounded-sm bg-inset"
                        style={{ width: `${width}%`, minWidth: "7rem" }}
                        title={`${division.title}: ${money(division.rollup.actual)} actual · ${money(division.rollup.committed)} committed of ${money(budget)}`}
                      >
                        <div
                          className="absolute inset-y-0 left-0 rounded-sm bg-info/30"
                          style={{ width: `${Math.min(100, committedFrac * 100)}%` }}
                        />
                        <div
                          className={`bar-grow absolute inset-y-0 left-0 rounded-sm ${
                            spentFrac > 1 ? "bg-danger" : "bg-accent"
                          }`}
                          style={{ width: `${Math.min(100, spentFrac * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
                <p className="pt-1 text-[10px] text-muted">
                  Bar length = share of budget · solid fill = actual spend · light fill = committed
                </p>
              </div>
            </Card>

            <div className="space-y-4">
              <Card title="Needs attention" className="rise">
                <div className="space-y-2">
                  <Link
                    href="/change-orders"
                    className="group flex items-center justify-between rounded-md border border-border-subtle bg-elevated px-3 py-2.5 transition-colors hover:border-amber/40 hover:bg-hovered"
                  >
                    <span className="flex items-center gap-2 text-sm text-secondary">
                      <AlertTriangle size={14} className="text-amber" /> Open PCOs
                    </span>
                    <span className="figure font-mono text-lg tabular-nums text-amber">
                      {kpis.open_pcos}
                    </span>
                  </Link>
                  <Link
                    href="/approvals"
                    className="group flex items-center justify-between rounded-md border border-border-subtle bg-elevated px-3 py-2.5 transition-colors hover:border-amber/40 hover:bg-hovered"
                  >
                    <span className="flex items-center gap-2 text-sm text-secondary">
                      <CheckSquare size={14} className="text-amber" /> Pending approvals
                    </span>
                    <span className="figure font-mono text-lg tabular-nums text-amber">
                      {kpis.pending_approvals}
                    </span>
                  </Link>
                </div>
              </Card>
              <Card title="How numbers move" className="rise">
                <p className="text-xs leading-relaxed text-secondary">
                  Budget changes only through <b className="text-primary">approved OCOs</b>.
                  Committed grows from <b className="text-primary">approved POs / SCOs</b>. Actuals
                  are posted cost entries. Click any line in the WBS to see the documents behind
                  it.
                </p>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
