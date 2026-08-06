# Production Readiness Gap Report — CFCS Hardening Pass

Audit target: the CFCS baseline (pre-hardening commit `7d88aac`). Each gap
lists its resolution in this pass, or its explicit residual status.

## P0 — must fix before production (all RESOLVED in this pass)

| # | Gap | Where it was | Resolution |
|---|---|---|---|
| P0-1 | Runtime `create_all` was the schema path; no committed migrations | `app/main.py` lifespan; empty `alembic/versions/` | Committed `alembic/versions/0001_initial_schema.py` + `0002_audit_immutability.py`; `create_all` gated to `ENVIRONMENT=dev` and forced off elsewhere (`app/core/config.py`); compose + CI run `alembic upgrade head`; `tests/test_platform.py::test_alembic_migrations_run_clean` |
| P0-2 | Check-then-write races: two concurrent approvals/submits could both apply financial effects | `app/services/approval_service.py::decide`, `workflow_service.py` transitions/convert/submit | Row locks (`SELECT FOR UPDATE` via `app/db/session.py::locked_get`, Postgres) + portable compare-and-swap guarded UPDATEs (`_cas_status`, decide CAS) — loser gets 409; proven by `tests/test_concurrency.py` (3 race tests) |
| P0-3 | No duplicate-submission protection: a retried decide/submit re-applied effects | all mutating endpoints | `Idempotency-Key` support on decide / PO submit / CO transition / CO convert (`app/models/idempotency.py`, `app/services/idempotency_service.py`) — insert-before-execute + unique constraint beats concurrent duplicates; `tests/test_idempotency.py` (5 tests) |
| P0-4 | Wildcard CORS (`allow_origins=["*"]` with credentials) | `app/main.py` | Explicit `CORS_ORIGINS` allowlist; prod boot-refuses `*`/empty (`config.py`); headers restricted to Authorization/Content-Type/Idempotency-Key/X-Request-ID |
| P0-5 | Insecure default `SECRET_KEY` usable in prod | `app/core/config.py` | Prod profile refuses default/short keys, DEBUG, SQLite; `tests/test_platform.py::test_prod_config_refuses_insecure_defaults` |
| P0-6 | Audit rows mutable via ORM or SQL despite hash chain | `app/models/audit.py` | ORM listeners raise `AuditImmutabilityError`; Postgres trigger (migration 0002) blocks raw UPDATE/DELETE; SQLite relies on chain detection — all three covered by `tests/test_audit_immutability.py` |
| P0-7 | Document numbering race → duplicate PCO/PO numbers (unique-constraint 500s) | `app/services/numbering_service.py` | Project row taken as row-level mutex before counting; constraint remains backstop |

## P1 — should fix before scale (RESOLVED except where noted)

| # | Gap | Resolution / residual |
|---|---|---|
| P1-1 | No health probes; deploys had no readiness gate | `/health/live` + `/health/ready` (DB always, Redis opt-in) in `app/main.py`; compose healthcheck; tested |
| P1-2 | No request correlation; plain-text logs; uncaught errors leaked stack traces | JSON structured logs + `X-Request-ID` propagation (`app/core/logging.py`); global handler returns `correlation_id` and logs the trace server-side |
| P1-3 | No rate limiting on login (credential stuffing) or mutating endpoints | Sliding-window limiter (`app/core/rate_limit.py`): 10/min auth, 120/min mutating, 300/min read. **Residual:** per-process only — front with shared limiter before horizontal scaling |
| P1-4 | Float money in API schemas | All money inputs are `Decimal` with `max_digits=16, decimal_places=2` (rejects sub-cent input); services compute pure Decimal with cent quantization; forecast identities (`EAC = actual + ETC`, `VAC = budget − EAC`) asserted at runtime (`forecast_service._check_invariants`). Outputs serialize cent-quantized values (IEEE-754-exact) |
| P1-5 | No CI | `.github/workflows/cfcs-ci.yml`: ruff, mypy, pytest (SQLite), pytest + Alembic against PostgreSQL 16 service, smoke test |
| P1-6 | OpenAPI/docs exposed in prod | `/docs`, `/openapi.json` disabled when `ENVIRONMENT=prod` |
| P1-7 | No ops docs | `docs/runbooks/`: deployment, rollback, secrets, backup-restore, incident-response |

## P2 — track (OPEN, accepted for initial production)

| # | Gap | Notes |
|---|---|---|
| P2-1 | JWTs are stateless with 8h lifetime; no revocation list | Rotate SECRET_KEY to force logout; add token JTI denylist (Redis) when SSO lands |
| P2-2 | Login lockout is IP-based (rate limiter), not account-based | Add per-account failed-attempt lockout + alerting |
| P2-3 | Idempotency records grow unbounded | Add retention sweep (e.g. delete > 30 days) to the Celery beat schedule |
| P2-4 | Single global approval matrix | Per-project rules are a straightforward `approval_rules.project_id` extension |
| P2-5 | Streamlit UI does not yet send Idempotency-Key headers | API accepts them today; UI wiring is additive |
| P2-6 | No metrics endpoint (Prometheus) / tracing | Structured logs carry request_id + duration_ms; add OTel exporter next |
| P2-7 | Actuals entered manually; no GL integration | Same as baseline scope; ERP sync is the next module |

## Branch protection recommendations (apply in repo settings)
- Protect `main`: require PRs (no direct pushes), ≥1 approving review, dismiss
  stale approvals on new commits.
- Required status checks: `lint`, `unit-tests`, `integration-tests`,
  `smoke-test` (exact CI job names), strict = branch up to date before merge.
- Require linear history; forbid force-pushes and deletions; include admins.
- Optional: CODEOWNERS routing `app/services/**` and `alembic/**` to the
  finance-platform owners.
