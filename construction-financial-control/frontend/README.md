# CFCS Frontend (Next.js)

Dark command-center UI for the Construction Financial Control System.

```bash
cd frontend
npm install
API_PROXY_TARGET=http://localhost:8000 npm run dev   # http://localhost:3000
```

`API_PROXY_TARGET` points at the FastAPI backend (default `http://localhost:8000`;
use `http://localhost:8001` if the API runs there). The Next server proxies
`/api/v1/*` server-side, so the browser stays same-origin and the API's CORS
allowlist stays strict.

Production: `npm run build && npm run start` (or the `ui` service in
docker-compose).

Screens: Dashboard (KPIs + method explainer + division bars), Budget & WBS
(CSI tree with rollups, inline manual-ETC editing, per-line document
drill-down, Excel/CSV import wizard, CSI autocomplete), Change Orders
(PCO → convert → approval chains), Purchase Orders (SCO buyout + budget-check
submit), Approvals inbox, Vendors, Audit ledger with chain verification.
