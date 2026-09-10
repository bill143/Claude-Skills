"use client";

import {
  CheckSquare,
  FileSpreadsheet,
  GitPullRequestArrow,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Plus,
  ScrollText,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setToken, type ApprovalRequest, type Project } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Button, ErrorNote, Field, Input, Modal, Select } from "@/components/ui";

const NAV_SECTIONS: {
  label: string;
  items: { href: string; label: string; icon: typeof LayoutDashboard; badge?: "approvals" }[];
}[] = [
  {
    label: "Overview",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Cost Control",
    items: [
      { href: "/budget", label: "Budget & WBS", icon: FileSpreadsheet },
      { href: "/change-orders", label: "Change Orders", icon: GitPullRequestArrow },
      { href: "/purchase-orders", label: "Purchase Orders", icon: Package },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/approvals", label: "Approvals", icon: CheckSquare, badge: "approvals" },
      { href: "/audit", label: "Audit Ledger", icon: ScrollText },
    ],
  },
  {
    label: "Directory",
    items: [{ href: "/vendors", label: "Vendors", icon: Users }],
  },
];

const PAGE_TITLES: Record<string, string> = Object.fromEntries(
  NAV_SECTIONS.flatMap((section) => section.items.map((item) => [item.href, item.label])),
);

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

function BudgetControlChip({ mode }: { mode: string }) {
  const tone =
    mode === "STOP"
      ? "border-danger/30 bg-danger/10 text-danger"
      : mode === "WARN"
        ? "border-amber/30 bg-amber/10 text-amber"
        : "border-border-strong/40 bg-border-default/30 text-muted";
  return (
    <span
      title={`Budget control: ${mode}`}
      className={`hidden items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] tracking-wider sm:inline-flex ${tone}`}
    >
      {mode}
    </span>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, projects, project, selectProject, refreshProjects } = useApp();
  const [showNewProject, setShowNewProject] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState<number>(0);

  useEffect(() => {
    setDrawerOpen(false);
    void api<ApprovalRequest[]>("/approvals/pending")
      .then((list) => setPendingCount(list.length))
      .catch(() => setPendingCount(0));
  }, [pathname]);

  const initials = (user?.full_name ?? "?")
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const pageTitle =
    Object.entries(PAGE_TITLES).find(([href]) => pathname.startsWith(href))?.[1] ?? "CFCS";

  const sidebar = (
    <aside className="flex h-full w-60 flex-col border-r border-border-subtle bg-surface">
      <div className="flex items-center gap-2.5 border-b border-border-subtle px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-gradient-to-br from-accent to-info font-display text-sm font-bold text-white shadow-[0_0_16px_-2px_var(--glow-accent)]">
          CF
        </div>
        <div>
          <p className="font-display text-sm font-bold leading-tight text-primary">CFCS</p>
          <p className="text-[9px] uppercase tracking-[0.22em] text-muted">Financial Control</p>
        </div>
        <button
          onClick={() => setDrawerOpen(false)}
          aria-label="Close navigation"
          className="ml-auto rounded p-1 text-muted hover:text-primary lg:hidden"
        >
          <X size={16} />
        </button>
      </div>

      <div className="border-b border-border-subtle p-3">
        <p className="mb-1.5 px-1 text-[9px] uppercase tracking-[0.22em] text-muted">Project</p>
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

      <nav className="flex-1 space-y-4 overflow-y-auto p-3">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="mb-1 px-3 text-[9px] font-medium uppercase tracking-[0.22em] text-muted">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon, badge }) => {
                const active = pathname.startsWith(href);
                const count = badge === "approvals" ? pendingCount : 0;
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`group relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors duration-150 ${
                      active
                        ? "bg-accent/10 text-primary"
                        : "text-secondary hover:bg-hovered hover:text-primary"
                    }`}
                  >
                    {active ? (
                      <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-accent shadow-[0_0_8px_var(--accent-primary)]" />
                    ) : null}
                    <Icon
                      size={16}
                      strokeWidth={active ? 2.2 : 1.8}
                      className={active ? "text-accent" : "text-muted group-hover:text-secondary"}
                    />
                    {label}
                    {count > 0 ? (
                      <span className="ml-auto flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-amber/15 px-1 font-mono text-[10px] font-medium text-amber">
                        {count}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="space-y-2 border-t border-border-subtle p-3">
        <p className="flex items-center gap-1.5 px-1 text-[10px] text-muted">
          <ShieldCheck size={12} className="text-success" />
          SHA-256 hash-chained ledger
        </p>
        <div className="flex items-center justify-between rounded-md bg-elevated px-3 py-2">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-strong bg-inset font-mono text-[10px] text-secondary">
              {initials}
            </span>
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-primary">{user?.full_name}</p>
              <p className="text-[9px] uppercase tracking-[0.18em] text-muted">
                {user?.role.replace(/_/g, " ")}
              </p>
            </div>
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
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <div className="fixed inset-y-0 left-0 z-40 hidden lg:block">{sidebar}</div>

      {/* Mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 animate-slide-in-left">{sidebar}</div>
        </div>
      ) : null}

      <div className="min-w-0 flex-1 lg:ml-60">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border-subtle bg-base/85 px-4 backdrop-blur-md sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5 text-sm">
            <button
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
              className="rounded p-1.5 text-secondary hover:bg-hovered hover:text-primary lg:hidden"
            >
              <Menu size={17} />
            </button>
            <span className="rounded border border-border-default bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-accent">
              {project?.code ?? "—"}
            </span>
            <span className="hidden text-muted sm:inline">/</span>
            <span className="hidden truncate text-secondary sm:inline">
              {project?.name ?? "No project"}
            </span>
            <span className="text-muted">/</span>
            <span className="truncate font-medium text-primary">{pageTitle}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2.5">
            {project ? <BudgetControlChip mode={project.budget_control} /> : null}
            <p className="font-mono text-[11px] tabular-nums text-muted">
              <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-success align-middle" />
              Synced{" "}
              {new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
            </p>
          </div>
        </header>
        <main className="px-4 py-5 sm:px-6">{children}</main>
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
