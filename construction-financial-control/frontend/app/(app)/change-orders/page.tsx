"use client";

import { ArrowRight, ChevronRight, GitPullRequestArrow, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type ApprovalRequest,
  type BudgetLine,
  type ChangeOrder,
  type Vendor,
} from "@/lib/api";
import { dateShort, money } from "@/lib/format";
import { useApp } from "@/lib/store";
import {
  Button,
  ChainStepper,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  SkeletonRows,
  StatusBadge,
  TypeChip,
  td,
  tdMono,
  th,
  thRight,
} from "@/components/ui";

const ACTION_LABELS: Record<string, string> = {
  send_to_pricing: "Send to Pricing",
  submit: "Mark Priced / Submitted",
  submit_for_approval: "Submit for Approval",
  revise: "Revise (back to draft)",
  void: "Void",
  convert: "Convert to OCO / SCO",
};

/* PCO pipeline + contract totals derived from the list. */
function PipelineStrip({ orders }: { orders: ChangeOrder[] }) {
  const stages = useMemo(() => {
    const pcos = orders.filter((co) => co.co_type === "PCO");
    const count = (status: string) => pcos.filter((co) => co.status === status).length;
    const approvedTotal = (type: string) =>
      orders
        .filter((co) => co.co_type === type && co.status === "APPROVED")
        .reduce((sum, co) => sum + co.total_amount, 0);
    return {
      pipeline: [
        { label: "Draft", value: count("DRAFT") },
        { label: "Pricing", value: count("PRICING") },
        { label: "Submitted", value: count("SUBMITTED") },
        { label: "Converted", value: count("CONVERTED") },
      ],
      oco: approvedTotal("OCO"),
      sco: approvedTotal("SCO"),
    };
  }, [orders]);

  return (
    <div className="panel rise flex flex-wrap items-stretch gap-x-1 gap-y-3 px-4 py-3">
      {stages.pipeline.map((stage, index) => (
        <div key={stage.label} className="flex items-center">
          <div className="px-2">
            <p className="text-[9px] uppercase tracking-[0.18em] text-muted">{stage.label}</p>
            <p
              className={`figure mt-0.5 font-mono text-xl leading-none ${
                stage.value > 0 ? "text-primary" : "text-muted"
              }`}
            >
              {stage.value}
            </p>
          </div>
          {index < stages.pipeline.length - 1 ? (
            <ChevronRight size={14} className="mx-1 text-border-strong" />
          ) : null}
        </div>
      ))}
      <div className="mx-3 hidden w-px self-stretch bg-border-default sm:block" />
      <div className="px-2">
        <p className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.18em] text-muted">
          <TypeChip value="OCO" /> approved
        </p>
        <p className="figure mt-0.5 font-mono text-xl leading-none text-gold">
          {money(stages.oco)}
        </p>
      </div>
      <div className="px-2">
        <p className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.18em] text-muted">
          <TypeChip value="SCO" /> approved
        </p>
        <p className="figure mt-0.5 font-mono text-xl leading-none text-info">
          {money(stages.sco)}
        </p>
      </div>
    </div>
  );
}

type DraftLine = { budget_line_id: number | ""; description: string; quantity: number; unit_cost: number };

function CreatePcoModal({ projectId, onClose, onDone }: { projectId: number; onClose: () => void; onDone: () => void }) {
  const [budgetLines, setBudgetLines] = useState<BudgetLine[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [days, setDays] = useState(0);
  const [lines, setLines] = useState<DraftLine[]>([
    { budget_line_id: "", description: "", quantity: 1, unit_cost: 0 },
  ]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api<BudgetLine[]>(`/projects/${projectId}/budget-lines`).then(setBudgetLines);
  }, [projectId]);

  const total = lines.reduce((sum, line) => sum + line.quantity * line.unit_cost, 0);

  const submit = async () => {
    setError(null);
    try {
      await api(`/projects/${projectId}/change-orders`, {
        method: "POST",
        body: {
          co_type: "PCO",
          title,
          description: description || null,
          schedule_impact_days: days,
          lines: lines
            .filter((line) => line.budget_line_id !== "" && line.unit_cost > 0)
            .map((line) => ({ ...line, budget_line_id: Number(line.budget_line_id) })),
        },
      });
      onDone();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PCO");
    }
  };

  return (
    <Modal title="New Potential Change Order" onClose={onClose} wide>
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            <Field label="Title" required>
              <Input value={title} placeholder="Owner-requested lobby skylight" onChange={(e) => setTitle(e.target.value)} />
            </Field>
          </div>
          <Field label="Schedule impact (days)">
            <Input type="number" value={days} onChange={(e) => setDays(Number(e.target.value))} />
          </Field>
        </div>
        <Field label="Scope description">
          <Input value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            Cost lines
          </p>
          <div className="space-y-2">
            {lines.map((line, index) => (
              <div key={index} className="flex items-center gap-2">
                <Select
                  aria-label="Budget line"
                  className="flex-1"
                  value={line.budget_line_id}
                  onChange={(e) => {
                    const next = [...lines];
                    next[index] = { ...line, budget_line_id: Number(e.target.value) };
                    setLines(next);
                  }}
                >
                  <option value="">Select budget line…</option>
                  {budgetLines.map((bl) => (
                    <option key={bl.id} value={bl.id}>
                      {bl.cost_code} — {bl.description}
                    </option>
                  ))}
                </Select>
                <Input
                  className="!w-48"
                  placeholder="Line description"
                  value={line.description}
                  onChange={(e) => {
                    const next = [...lines];
                    next[index] = { ...line, description: e.target.value };
                    setLines(next);
                  }}
                />
                <Input
                  className="!w-20 text-right font-mono"
                  type="number"
                  min={0}
                  aria-label="Quantity"
                  value={line.quantity}
                  onChange={(e) => {
                    const next = [...lines];
                    next[index] = { ...line, quantity: Number(e.target.value) };
                    setLines(next);
                  }}
                />
                <Input
                  className="!w-28 text-right font-mono"
                  type="number"
                  min={0}
                  aria-label="Unit cost"
                  placeholder="Unit $"
                  value={line.unit_cost || ""}
                  onChange={(e) => {
                    const next = [...lines];
                    next[index] = { ...line, unit_cost: Number(e.target.value) };
                    setLines(next);
                  }}
                />
                <button
                  aria-label="Remove line"
                  className="p-1.5 text-muted hover:text-danger"
                  onClick={() => setLines(lines.filter((_, i) => i !== index))}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setLines([...lines, { budget_line_id: "", description: "", quantity: 1, unit_cost: 0 }])}
            >
              <Plus size={14} /> Add line
            </Button>
            <p className="figure font-mono text-sm tabular-nums text-primary">Total {money(total)}</p>
          </div>
        </div>

        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!title || total <= 0} onClick={submit}>
            Create PCO
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function ConvertModal({ co, vendors, onClose, onDone }: { co: ChangeOrder; vendors: Vendor[]; onClose: () => void; onDone: () => void }) {
  const [targets, setTargets] = useState<string[]>(["OCO", "SCO"]);
  const [vendorId, setVendorId] = useState<number | "">(vendors[0]?.id ?? "");
  const [markup, setMarkup] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    try {
      await api(`/change-orders/${co.id}/convert`, {
        method: "POST",
        idempotent: true,
        body: {
          targets,
          vendor_id: targets.includes("SCO") ? Number(vendorId) : null,
          oco_markup_pct: markup / 100,
        },
      });
      onDone();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Convert failed");
    }
  };

  return (
    <Modal title={`Convert ${co.number}`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-secondary">
          Creates draft contract documents from this priced PCO. The SCO carries cost (
          <span className="font-mono">{money(co.total_amount)}</span>); the OCO adds your markup for
          the owner side.
        </p>
        <div className="flex gap-3">
          {["OCO", "SCO"].map((target) => (
            <label
              key={target}
              className={`flex flex-1 cursor-pointer items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors ${
                targets.includes(target)
                  ? "border-accent bg-accent/10 text-primary"
                  : "border-border-default text-secondary hover:border-border-strong"
              }`}
            >
              <input
                type="checkbox"
                className="accent-[var(--accent-primary)]"
                checked={targets.includes(target)}
                onChange={(e) =>
                  setTargets(e.target.checked ? [...targets, target] : targets.filter((t) => t !== target))
                }
              />
              {target === "OCO" ? "Owner Change Order" : "Subcontractor CO"}
            </label>
          ))}
        </div>
        {targets.includes("SCO") ? (
          <Field label="Subcontractor" required>
            <Select value={vendorId} onChange={(e) => setVendorId(Number(e.target.value))}>
              {vendors.map((vendor) => (
                <option key={vendor.id} value={vendor.id}>
                  {vendor.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        {targets.includes("OCO") ? (
          <Field label={`OCO markup: ${markup}% → owner price ${money(co.total_amount * (1 + markup / 100))}`}>
            <input
              type="range"
              min={0}
              max={30}
              value={markup}
              onChange={(e) => setMarkup(Number(e.target.value))}
              className="w-full accent-[var(--accent-primary)]"
            />
          </Field>
        ) : null}
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={targets.length === 0} onClick={submit}>
            Convert
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default function ChangeOrdersPage() {
  const { project } = useApp();
  const [orders, setOrders] = useState<ChangeOrder[] | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [selected, setSelected] = useState<ChangeOrder | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showConvert, setShowConvert] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!project) return;
    const [list, vendorList] = await Promise.all([
      api<ChangeOrder[]>(`/projects/${project.id}/change-orders`),
      api<Vendor[]>("/vendors"),
    ]);
    setOrders(list);
    setVendors(vendorList);
    setSelected((current) => (current ? list.find((co) => co.id === current.id) ?? null : null));
  }, [project]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setApprovals([]);
      return;
    }
    void api<ApprovalRequest[]>(`/change-orders/${selected.id}/approvals`).then(setApprovals);
  }, [selected]);

  const act = async (co: ChangeOrder, action: string) => {
    setError(null);
    if (action === "convert") {
      setSelected(co);
      setShowConvert(true);
      return;
    }
    try {
      await api(`/change-orders/${co.id}/transition`, {
        method: "POST",
        idempotent: true,
        body: { action },
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  };

  if (!project || orders === null) return <SkeletonRows rows={8} />;

  return (
    <div className="space-y-4">
      <PageHeader
        kicker="Cost Control"
        title="Change Orders"
        description="PCO → priced → converted to OCO (owner) / SCO (sub) → approved through the matrix."
        actions={
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            <Plus size={15} /> New PCO
          </Button>
        }
      />

      <ErrorNote error={error} />

      {orders.length === 0 ? (
        <EmptyState
          icon={<GitPullRequestArrow size={20} />}
          title="No change orders"
          body="Start the pipeline with a Potential Change Order — price it, then convert it into owner and subcontractor documents."
          action={
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> New PCO
            </Button>
          }
        />
      ) : (
        <>
          <PipelineStrip orders={orders} />
          <div className="grid gap-4 xl:grid-cols-3">
            <div className="panel overflow-x-auto xl:col-span-2">
              <table className="w-full">
                <thead className="bg-elevated">
                  <tr>
                    <th className={th}>Number</th>
                    <th className={th}>Type</th>
                    <th className={th}>Title</th>
                    <th className={th}>Status</th>
                    <th className={thRight}>Amount</th>
                    <th className={th}>Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {orders.map((co) => (
                    <tr
                      key={co.id}
                      onClick={() => setSelected(co)}
                      className={`cursor-pointer transition-colors hover:bg-hovered ${
                        selected?.id === co.id
                          ? "bg-accent/5 shadow-[inset_2px_0_0_var(--accent-primary)]"
                          : ""
                      }`}
                    >
                      <td className={`${td} font-mono text-accent`}>{co.number}</td>
                      <td className={td}>
                        <TypeChip value={co.co_type} />
                      </td>
                      <td className={`${td} max-w-[14rem] truncate`}>{co.title}</td>
                      <td className={td}>
                        <StatusBadge status={co.status} />
                      </td>
                      <td className={tdMono}>{money(co.total_amount)}</td>
                      <td className={`${td} text-muted`}>{dateShort(co.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel">
              {!selected ? (
                <p className="p-6 text-center text-sm text-muted">
                  Select a change order to see its lines, approval chain, and actions.
                </p>
              ) : (
                <div className="space-y-4 p-4">
                  <div>
                    <p className="flex items-center gap-2">
                      <span className="font-mono text-sm text-accent">{selected.number}</span>
                      <TypeChip value={selected.co_type} />
                    </p>
                    <h2 className="mt-0.5 font-display text-lg font-semibold text-primary">
                      {selected.title}
                    </h2>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <StatusBadge status={selected.status} />
                      <span className="figure font-mono text-sm tabular-nums text-primary">
                        {money(selected.total_amount)}
                      </span>
                      {selected.schedule_impact_days ? (
                        <span className="text-xs text-amber">+{selected.schedule_impact_days} days</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="space-y-1">
                    {selected.lines.map((line) => (
                      <div
                        key={line.id}
                        className="flex justify-between rounded border border-border-subtle bg-elevated px-2.5 py-1.5 text-xs"
                      >
                        <span className="truncate text-secondary">{line.description}</span>
                        <span className="figure font-mono tabular-nums text-primary">
                          {money(line.amount)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {approvals.length ? (
                    <div>
                      <p className="mb-1.5 text-[9px] font-medium uppercase tracking-[0.18em] text-muted">
                        Approval chain
                      </p>
                      <ChainStepper steps={approvals} />
                    </div>
                  ) : null}

                  <div className="space-y-1.5 border-t border-border-subtle pt-3">
                    {selected.allowed_actions.length === 0 ? (
                      <p className="text-xs text-muted">
                        No actions available — this document is {selected.status.toLowerCase()}.
                      </p>
                    ) : (
                      selected.allowed_actions.map((action) => (
                        <Button
                          key={action}
                          className="w-full justify-between"
                          variant={action === "void" ? "danger" : action === "convert" ? "primary" : "secondary"}
                          onClick={() => void act(selected, action)}
                        >
                          {ACTION_LABELS[action] ?? action}
                          <ArrowRight size={14} />
                        </Button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {showCreate ? (
        <CreatePcoModal projectId={project.id} onClose={() => setShowCreate(false)} onDone={load} />
      ) : null}
      {showConvert && selected ? (
        <ConvertModal co={selected} vendors={vendors} onClose={() => setShowConvert(false)} onDone={load} />
      ) : null}
    </div>
  );
}
