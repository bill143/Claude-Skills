# Rollback Runbook

## Application rollback (no schema involvement) — the default
1. Re-deploy the previous image tag; readiness gate as in deployment.
2. Verify `GET /health/ready` and `GET /api/v1/audit/verify`.
3. No data action needed: all financial state is derived from documents, not
   denormalized aggregates, so a code rollback cannot corrupt totals.

## Schema rollback
Migrations 0001/0002 are reversible (`alembic downgrade -1`), BUT:
- **Never downgrade a migration that has dropped or rewritten data.**
- Preferred path is roll-forward: ship a fixing migration instead of downgrading.
- If a downgrade is unavoidable:
  ```bash
  # 1. Stop API writes (scale to 0 or block at ingress).
  # 2. Snapshot first:
  pg_dump "$DATABASE_URL" -Fc -f pre-rollback-$(date +%Y%m%d%H%M).dump
  # 3. Downgrade one step and redeploy the matching code version:
  alembic downgrade -1
  ```

## Rollback decision matrix
| Symptom | Action |
|---|---|
| Elevated 5xx after deploy | App rollback to previous tag |
| Migration failed mid-apply | Alembic is transactional on Postgres: failed revision auto-rolls back; fix forward |
| `/audit/verify` returns valid:false | Do NOT roll back — this is an integrity incident: follow incident-response.md |
| Wrong forecast numbers | App rollback + open P0; numbers are derived, so fixing code fixes numbers |
