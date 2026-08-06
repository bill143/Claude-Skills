# Incident Response Quickstart

## Severity ladder
- **P0**: audit chain invalid, money math wrong, data loss, auth bypass.
- **P1**: API down/degraded, approvals blocked, migrations stuck.
- **P2**: single-endpoint errors, UI degradation, worker backlog.

## First 15 minutes
1. Grab correlation IDs: every 5xx response and log line carries
   `request_id` / `correlation_id`. Filter logs by it:
   `jq 'select(.request_id=="<id>")'` over the JSON log stream.
2. Check probes: `GET /health/live` (process) vs `GET /health/ready`
   (dependencies) — distinguishes app crash from DB/Redis outage.
3. Check integrity: `GET /api/v1/audit/verify`.
   - `valid:false` ⇒ **P0**: snapshot the DB immediately (`pg_dump`), preserve
     logs, do not restart/rollback (destroys evidence), engage security lead.
     `first_broken_event_id` pinpoints the first tampered/altered event.
4. Recent deploy? Follow rollback.md decision matrix.

## Common playbooks
| Symptom | Playbook |
|---|---|
| 429 storms | Legitimate load vs abuse: check per-client pattern in access logs; raise `RATE_LIMIT_*` only for verified load |
| 409 "already decided/modified concurrently" | Working as designed (race guard). Investigate only if a single user reports it repeatedly |
| 422 "budget control is STOP" | Not an incident — governance. PM must revise budget (OCO) or PO |
| Approvals stuck | `GET /api/v1/approvals/pending` as admin; verify the required role has an active user |
| DB connection exhaustion | Check pool metrics; readiness flips to 503 → platform stops routing; scale pool/replicas |

## Communication
- P0/P1: open an incident channel, post the correlation ID, timeline, and the
  audit-verify verdict first. Financial-integrity incidents also notify the
  finance owner immediately.
- Postmortem within 5 business days for P0/P1; action items become P1 issues.
