# Secrets Management Checklist

## Inventory
| Secret | Used by | Rotation |
|---|---|---|
| SECRET_KEY (JWT signing) | API | 90 days, or immediately on suspicion |
| DATABASE_URL (contains DB password) | API, worker, migrations job | 90 days |
| REDIS_URL (if auth enabled) | worker | 90 days |
| Postgres superuser password | ops only, never the app | 90 days |

## Rules
- [ ] Secrets live only in the platform secret store (K8s Secrets + KMS,
      AWS Secrets Manager, etc.) — never in git, images, or compose files.
- [ ] `.env` files are git-ignored; `.env.example` carries placeholders only.
- [ ] The app DB user has DML only (SELECT/INSERT/UPDATE/DELETE) — DDL rights
      belong to the migrations job. The audit trigger (migration 0002) then
      also protects audit rows from the app credential entirely.
- [ ] `ENVIRONMENT=prod` boot-validates SECRET_KEY (≥32 chars, non-default) —
      do not weaken this check.
- [ ] Rotating SECRET_KEY invalidates all active JWTs (default lifetime 8h):
      rotate during a maintenance window or accept forced re-login.
- [ ] CI uses repository/environment secrets with least scope; no secret is
      echoed in workflow logs.
- [ ] Access to prod secrets is role-gated and audited by the platform.
