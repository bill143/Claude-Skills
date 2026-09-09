# Deployment Runbook

## Preconditions
- CI green on the release commit (lint, unit, integration vs PostgreSQL, smoke).
- Secrets provisioned per `docs/runbooks/secrets.md` (`SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`).
- Database backup taken within the last 24h (`docs/runbooks/backup-restore.md`).

## Standard deploy (container platform)
1. Build & tag from the release commit:
   ```bash
   docker build -t cfcs-api:<version> construction-financial-control/
   ```
2. Run migrations as a one-off job **before** rolling app containers:
   ```bash
   docker run --rm -e ENVIRONMENT=prod -e DATABASE_URL=$DATABASE_URL \
     cfcs-api:<version> alembic upgrade head
   ```
   Migrations are additive-first; a revision that drops/renames columns must ship
   one release AFTER the code stops using them (expand/contract pattern).
3. Roll the API with the new image. Readiness gate: `GET /health/ready` must
   return 200 (checks DB, plus Redis when `READINESS_CHECK_REDIS=true`).
   Liveness probe: `GET /health/live`.
4. Roll the Streamlit UI (same image, `streamlit run streamlit_app.py ...`).
5. Post-deploy verification (2 minutes):
   ```bash
   curl -fsS $API/health/ready
   curl -fsS $API/api/v1/audit/verify -H "Authorization: Bearer $TOKEN"   # expect valid:true
   ```
6. Watch structured logs for 5 minutes: filter `level:ERROR`; every entry has a
   `request_id` — quote it in any incident.

## Environment profiles
| Setting | dev | stage | prod |
|---|---|---|---|
| ENVIRONMENT | dev | stage | prod |
| AUTO_CREATE_TABLES | optional | forced off | forced off |
| /docs (OpenAPI UI) | on | on | disabled |
| CORS | localhost | explicit list | explicit list (enforced non-`*`) |
| SECRET_KEY | default ok | random | random ≥32 chars (enforced) |
| DB | SQLite ok | PostgreSQL | PostgreSQL (enforced) |

## Scaling note
The rate limiter is per-process. Before scaling beyond one API replica, front
it with a shared limiter (Redis-backed, or the ingress/API gateway) and keep
the in-process limiter as a backstop.
