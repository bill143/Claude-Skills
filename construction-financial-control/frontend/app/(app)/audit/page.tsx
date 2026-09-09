"use client";

import { ShieldCheck, ShieldX } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { Button, SkeletonRows, td, th } from "@/components/ui";

type AuditEvent = {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  actor_id: number | null;
  payload: Record<string, unknown>;
  hash: string;
  created_at: string;
};

type Verify = { valid: boolean; events: number; first_broken_event_id: number | null };

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);

  const load = useCallback(async () => {
    setEvents(await api<AuditEvent[]>("/audit", { params: { limit: 200 } }));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runVerify = async () => {
    setVerify(await api<Verify>("/audit/verify"));
  };

  if (events === null) return <SkeletonRows rows={10} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-primary">Audit Ledger</h1>
          <p className="mt-0.5 text-sm text-secondary">
            Append-only, SHA-256 hash-chained. Every transition, decision, warning, and dollar is
            journaled — tampering breaks the chain.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {verify ? (
            verify.valid ? (
              <span className="flex items-center gap-1.5 text-sm text-success">
                <ShieldCheck size={16} /> Chain intact · {verify.events} events
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-sm text-danger">
                <ShieldX size={16} /> BROKEN at event {verify.first_broken_event_id}
              </span>
            )
          ) : null}
          <Button variant="secondary" onClick={runVerify}>
            Verify chain
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border-default bg-surface">
        <table className="w-full">
          <thead className="bg-elevated">
            <tr>
              <th className={th}>When</th>
              <th className={th}>Entity</th>
              <th className={th}>Action</th>
              <th className={th}>Detail</th>
              <th className={th}>Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {events.map((event) => (
              <tr key={event.id} className="transition-colors hover:bg-hovered">
                <td className={`${td} text-muted`}>{dateTime(event.created_at)}</td>
                <td className={`${td} font-mono text-xs text-secondary`}>
                  {event.entity_type}#{event.entity_id}
                </td>
                <td className={`${td} text-primary`}>{event.action}</td>
                <td className={`${td} max-w-[22rem] truncate font-mono text-xs text-muted`}>
                  {JSON.stringify(event.payload)}
                </td>
                <td className={`${td} font-mono text-[10px] text-muted`}>
                  {event.hash.slice(0, 12)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
