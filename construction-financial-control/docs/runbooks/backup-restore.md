# Backup & Restore Procedure

## What must be backed up
PostgreSQL is the only stateful store (Redis holds ephemeral queue state only).
The `audit_events` hash chain makes backups tamper-evident: after any restore,
`GET /api/v1/audit/verify` proves ledger integrity.

## Backups
- **Continuous**: enable WAL archiving / PITR on the Postgres instance
  (RPO ≤ 5 min for a financial system of record).
- **Daily logical dump** (belt and suspenders, 30-day retention, offsite):
  ```bash
  pg_dump "$DATABASE_URL" -Fc -f cfcs-$(date +%Y%m%d).dump
  ```
- **Pre-deploy snapshot** before every schema migration (see deployment.md).

## Restore drill (run quarterly — an untested backup is not a backup)
```bash
createdb cfcs_restore
pg_restore -d cfcs_restore --no-owner cfcs-<date>.dump
DATABASE_URL=postgresql+psycopg2://...cfcs_restore alembic current   # must be at head
# Point a throwaway API instance at cfcs_restore, then:
curl -fsS $API/api/v1/audit/verify -H "Authorization: Bearer $TOKEN"  # valid:true
```

## Full restore (data loss event)
1. Freeze writes (scale API to 0).
2. Restore latest base + WAL to target time (PITR), or latest dump.
3. `alembic current` must equal the code's expected head; migrate if restoring
   an older dump onto newer code.
4. Verify audit chain, spot-check one project's KPIs against a known report.
5. Unfreeze; announce the recovery point (any approvals/POs after it must be
   re-entered — the audit ledger of the lost window, if recoverable from logs,
   is the re-entry checklist).
