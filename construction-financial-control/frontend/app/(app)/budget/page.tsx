"use client";

import { ChevronDown, ChevronRight, FileUp, Pencil, Plus, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type CostCode,
  type ImportPreview,
  type LineMetrics,
  type WbsDivision,
  type WbsTree,
} from "@/lib/api";
import { money, moneyExact, vacTone } from "@/lib/format";
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

const COLUMNS = ["Budget", "Changes", "Current", "Committed", "Actual", "ETC", "EAC", "VAC"];

function RollupCells({ rollup }: { rollup: Record<string, number> }) {
  const keys = [
    "original_budget",
    "approved_changes",
    "current_budget",
    "committed",
    "actual",
    "etc",
    "eac",
    "vac",
  ];
  return (
    <>
      {keys.map((key) => (
        <td
          key={key}
          className={`${tdMono} ${key === "vac" ? `text-${vacTone(rollup[key])}` : ""}`}
        >
          {money(rollup[key])}
        </td>
      ))}
    </>
  );
}

/* ---------------- Inline manual-ETC editor ---------------- */

function EtcCell({ line, onSaved }: { line: LineMetrics; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(line.etc));
  const [busy, setBusy] = useState(false);

  const save = async (clear: boolean) => {
    setBusy(true);
    try {
      await api(`/budget-lines/${line.id}`, {
        method: "PATCH",
        body: clear ? { clear_manual_etc: true } : { manual_etc: Number(value) || 0 },
      });
      setEditing(false);
      onSaved();
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <td className={`${tdMono} !py-1`}>
        <span className="inline-flex items-center gap-1">
          <input
            autoFocus
            type="number"
            min={0}
            value={value}
            disabled={busy}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void save(false);
              if (e.key === "Escape") setEditing(false);
            }}
            className="h-7 w-28 rounded border border-accent bg-elevated px-2 text-right font-mono text-sm text-primary focus:outline-none"
            aria-label="Manual cost to complete"
          />
          <button
            title="Save ETC"
            className="text-success hover:opacity-80"
            onClick={() => void save(false)}
          >
            ✓
          </button>
          {line.manual_etc !== null ? (
            <button
              title="Clear manual ETC (revert to computed)"
              className="text-danger hover:opacity-80"
              onClick={() => void save(true)}
            >
              <X size={13} />
            </button>
          ) : null}
        </span>
      </td>
    );
  }
  return (
    <td className={`${tdMono} group cursor-pointer`} onClick={() => setEditing(true)}>
      <span className="inline-flex items-center gap-1.5">
        {line.manual_etc !== null ? (
          <span
            className="rounded bg-amber/15 px-1 text-[10px] font-medium uppercase text-amber"
            title="PM-entered cost to complete"
          >
            manual
          </span>
        ) : null}
        {money(line.etc)}
        <Pencil size={11} className="text-muted opacity-0 transition-opacity group-hover:opacity-100" />
      </span>
    </td>
  );
}

/* ---------------- Drill-down drawer ---------------- */

type LineDetail = {
  metrics: LineMetrics;
  change_orders: {
    id: number;
    number: string;
    co_type: string;
    status: string;
    title: string;
    line_amount: number;
  }[];
  purchase_orders: { id: number; number: string; status: string; line_amount: number }[];
  cost_entries: { id: number; entry_date: string; amount: number; description: string | null }[];
};

function Drawer({ lineId, onClose, onChanged }: { lineId: number; onClose: () => void; onChanged: () => void }) {
  const [detail, setDetail] = useState<LineDetail | null>(null);
  const [cost, setCost] = useState({ amount: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setDetail(await api<LineDetail>(`/budget-lines/${lineId}/detail`));
  }, [lineId]);

  useEffect(() => {
    void load();
  }, [load]);

  const postCost = async () => {
    setError(null);
    try {
      await api(`/budget-lines/${lineId}/costs`, {
        method: "POST",
        body: {
          entry_date: new Date().toISOString().slice(0, 10),
          amount: Number(cost.amount),
          description: cost.description || "Cost entry",
        },
      });
      setCost({ amount: "", description: "" });
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  const m = detail?.metrics;
  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-[26rem] animate-slide-in-right overflow-y-auto border-l border-border-default bg-surface shadow-2xl">
      <div className="sticky top-0 flex items-center justify-between border-b border-border-subtle bg-surface px-5 py-4">
        <div>
          <p className="font-mono text-sm text-accent">{m?.cost_code ?? "…"}</p>
          <h2 className="text-sm font-medium text-primary">{m?.description ?? "Loading"}</h2>
        </div>
        <button
          onClick={onClose}
          aria-label="Close details"
          className="rounded p-1 text-muted hover:bg-hovered hover:text-primary"
        >
          <X size={18} />
        </button>
      </div>

      {!detail ? (
        <SkeletonRows rows={6} />
      ) : (
        <div className="space-y-5 p-5">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {(
              [
                ["Current budget", detail.metrics.current_budget],
                ["Committed", detail.metrics.committed],
                ["Actual", detail.metrics.actual],
                ["EAC", detail.metrics.eac],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-md bg-elevated p-3">
                <p className="text-[10px] uppercase tracking-widest text-muted">{label}</p>
                <p className="mt-1 font-mono tabular-nums text-primary">{money(value)}</p>
              </div>
            ))}
          </div>

          <section>
            <h3 className="mb-2 text-xs uppercase tracking-widest text-muted">
              Change orders touching this line
            </h3>
            {detail.change_orders.length === 0 ? (
              <p className="text-xs text-muted">None.</p>
            ) : (
              <ul className="space-y-1.5">
                {detail.change_orders.map((co) => (
                  <li
                    key={`${co.id}`}
                    className="flex items-center justify-between rounded-md bg-elevated px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-accent">{co.number}</span>
                      <StatusBadge status={co.status} />
                    </span>
                    <span className="font-mono tabular-nums">{money(co.line_amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-xs uppercase tracking-widest text-muted">Purchase orders</h3>
            {detail.purchase_orders.length === 0 ? (
              <p className="text-xs text-muted">None.</p>
            ) : (
              <ul className="space-y-1.5">
                {detail.purchase_orders.map((po) => (
                  <li
                    key={po.id}
                    className="flex items-center justify-between rounded-md bg-elevated px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-accent">{po.number}</span>
                      <StatusBadge status={po.status} />
                    </span>
                    <span className="font-mono tabular-nums">{money(po.line_amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-xs uppercase tracking-widest text-muted">
              Actual cost entries
            </h3>
            {detail.cost_entries.length === 0 ? (
              <p className="text-xs text-muted">No costs posted yet.</p>
            ) : (
              <ul className="max-h-44 space-y-1.5 overflow-y-auto pr-1">
                {detail.cost_entries.map((entry) => (
                  <li
                    key={entry.id}
                    className="flex items-center justify-between rounded-md bg-elevated px-3 py-2 text-sm"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-secondary">
                        {entry.description ?? "Cost entry"}
                      </span>
                      <span className="font-mono text-[10px] text-muted">{entry.entry_date}</span>
                    </span>
                    <span className="font-mono tabular-nums">{moneyExact(entry.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex items-end gap-2">
              <Field label="Amount ($)">
                <Input
                  type="number"
                  value={cost.amount}
                  onChange={(e) => setCost({ ...cost, amount: e.target.value })}
                />
              </Field>
              <Field label="Description">
                <Input
                  value={cost.description}
                  placeholder="Invoice #"
                  onChange={(e) => setCost({ ...cost, description: e.target.value })}
                />
              </Field>
              <Button variant="primary" size="md" disabled={!cost.amount} onClick={postCost}>
                Post
              </Button>
            </div>
            <div className="mt-2">
              <ErrorNote error={error} />
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}

/* ---------------- Import wizard ---------------- */

function ImportWizard({ projectId, onClose, onDone }: { projectId: number; onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [onDuplicate, setOnDuplicate] = useState("skip");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ created: number; updated: number; skipped: number } | null>(null);

  const run = async (mode: "preview" | "commit") => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api<ImportPreview & { created: number; updated: number; skipped: number }>(
        `/projects/${projectId}/budget-lines/import`,
        { method: "POST", formData: form, params: { mode, on_duplicate: onDuplicate } },
      );
      if (mode === "preview") setPreview(response);
      else {
        setResult(response);
        onDone();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Import budget from Excel / CSV" onClose={onClose} wide>
      {result ? (
        <div className="space-y-4 text-center">
          <p className="font-display text-xl text-success">Import complete</p>
          <p className="text-sm text-secondary">
            {result.created} created · {result.updated} updated · {result.skipped} skipped
          </p>
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Budget file (.xlsx or .csv)" hint="Needs a cost-code column and an amount column — headers are matched flexibly.">
              <input
                type="file"
                accept=".xlsx,.csv"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setPreview(null);
                }}
                className="block text-sm text-secondary file:mr-3 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-1.5 file:text-sm file:text-white hover:file:bg-blue-600"
              />
            </Field>
            <Field label="If a code already exists">
              <Select value={onDuplicate} onChange={(e) => setOnDuplicate(e.target.value)}>
                <option value="skip">Skip it</option>
                <option value="update">Update its amount</option>
                <option value="error">Fail the import</option>
              </Select>
            </Field>
            <Button variant="secondary" disabled={!file || busy} onClick={() => void run("preview")}>
              {busy && !preview ? "Analyzing…" : "Preview"}
            </Button>
          </div>

          <ErrorNote error={error} />

          {preview ? (
            <>
              <div className="flex gap-4 text-xs text-secondary">
                <span>
                  <b className="text-primary">{preview.rows_parsed}</b> rows
                </span>
                <span>
                  <b className="text-success">{preview.rows_new}</b> new
                </span>
                <span>
                  <b className="text-amber">{preview.rows_duplicate}</b> already exist
                </span>
                <span>
                  <b className={preview.rows_invalid ? "text-danger" : "text-primary"}>
                    {preview.rows_invalid}
                  </b>{" "}
                  invalid
                </span>
                <span className="ml-auto font-mono tabular-nums text-primary">
                  {money(preview.total_amount_new)} new budget
                </span>
              </div>
              <div className="max-h-72 overflow-y-auto rounded-md border border-border-subtle">
                <table className="w-full">
                  <thead className="sticky top-0 bg-elevated">
                    <tr>
                      <th className={th}>Code</th>
                      <th className={th}>Description</th>
                      <th className={th}>Div</th>
                      <th className={thRight}>Amount</th>
                      <th className={th}>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {preview.rows.map((row) => (
                      <tr key={row.code}>
                        <td className={`${td} font-mono text-accent`}>{row.code}</td>
                        <td className={`${td} max-w-[16rem] truncate`}>{row.description}</td>
                        <td className={`${td} font-mono text-muted`}>{row.division}</td>
                        <td className={tdMono}>{money(row.amount)}</td>
                        <td className={td}>
                          {row.exists_in_project ? (
                            <span className="text-xs text-amber">duplicate</span>
                          ) : (
                            <span className="text-xs text-success">
                              new{row.merged_rows > 1 ? ` (merged ×${row.merged_rows})` : ""}
                              {!row.in_library ? " · custom code" : ""}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.invalid.length ? (
                <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
                  {preview.invalid.map((row) => (
                    <p key={row.row}>
                      Row {row.row} ({row.code}): {row.error}
                    </p>
                  ))}
                </div>
              ) : null}
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  disabled={busy || preview.rows_invalid > 0 || preview.rows_parsed === 0}
                  onClick={() => void run("commit")}
                >
                  {busy ? "Importing…" : `Import ${preview.rows_new} lines`}
                </Button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </Modal>
  );
}

/* ---------------- Add-line modal with CSI autocomplete ---------------- */

function AddLineModal({ projectId, onClose, onDone }: { projectId: number; onClose: () => void; onDone: () => void }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<CostCode[]>([]);
  const [form, setForm] = useState({ cost_code: "", description: "", category: "SUBCONTRACT", amount: "" });
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }
    timer.current = setTimeout(async () => {
      setSuggestions(await api<CostCode[]>("/cost-codes", { params: { q: query, limit: 8 } }));
    }, 200);
  }, [query]);

  const submit = async () => {
    setError(null);
    try {
      await api(`/projects/${projectId}/budget-lines`, {
        method: "POST",
        body: {
          cost_code: form.cost_code || query,
          description: form.description || undefined,
          category: form.category,
          original_budget: Number(form.amount) || 0,
        },
      });
      onDone();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add line");
    }
  };

  return (
    <Modal title="Add budget line" onClose={onClose}>
      <div className="space-y-4">
        <Field label="CSI cost code" required hint="Search the 3,401-code MasterFormat library, or type a custom code.">
          <Input
            value={form.cost_code || query}
            placeholder="03 30 00 or 'concrete'"
            onChange={(e) => {
              setQuery(e.target.value);
              setForm({ ...form, cost_code: "" });
            }}
          />
          {suggestions.length > 0 && !form.cost_code ? (
            <ul className="mt-1 max-h-44 overflow-y-auto rounded-md border border-border-default bg-elevated">
              {suggestions.map((code) => (
                <li key={code.code}>
                  <button
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-hovered"
                    onClick={() =>
                      setForm({ ...form, cost_code: code.code, description: code.title })
                    }
                  >
                    <span className="font-mono text-xs text-accent">{code.code}</span>
                    <span className="truncate text-secondary">{code.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </Field>
        <Field label="Description" hint="Leave blank to auto-fill from the CSI library.">
          <Input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Category">
            <Select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {["SUBCONTRACT", "LABOR", "MATERIAL", "EQUIPMENT", "GENERAL_CONDITIONS"].map((c) => (
                <option key={c} value={c}>
                  {c.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Original budget ($)" required>
            <Input
              type="number"
              min={0}
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />
          </Field>
        </div>
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!(form.cost_code || query) || !form.amount} onClick={submit}>
            Add line
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* ---------------- Page ---------------- */

export default function BudgetPage() {
  const { project } = useApp();
  const [wbs, setWbs] = useState<WbsTree | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [drawerLine, setDrawerLine] = useState<number | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!project) return;
    setLoading(true);
    const tree = await api<WbsTree>(`/projects/${project.id}/wbs`);
    setWbs(tree);
    setOpen((current) =>
      Object.keys(current).length
        ? current
        : Object.fromEntries(tree.divisions.map((d) => [d.division, true])),
    );
    setLoading(false);
  }, [project]);

  useEffect(() => {
    void load();
  }, [load]);

  const empty = useMemo(() => wbs !== null && wbs.divisions.length === 0, [wbs]);

  if (!project) return <SkeletonRows rows={8} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-primary">Budget & WBS</h1>
          <p className="mt-0.5 text-sm text-secondary">
            CSI MasterFormat hierarchy — Division → Section → Line. Click a line for its documents;
            click an ETC to enter your own cost-to-complete.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowImport(true)}>
            <FileUp size={15} /> Import Excel/CSV
          </Button>
          <Button variant="primary" onClick={() => setShowAdd(true)}>
            <Plus size={15} /> Add line
          </Button>
        </div>
      </div>

      {loading || !wbs ? (
        <SkeletonRows rows={10} />
      ) : empty ? (
        <EmptyState
          title="No budget lines yet"
          body="Import your budget spreadsheet to build the whole WBS in one shot, or add lines individually from the CSI library."
          action={
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => setShowImport(true)}>
                <FileUp size={15} /> Import budget
              </Button>
              <Button variant="secondary" onClick={() => setShowAdd(true)}>
                Add a line
              </Button>
            </div>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border-default bg-surface">
          <table className="w-full min-w-[64rem]">
            <thead className="sticky top-0 z-10 bg-elevated">
              <tr>
                <th className={`${th} w-[26rem]`}>WBS / Cost Code</th>
                {COLUMNS.map((column) => (
                  <th key={column} className={thRight}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {wbs.divisions.map((division: WbsDivision) => (
                <DivisionRows
                  key={division.division}
                  division={division}
                  open={open}
                  toggle={(key) => setOpen({ ...open, [key]: !open[key] })}
                  onSelectLine={setDrawerLine}
                  onChanged={load}
                />
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border-strong bg-elevated font-medium">
                <td className={`${td} uppercase tracking-wider text-muted`}>Project total</td>
                <RollupCells rollup={wbs.totals as unknown as Record<string, number>} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {drawerLine !== null ? (
        <Drawer lineId={drawerLine} onClose={() => setDrawerLine(null)} onChanged={load} />
      ) : null}
      {showImport ? (
        <ImportWizard projectId={project.id} onClose={() => setShowImport(false)} onDone={load} />
      ) : null}
      {showAdd ? (
        <AddLineModal projectId={project.id} onClose={() => setShowAdd(false)} onDone={load} />
      ) : null}
    </div>
  );
}

function DivisionRows({
  division,
  open,
  toggle,
  onSelectLine,
  onChanged,
}: {
  division: WbsDivision;
  open: Record<string, boolean>;
  toggle: (key: string) => void;
  onSelectLine: (id: number) => void;
  onChanged: () => void;
}) {
  const expanded = open[division.division] ?? false;
  return (
    <>
      <tr
        className="cursor-pointer bg-base/40 transition-colors hover:bg-hovered"
        onClick={() => toggle(division.division)}
      >
        <td className={`${td} font-medium`}>
          <span className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown size={15} className="text-muted" />
            ) : (
              <ChevronRight size={15} className="text-muted" />
            )}
            <span className="font-mono text-amber">{division.division}</span>
            <span className="text-primary">{division.title}</span>
          </span>
        </td>
        <RollupCells rollup={division.rollup as unknown as Record<string, number>} />
      </tr>
      {expanded
        ? division.sections.map((section) => (
            <SectionRows
              key={section.code}
              divisionKey={division.division}
              section={section}
              open={open}
              toggle={toggle}
              onSelectLine={onSelectLine}
              onChanged={onChanged}
            />
          ))
        : null}
    </>
  );
}

function SectionRows({
  divisionKey,
  section,
  open,
  toggle,
  onSelectLine,
  onChanged,
}: {
  divisionKey: string;
  section: { code: string; title: string; rollup: Record<string, number>; lines: LineMetrics[] };
  open: Record<string, boolean>;
  toggle: (key: string) => void;
  onSelectLine: (id: number) => void;
  onChanged: () => void;
}) {
  const key = `${divisionKey}:${section.code}`;
  const expanded = open[key] ?? true;
  const single = section.lines.length === 1 && section.lines[0].cost_code === section.code;
  if (single) {
    const line = section.lines[0];
    return (
      <LineRow line={line} indent={1} onSelect={onSelectLine} onChanged={onChanged} />
    );
  }
  return (
    <>
      <tr className="cursor-pointer transition-colors hover:bg-hovered" onClick={() => toggle(key)}>
        <td className={td}>
          <span className="flex items-center gap-2 pl-6">
            {expanded ? (
              <ChevronDown size={13} className="text-muted" />
            ) : (
              <ChevronRight size={13} className="text-muted" />
            )}
            <span className="font-mono text-xs text-info">{section.code}</span>
            <span className="text-secondary">{section.title}</span>
          </span>
        </td>
        <RollupCells rollup={section.rollup} />
      </tr>
      {expanded
        ? section.lines.map((line) => (
            <LineRow key={line.id} line={line} indent={2} onSelect={onSelectLine} onChanged={onChanged} />
          ))
        : null}
    </>
  );
}

function LineRow({
  line,
  indent,
  onSelect,
  onChanged,
}: {
  line: LineMetrics;
  indent: number;
  onSelect: (id: number) => void;
  onChanged: () => void;
}) {
  return (
    <tr className="group transition-colors hover:bg-hovered">
      <td className={td}>
        <button
          className="flex items-center gap-2 text-left"
          style={{ paddingLeft: `${indent * 1.5}rem` }}
          onClick={() => onSelect(line.id)}
          title="Open documents behind this line"
        >
          <span className="font-mono text-xs text-accent group-hover:underline">
            {line.cost_code}
          </span>
          <span className="max-w-[15rem] truncate text-secondary">{line.description}</span>
        </button>
      </td>
      <td className={tdMono}>{money(line.original_budget)}</td>
      <td className={tdMono}>{money(line.approved_changes)}</td>
      <td className={tdMono}>{money(line.current_budget)}</td>
      <td className={tdMono}>{money(line.committed)}</td>
      <td className={tdMono}>{money(line.actual)}</td>
      <EtcCell line={line} onSaved={onChanged} />
      <td className={tdMono}>{money(line.eac)}</td>
      <td className={`${tdMono} text-${vacTone(line.vac)}`}>{money(line.vac)}</td>
    </tr>
  );
}
