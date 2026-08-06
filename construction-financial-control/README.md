# Construction Financial Control System (CFCS)

A budget-forecasting and change-order control platform for general contractors:
PCO → OCO/SCO change-order pipeline, PO commitments with budget control,
role + threshold approval workflows, EAC/ETC forecasting, and a tamper-evident
audit ledger.

**Stack:** FastAPI · SQLAlchemy 2.0 · PostgreSQL · Alembic · JWT/RBAC ·
Streamlit · (optional) Celery + Redis.

The design was distilled from an evidence-based review of ten open-source
ERP/PM systems — see [Design provenance](#design-provenance) below.

---

## Quick start (Docker)

```bash
cd construction-financial-control
docker compose up --build
```

- API + docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501
- Postgres: `localhost:5432` (cfcs / cfcs / cfcs)

The `api` container seeds demo data automatically. Sign in on the Streamlit
sidebar as any of (password `ChangeMe123!`):

| Email | Role |
|---|---|
| admin@example.com | ADMIN |
| pm@example.com | PROJECT_MANAGER |
| exec@example.com | EXECUTIVE |
| finance@example.com | FINANCE |

Optional nightly forecast-snapshot worker: `docker compose --profile worker up`.

## Quick start (no Docker)

```bash
cd construction-financial-control
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # defaults expect Postgres on localhost:5432

# Option A — Postgres (production-like):
#   createdb cfcs; then edit DATABASE_URL in .env
# Option B — zero-setup SQLite:
#   export DATABASE_URL=sqlite:///./cfcs.db

python scripts/seed.py                # creates tables + demo data
uvicorn app.main:app --reload         # terminal 1 → http://localhost:8000/docs
streamlit run streamlit_app.py        # terminal 2 → http://localhost:8501
```

Verify the whole control loop end-to-end (uses a throwaway SQLite DB):

```bash
python scripts/smoke_test.py
```

## Migrations

Dev mode auto-creates tables (`AUTO_CREATE_TABLES=true`). For production:

```bash
export AUTO_CREATE_TABLES=false
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## Domain workflow

```
                 ┌────────────── PCO (Potential Change Order) ──────────────┐
   DRAFT ──send_to_pricing──► PRICING (RFQ to subs) ──submit──► SUBMITTED ──convert──► CONVERTED
                                                                    │
                              ┌─────────────────────────────────────┴─────────────┐
                              ▼                                                   ▼
               OCO (owner: cost + markup)                          SCO (sub: buyout cost)
       DRAFT ─submit_for_approval─► PENDING_APPROVAL       DRAFT ─submit_for_approval─► PENDING_APPROVAL
                    │ approval chain (role+threshold)                     │
                    ▼                                                     ▼
             APPROVED → raises contract value                      APPROVED → commitment
             + current budget (per line)                           (until superseded by a PO
                    │ REJECTED → revise → DRAFT                     sourced from the SCO)
                                                                          │
                                                              PO from SCO or manual lines
                                                    DRAFT ─submit─► budget check (STOP/WARN/IGNORE)
                                                          ─► PENDING_APPROVAL ─► APPROVED (commitment)
```

**Financial model per budget line** (all derived, never denormalized):

- `current_budget = original_budget + approved OCO lines`
- `committed = approved/closed PO lines + approved SCO lines not superseded by a PO`
- `actual = dated cost entries`
- `EAC` (REMAINING_BUDGET) `= max(committed, actual) + max(current_budget − committed, 0)`
- `EAC` (CPI) `= actual + (current_budget − EV) / CPI` with `EV = %complete × current_budget`
- `ETC = EAC − actual`, `VAC = current_budget − EAC`

**Approval matrix** (`approval_rules`): a document of amount X requires one
approval from every rule of its entity type with `threshold_amount ≤ X`, in
sequence order. Rejection at any step rejects the document (revisable).
Defaults seeded: CO → PM ($0+) → Executive ($50k+) → Finance ($100k+);
PO → PM ($0+) → Executive ($100k+).

**Audit ledger** (`audit_events`): every creation, transition, approval
decision, budget warning, cost posting, and snapshot is appended with a
SHA-256 hash chained to the previous event. `GET /api/v1/audit/verify`
recomputes the chain and reports the first broken link, if any.

## Project layout

```
app/
  main.py               FastAPI app + router mounting + dev table bootstrap
  core/config.py        pydantic-settings configuration
  core/security.py      pbkdf2 password hashing + JWT
  db/session.py         engine/session factory; db/base.py model registry
  models/               users, vendors, projects, budget (+costs, snapshots),
                        change orders, purchase orders, approvals, audit events
  schemas/              pydantic request/response models
  api/                  auth, projects, vendors, budgets, change_orders,
                        purchase_orders, approvals, audit, dashboard
  services/
    workflow_service.py   state machines, PCO conversion, PO budget control
    approval_service.py   threshold chains, sequenced decisions, finalization
    forecast_service.py   commitments, actuals, EAC/ETC/VAC, KPIs, snapshots
    audit_service.py      hash-chained append-only ledger
    numbering_service.py  PCO-0001 / PO-0001 numbering
  tasks.py              optional Celery beat: nightly forecast snapshots
scripts/seed.py         demo data; scripts/smoke_test.py  end-to-end test
streamlit_app.py        7-tab UI (dashboard, COs, POs, approvals, budget, vendors, audit)
```

---

## Design provenance

Ten repositories were analyzed against a weighted rubric (Domain Fit 20%,
Financial Controls 20%, CO Workflow 20%, Extensibility 15%, Python/Streamlit
implementation speed 15%, Operational Maturity 10%). Scores are 0–10.

| Rank | Repository | Weighted | Pattern(s) adopted here |
|---|---|---|---|
| 1 | https://github.com/frappe/erpnext | 7.60 | Budget-vs-committed-vs-actual model; STOP/WARN/IGNORE budget control on POs; naming series |
| 2 | https://github.com/odoo/odoo | 7.55 | Purchase double-validation (amount-gated second approval); chatter-style event trail concept |
| 3 | https://github.com/OCA/purchase-workflow | 6.80 | Tier validation → the role+threshold approval matrix |
| 4 | https://github.com/frappe/frappe | 6.75 | Explicit workflow tables: (state, action) → state with role gating |
| 5 | https://github.com/tryton/tryton | 6.20 | Guarded transition functions as the *only* status mutators |
| 6 | https://github.com/OCA/account-financial-tools | 6.00 | Derived (not denormalized) financial rollups |
| 7 | https://github.com/OCA/project | 5.80 | Project-scoped document organization |
| 8 | https://github.com/apache/fineract | 5.60 | Maker-checker + command journal → hash-chained audit ledger |
| 9 | https://github.com/opf/openproject | 5.50 | Budgets: planned vs actual container rollups feeding KPIs |
| 10 | https://github.com/Dolibarr/dolibarr | 5.30 | Amount-threshold second approval precedent for supplier orders |

No source code was copied from any of these projects — CFCS is a clean-room
MIT-compatible implementation of the *patterns* (see licensing notes in the
PR/analysis document). All ten systems carry copyleft licenses (GPLv3, LGPLv3,
AGPLv3, Apache-2.0*), so pattern-level reuse, not code reuse, was a hard
constraint. (*Fineract is Apache-2.0 and would permit code reuse, but is Java.)

## API surface (v1)

`POST /auth/login` · `GET /auth/me` · `POST /auth/users` ·
`POST|GET /projects` · `POST|GET /vendors` ·
`POST|GET /projects/{id}/budget-lines` · `POST /budget-lines/{id}/costs` ·
`GET /projects/{id}/forecast[?method=CPI&percent_complete=]` ·
`POST|GET /projects/{id}/forecast/snapshot(s)` ·
`POST|GET /projects/{id}/change-orders` · `GET /change-orders/{id}` ·
`POST /change-orders/{id}/transition` · `POST /change-orders/{id}/convert` ·
`GET /change-orders/{id}/approvals` ·
`POST|GET /projects/{id}/purchase-orders` · `POST /purchase-orders/{id}/submit` ·
`POST /purchase-orders/{id}/transition` · `GET /purchase-orders/{id}/approvals` ·
`GET /approvals/pending` · `POST /approvals/{id}/decide` · `POST|GET /approvals/rules` ·
`GET /audit` · `GET /audit/verify` · `GET /projects/{id}/kpis` · `GET /health`
