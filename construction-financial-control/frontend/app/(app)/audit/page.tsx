"use client";

import { ChevronDown, ChevronRight, Link2, ShieldCheck, ShieldX } from "lucide-react";
import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { Button, PageHeader, SkeletonRows, td, th } from "@/components/ui";

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

const ACTION_TONES: [RegExp, string][] = [
  [/reject|void|tamper|denied/i, "text-danger"],
  [/approve/i, "text-success"],
  [/warn/i, "text-amber"],
  [/create|convert/i, "text-accent"],
];

function actionTone(action: string): string {
  return ACTION_TONES.find(([pattern]) => pattern.test(action))?.[1] ?? "text-primary";
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(async () => {
    setEvents(await api<AuditEvent[]>("/audit", { params: { limit: 200 } }));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runVerify = async () => {
    setVerifying(true);
    try {
      setVerify(await api<Verify>("/audit/verify"));
    } finally {
      setVerifying(false);
    }
  };

  if (events === null) return <SkeletonRows rows={10} />;

  return (
    <div className="space-y-4">
      <PageHeader
        kicker="Governance"
        title="Audit Ledger"
        description="Append-only, SHA-256 hash-chained. Every transition, decision, warning, and dollar is journaled — tampering breaks the chain."
        actions={
          <Button variant="secondary" onClick={runVerify} disabled={verifying}>
            <ShieldCheck size={15} /> {verifying ? "Verifying…" : "Verify chain"}
          </Button>
        }
      />

      {verify ? (
        verify.valid ? (
          <div className="flex items-center gap-2.5 rounded-md border border-success/25 bg-success/10 px-4 py-3">
            <ShieldCheck size={18} className="shrink-0 text-success" />
            <div>
              <p className="text-sm font-medium text-success">Chain intact</p>
              <p className="text-xs text-secondary">
                All {verify.events} events re-hashed and verified against their recorded chain.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 rounded-md border border-danger/30 bg-danger/10 px-4 py-3">
            <ShieldX size={18} className="shrink-0 text-danger" />
            <div>
              <p className="text-sm font-medium text-danger">
                Chain BROKEN at event {verify.first_broken_event_id}
              </p>
              <p className="text-xs text-secondary">
                The ledger has been altered outside the application. Treat downstream records as
                unverified.
              </p>
            </div>
          </div>
        )
      ) : null}

      <div className="panel overflow-x-auto">
        <table className="w-full">
          <thead className="bg-elevated">
            <tr>
              <th className={`${th} w-8`} aria-label="Expand" />
              <th className={th}>When</th>
              <th className={th}>Entity</th>
              <th className={th}>Action</th>
              <th className={th}>Detail</th>
              <th className={th}>Chain</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {events.map((event) => {
              const isOpen = expanded === event.id;
              return (
                <Fragment key={event.id}>
                  <tr
                    className="cursor-pointer transition-colors hover:bg-hovered"
                    onClick={() => setExpanded(isOpen ? null : event.id)}
                  >
                    <td className={`${td} text-muted`}>
                      {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </td>
                    <td className={`${td} font-mono text-xs text-muted`}>
                      {dateTime(event.created_at)}
                    </td>
                    <td className={td}>
                      <span className="rounded border border-border-default bg-elevated px-1.5 py-px font-mono text-[10px] tracking-wider text-secondary">
                        {event.entity_type}#{event.entity_id}
                      </span>
                    </td>
                    <td className={`${td} text-[13px] font-medium ${actionTone(event.action)}`}>
                      {event.action}
                    </td>
                    <td className={`${td} max-w-[20rem] truncate font-mono text-xs text-muted`}>
                      {JSON.stringify(event.payload)}
                    </td>
                    <td className={td}>
                      <span
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-muted"
                        title={event.hash}
                      >
                        <Link2 size={10} className="text-border-strong" />
                        {event.hash.slice(0, 10)}
                      </span>
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr className="bg-inset/60">
                      <td />
                      <td colSpan={5} className="px-3 py-3">
                        <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-border-subtle bg-inset p-3 font-mono text-[11px] leading-relaxed text-secondary">
                          {JSON.stringify(event.payload, null, 2)}
                        </pre>
                        <p className="mt-2 font-mono text-[10px] text-muted">
                          hash {event.hash}
                          {event.actor_id !== null ? ` · actor #${event.actor_id}` : " · system"}
                        </p>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
