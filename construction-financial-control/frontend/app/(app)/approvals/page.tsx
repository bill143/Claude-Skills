"use client";

import { Check, CheckSquare, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type ApprovalRequest } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useApp } from "@/lib/store";
import { Button, EmptyState, ErrorNote, Input, PageHeader, SkeletonRows } from "@/components/ui";

export default function ApprovalsPage() {
  const { user } = useApp();
  const [pending, setPending] = useState<ApprovalRequest[] | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setPending(await api<ApprovalRequest[]>("/approvals/pending"));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (request: ApprovalRequest, approve: boolean) => {
    setError(null);
    try {
      await api(`/approvals/${request.id}/decide`, {
        method: "POST",
        idempotent: true,
        body: { approve, comment: comments[request.id] || null },
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    }
  };

  if (pending === null) return <SkeletonRows rows={6} />;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader
        kicker="Governance"
        title="Approvals"
        description={`Steps waiting on your role (${user?.role.replace(/_/g, " ") ?? "…"}). Chains decide in sequence; a rejection closes the chain and sends the document back for revision.`}
      />

      <ErrorNote error={error} />

      {pending.length === 0 ? (
        <EmptyState
          icon={<CheckSquare size={20} />}
          title="Queue clear"
          body="Nothing is waiting on your approval. New submissions will appear here."
        />
      ) : (
        <div className="space-y-3">
          {pending.map((request, index) => (
            <div
              key={request.id}
              className="panel rise relative overflow-hidden p-4 pl-5"
              style={{ "--stagger": index } as React.CSSProperties}
            >
              <span className="absolute inset-y-0 left-0 w-1 bg-amber/70" aria-hidden />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium text-primary">
                    <span className="rounded border border-border-default bg-elevated px-1.5 py-px font-mono text-[10px] tracking-wider text-secondary">
                      {request.entity_type.replace(/_/g, " ")} #{request.entity_id}
                    </span>
                    Step {request.sequence} of chain
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    Requires{" "}
                    <span className="font-medium text-secondary">
                      {request.required_role.replace(/_/g, " ")}
                    </span>{" "}
                    · requested {dateTime(request.created_at)}
                  </p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/25 bg-amber/10 px-2 py-0.5 text-[11px] font-medium text-amber">
                  <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-current" />
                  awaiting decision
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Input
                  className="min-w-[12rem] flex-1"
                  placeholder="Comment (recorded in the audit ledger)"
                  value={comments[request.id] ?? ""}
                  onChange={(e) => setComments({ ...comments, [request.id]: e.target.value })}
                />
                <Button variant="success" onClick={() => void decide(request, true)}>
                  <Check size={15} /> Approve
                </Button>
                <Button variant="danger" onClick={() => void decide(request, false)}>
                  <X size={15} /> Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
