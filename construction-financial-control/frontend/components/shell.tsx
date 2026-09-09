"use client";

import {
  Building2,
  CheckSquare,
  FileSpreadsheet,
  GitPullRequestArrow,
  LayoutDashboard,
  LogOut,
  Package,
  Plus,
  ScrollText,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { api, setToken, type Project } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Button, ErrorNote, Field, Input, Modal, Select } from "@/components/ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/budget", label: "Budget & WBS", icon: FileSpreadsheet },
  { href: "/change-orders", label: "Change Orders", icon: GitPullRequestArrow },
  { href: "/purchase-orders", label: "Purchase Orders", icon: Package },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/vendors", label: "Vendors", icon: Users },
  { href: "/audit", label: "Audit Ledger", icon: ScrollText },
];

export function ProjectModal({
  existing,
  onClose,
  onSaved,
}: {
  existing?: Project | null;
  onClose: () => void;
  onSaved: (project: Project) => void;
}) {
  const [form, setForm] = useState({
    code: existing?.code ?? "",
    name: existing?.name ?? "",
    owner_name: existing?.owner_name ?? "",
    original_contract_value: existing?.original_contract_value ?? 0,
    budget_control: existing?.budget_control ?? "WARN",
    start_date: existing?.start_date ?? "",
    end_date: existing?.end_date ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        owner_name: form.owner_name || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        original_contract_value: Number(form.original_contract_value) || 0,
      };
      const saved = existing
        ? await api<Project>(`/projects/${existing.id}`, {
            method: "PATCH",
            body: {
              name: payload.name,
              owner_name: payload.owner_name ?? undefined,
              original_contract_value: payload.original_contract_value,
              budget_control: payload.budget_control,
              start_date: payload.start_date ?? undefined,
              end_date: payload.end_date ?? undefined,
            },
          })
        : await api<Project>("/projects", { method: "POST", body: payload });
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={existing ? `Edit ${existing.code}` : "New Project"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Project code" required>
          <Input
            value={form.code}
            disabled={!!existing}
            placeholder="PRJ-002"
            onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
        </Field>
        <Field label="Contract value ($)" required>
          <Input
            type="number"
            min={0}
            value={form.original_contract_value}
            onChange={(e) => setForm({ ...form, original_contract_value: Number(e.target.value) })}
          />
        </Field>
        <div className="col-span-2">
          <Field label="Project name" required>
            <Input
              value={form.name}
              placeholder="Riverside Medical Office Building"
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
        </div>
        <Field label="Owner">
          <Input
            value={form.owner_name}
            onChange={(e) => setForm({ ...form, owner_name: e.target.value })}
          />
        </Field>
        <Field label="Budget control" hint="What happens when a PO exceeds budget">
          <Select
            value={form.budget_control}
            onChange={(e) =>
              setForm({ ...form, budget_control: e.target.value as Project["budget_control"] })
            }
          >
            <option value="WARN">WARN — allow with warning</option>
            <option value="STOP">STOP — block the PO</option>
            <option value="IGNORE">IGNORE — no check</option>
          </Select>
        </Field>
        <Field label="Start date">
          <Input
            type="date"
            value={form.start_date ?? ""}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
          />
        </Field>
        <Field label="End date">
          <Input
            type="date"
            value={form.end_date ?? ""}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
          />
        </Field>
      </div>
      <div className="mt-5 space-y-3">
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={saving || !form.code || !form.name}
            onClick={submit}
          >
            {saving ? "Saving…" : existing ? "Save changes" : "Create project"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, projects, project, selectProject, refreshProjects } = useApp();
  const [showNewProject, setShowNewProject] = useState(false);

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border-subtle bg-surface">
        <div className="flex items-center gap-2.5 border-b border-border-subtle px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent font-display text-sm font-bold text-white">
            CF
          </div>
          <div>
            <p className="font-display text-sm font-bold leading-tight text-primary">CFCS</p>
            <p className="text-[10px] uppercase tracking-widest text-muted">Financial Control</p>
          </div>
        </div>

        <div className="border-b border-border-subtle p-3">
          <p className="mb-1.5 px-1 text-[10px] uppercase tracking-widest text-muted">Project</p>
          <div className="flex items-center gap-1.5">
            <Select
              aria-label="Select project"
              className="h-8 text-xs"
              value={project?.id ?? ""}
              onChange={(e) => selectProject(Number(e.target.value))}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </Select>
            <button
              onClick={() => setShowNewProject(true)}
              aria-label="Create new project"
              title="New project"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border-default text-secondary transition-colors hover:border-accent hover:text-accent"
            >
              <Plus size={15} />
            </button>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors duration-150 ${
                  active
                    ? "border-l-2 border-accent bg-accent/10 pl-[10px] text-primary"
                    : "text-secondary hover:bg-hovered hover:text-primary"
                }`}
              >
                <Icon size={17} strokeWidth={active ? 2.2 : 1.8} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border-subtle p-3">
          <div className="flex items-center justify-between rounded-md bg-elevated px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-sm text-primary">{user?.full_name}</p>
              <p className="text-[10px] uppercase tracking-widest text-muted">
                {user?.role.replace(/_/g, " ")}
              </p>
            </div>
            <button
              aria-label="Sign out"
              title="Sign out"
              onClick={() => {
                setToken(null);
                window.location.href = "/login";
              }}
              className="rounded p-1.5 text-muted transition-colors hover:bg-hovered hover:text-danger"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="ml-60 flex-1">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border-subtle bg-base/90 px-6 backdrop-blur">
          <div className="flex items-center gap-2 text-sm">
            <Building2 size={15} className="text-muted" />
            <span className="text-secondary">{project?.code ?? "—"}</span>
            <span className="text-muted">/</span>
            <span className="font-medium text-primary">{project?.name ?? "No project"}</span>
          </div>
          <p className="font-mono text-xs tabular-nums text-muted">
            Synced {new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
          </p>
        </header>
        <main className="px-6 py-5">{children}</main>
      </div>

      {showNewProject ? (
        <ProjectModal
          onClose={() => setShowNewProject(false)}
          onSaved={async (saved) => {
            await refreshProjects();
            selectProject(saved.id);
          }}
        />
      ) : null}
    </div>
  );
}
