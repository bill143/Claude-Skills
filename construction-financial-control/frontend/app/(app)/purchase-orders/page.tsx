"use client";

import { AlertTriangle, Plus, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type BudgetLine,
  type ChangeOrder,
  type PurchaseOrder,
  type Vendor,
} from "@/lib/api";
import { dateShort, money } from "@/lib/format";
import { useApp } from "@/lib/store";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Modal,
  Select,
  SkeletonRows,
  StatusBadge,
  td,
  tdMono,
  th,
  thRight,
} from "@/components/ui";

function CreatePoModal({
  projectId,
  vendors,
  onClose,
  onDone,
}: {
  projectId: number;
  vendors: Vendor[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [mode, setMode] = useState<"sco" | "manual">("sco");
  const [scos, setScos] = useState<ChangeOrder[]>([]);
  const [budgetLines, setBudgetLines] = useState<BudgetLine[]>([]);
  const [scoId, setScoId] = useState<number | "">("");
  const [vendorId, setVendorId] = useState<number | "">(vendors[0]?.id ?? "");
  const [lineId, setLineId] = useState<number | "">("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api<ChangeOrder[]>(`/projects/${projectId}/change-orders`, {
      params: { co_type: "SCO", status: "APPROVED" },
    }).then((list) => {
      setScos(list);
      if (list.length === 0) setMode("manual");
      else setScoId(list[0].id);
    });
    void api<BudgetLine[]>(`/projects/${projectId}/budget-lines`).then(setBudgetLines);
  }, [projectId]);

  const submit = async () => {
    setError(null);
    try {
      const selectedSco = scos.find((sco) => sco.id === Number(scoId));
      const body =
        mode === "sco"
          ? {
              vendor_id: selectedSco?.vendor_id,
              source_change_order_id: Number(scoId),
              lines: [],
            }
          : {
              vendor_id: Number(vendorId),
              lines: [
                {
                  budget_line_id: Number(lineId),
                  description: description || "Purchase order line",
                  quantity: 1,
                  unit_cost: Number(amount),
                },
              ],
            };
      await api(`/projects/${projectId}/purchase-orders`, { method: "POST", body });
      onDone();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PO");
    }
  };

  return (
    <Modal title="New Purchase Order" onClose={onClose}>
      <div className="space-y-4">
        <div className="flex overflow-hidden rounded-md border border-border-default text-sm">
          {(
            [
              ["sco", `From approved SCO (${scos.length})`],
              ["manual", "Manual lines"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              disabled={value === "sco" && scos.length === 0}
              onClick={() => setMode(value)}
              className={`flex-1 px-3 py-2 transition-colors disabled:opacity-40 ${
                mode === value ? "bg-accent text-white" : "bg-surface text-secondary hover:text-primary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "sco" ? (
          <Field
            label="Approved subcontractor change order"
            hint="Copies the SCO's vendor and lines; once this PO is approved it supersedes the SCO commitment (no double counting)."
          >
            <Select value={scoId} onChange={(e) => setScoId(Number(e.target.value))}>
              {scos.map((sco) => (
                <option key={sco.id} value={sco.id}>
                  {sco.number} — {sco.title} ({money(sco.total_amount)})
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <>
            <Field label="Vendor" required>
              <Select value={vendorId} onChange={(e) => setVendorId(Number(e.target.value))}>
                {vendors.map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Budget line" required>
              <Select value={lineId} onChange={(e) => setLineId(Number(e.target.value))}>
                <option value="">Select…</option>
                {budgetLines.map((line) => (
                  <option key={line.id} value={line.id}>
                    {line.cost_code} — {line.description}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Description">
                <Input value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
              <Field label="Amount ($)" required>
                <Input type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} />
              </Field>
            </div>
          </>
        )}

        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={mode === "sco" ? !scoId : !vendorId || !lineId || !amount}
            onClick={submit}
          >
            Create PO
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default function PurchaseOrdersPage() {
  const { project } = useApp();
  const [orders, setOrders] = useState<PurchaseOrder[] | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [warnings, setWarnings] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!project) return;
    const [list, vendorList] = await Promise.all([
      api<PurchaseOrder[]>(`/projects/${project.id}/purchase-orders`),
      api<Vendor[]>("/vendors"),
    ]);
    setOrders(list);
    setVendors(vendorList);
  }, [project]);

  useEffect(() => {
    void load();
  }, [load]);

  const vendorName = (id: number) => vendors.find((v) => v.id === id)?.name ?? `Vendor #${id}`;

  const submit = async (po: PurchaseOrder) => {
    setError(null);
    setWarnings(null);
    try {
      const result = await api<{ status: string; budget_warnings: { cost_code: string; overrun: number }[] }>(
        `/purchase-orders/${po.id}/submit`,
        { method: "POST", idempotent: true },
      );
      if (result.budget_warnings.length) {
        setWarnings(
          result.budget_warnings
            .map((w) => `${w.cost_code} over budget by ${money(w.overrun)}`)
            .join(" · "),
        );
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    }
  };

  if (!project || orders === null) return <SkeletonRows rows={8} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-primary">Purchase Orders</h1>
          <p className="mt-0.5 text-sm text-secondary">
            Commitments against the budget. Submission runs the {project.budget_control} budget
            check, then the approval matrix.
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          <Plus size={15} /> New PO
        </Button>
      </div>

      {warnings ? (
        <p className="flex items-center gap-2 rounded-md border border-amber/30 bg-amber/10 px-3 py-2 text-xs text-amber">
          <AlertTriangle size={14} /> Budget warning: {warnings}
        </p>
      ) : null}
      <ErrorNote error={error} />

      {orders.length === 0 ? (
        <EmptyState
          title="No purchase orders"
          body="Buy out approved SCOs into POs, or create manual POs against budget lines."
          action={
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> New PO
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border-default bg-surface">
          <table className="w-full">
            <thead className="bg-elevated">
              <tr>
                <th className={th}>Number</th>
                <th className={th}>Vendor</th>
                <th className={th}>Source</th>
                <th className={th}>Status</th>
                <th className={thRight}>Amount</th>
                <th className={th}>Created</th>
                <th className={`${th} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {orders.map((po) => (
                <tr key={po.id} className="transition-colors hover:bg-hovered">
                  <td className={`${td} font-mono text-accent`}>{po.number}</td>
                  <td className={td}>{vendorName(po.vendor_id)}</td>
                  <td className={`${td} text-muted`}>
                    {po.source_change_order_id ? `SCO #${po.source_change_order_id}` : "manual"}
                  </td>
                  <td className={td}>
                    <StatusBadge status={po.status} />
                  </td>
                  <td className={tdMono}>{money(po.total_amount)}</td>
                  <td className={`${td} text-muted`}>{dateShort(po.created_at)}</td>
                  <td className={`${td} text-right`}>
                    {po.status === "DRAFT" ? (
                      <Button size="sm" variant="primary" onClick={() => void submit(po)}>
                        <Send size={13} /> Submit
                      </Button>
                    ) : po.status === "APPROVED" ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          void api(`/purchase-orders/${po.id}/transition`, {
                            method: "POST",
                            idempotent: true,
                            body: { action: "close" },
                          }).then(load)
                        }
                      >
                        Close
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate ? (
        <CreatePoModal
          projectId={project.id}
          vendors={vendors}
          onClose={() => setShowCreate(false)}
          onDone={load}
        />
      ) : null}
    </div>
  );
}
