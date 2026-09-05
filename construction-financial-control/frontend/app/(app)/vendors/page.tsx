"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Vendor } from "@/lib/api";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Modal,
  Select,
  SkeletonRows,
  td,
  th,
} from "@/components/ui";

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", vendor_type: "SUBCONTRACTOR", trade: "", contact_email: "" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setVendors(await api<Vendor[]>("/vendors"));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const submit = async () => {
    setError(null);
    try {
      await api("/vendors", {
        method: "POST",
        body: { ...form, trade: form.trade || null, contact_email: form.contact_email || null },
      });
      setShowCreate(false);
      setForm({ name: "", vendor_type: "SUBCONTRACTOR", trade: "", contact_email: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  if (vendors === null) return <SkeletonRows rows={6} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-primary">Vendors & Subcontractors</h1>
          <p className="mt-0.5 text-sm text-secondary">
            SCOs and POs are written against this list.
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          <Plus size={15} /> Add vendor
        </Button>
      </div>

      {vendors.length === 0 ? (
        <EmptyState
          title="No vendors yet"
          body="Add your subcontractors and suppliers to write SCOs and POs against them."
          action={
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> Add vendor
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border-default bg-surface">
          <table className="w-full">
            <thead className="bg-elevated">
              <tr>
                <th className={th}>Name</th>
                <th className={th}>Type</th>
                <th className={th}>Trade</th>
                <th className={th}>Contact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {vendors.map((vendor) => (
                <tr key={vendor.id} className="transition-colors hover:bg-hovered">
                  <td className={`${td} font-medium text-primary`}>{vendor.name}</td>
                  <td className={td}>
                    <span
                      className={`font-mono text-xs ${
                        vendor.vendor_type === "SUBCONTRACTOR" ? "text-info" : "text-gold"
                      }`}
                    >
                      {vendor.vendor_type}
                    </span>
                  </td>
                  <td className={`${td} text-secondary`}>{vendor.trade ?? "—"}</td>
                  <td className={`${td} text-secondary`}>{vendor.contact_email ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate ? (
        <Modal title="Add vendor" onClose={() => setShowCreate(false)}>
          <div className="space-y-4">
            <Field label="Name" required>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Type">
                <Select
                  value={form.vendor_type}
                  onChange={(e) => setForm({ ...form, vendor_type: e.target.value })}
                >
                  <option value="SUBCONTRACTOR">Subcontractor</option>
                  <option value="SUPPLIER">Supplier</option>
                </Select>
              </Field>
              <Field label="Trade">
                <Input value={form.trade} onChange={(e) => setForm({ ...form, trade: e.target.value })} />
              </Field>
            </div>
            <Field label="Contact email">
              <Input
                type="email"
                value={form.contact_email}
                onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              />
            </Field>
            <ErrorNote error={error} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button variant="primary" disabled={!form.name} onClick={submit}>
                Add vendor
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
