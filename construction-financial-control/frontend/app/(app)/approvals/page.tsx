"use client";

import { Check, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type ApprovalRequest } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useApp } from "@/lib/store";
import { Button, EmptyState, ErrorNote, Input, SkeletonRows } from "@/components/ui";

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
      <div>
        <h1 className="font-display text-2xl font-bold text-primary">Approvals</h1>
        <p className="mt-0.5 text-sm text-secondary">
          Steps waiting on your role ({user?.role.replace(/_/g, " ")}). Chains decide in sequence;
          a rejection closes the chain and sends the document back for revision.
        </p>
      </div>

      <ErrorNote error={error} />

      {pending.length === 0 ? (
        <EmptyState
          title="Queue clear"
          body="Nothing is waiting on your approval. New submissions will appear here."
        />
      ) : (
        <div className="space-y-3">
          {pending.map((request) => (
            <div
              key={request.id}
              className="rounded-lg border border-border-default bg-surface p-4"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-primary">
                    {request.entity_type.replace(/_/g, " ")} #{request.entity_id}
                  </p>
                  <p className="text-xs text-muted">
                    Step {request.sequence} · requires {request.required_role.replace(/_/g, " ")} ·
                    requested {dateTime(request.created_at)}
                  </p>
                </div>
                <span className="rounded-full border border-amber/20 bg-amber/10 px-2 py-0.5 text-xs text-amber">
                  awaiting decision
                </span>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <Input
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
