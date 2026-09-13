# O'Neill Contractors — Platform Charter

**This document is the map of every software project owned by this GitHub
account. Read it before writing any code, in any repository. It exists
because three overlapping construction platforms were built in parallel by
sessions that never checked what already existed.**

## The system of record

There is exactly one company platform:

> **`bill143/nexus-est-app`** — the O'Neill Contractors operations platform.
> Next.js 14 + TypeScript (strict) + Supabase (Postgres, RLS) + Prisma.
> Five modules: Opportunity Pipeline / Go-No-Go, Estimating, Financial
> Management, Project Management, Admin.

**Every new feature, module, fix, or redesign for company operations goes
into `nexus-est-app`. No exceptions without Bill's explicit, written
instruction naming a different repository.**

## The other repositories

| Repository | Status | Rule |
|---|---|---|
| `bill143/nexus-est-app` | **SYSTEM OF RECORD** | All application work happens here |
| `bill143/Claude-Skills` (this repo) | Skills + archived CFCS source | Skills and agent config only — never application features |
| `bill143/NEXUS-Project-Management-Draft` | Archived research fork (AGPL) | Read-only reference. Never build on it — AGPL copyleft |

## History (why this file exists)

- **CFCS** (`construction-financial-control/` in Claude-Skills) — a complete
  FastAPI + Next.js financial-control app built Aug–Sep 2026. It duplicated
  the Financial Management module `nexus-est-app` already had. Its genuinely
  better pieces — the CSI MasterFormat WBS engine (3,401 codes), Excel/CSV
  budget import, per-line manual ETC, and the dark command-center UI design
  system — are being ported into `nexus-est-app`. The folder stays as the
  port source and historical record. Do not extend it.
- **NEXUS-Project-Management-Draft** — a federal-pivot fork of the
  open-source OpenConstructionERP, dormant since May 2026. Its ideas
  (CO₂/Buy Clean reporting, ML bid-price prediction) may be harvested as
  specs for `nexus-est-app`; its AGPL code may not be copied into
  proprietary repositories.

## Rules for every Claude / AI session

1. Read this file and `bill143/nexus-est-app`'s `CLAUDE.md` before building.
2. If asked to build something that plausibly already exists, **search
   `nexus-est-app` first** and say what you found before writing new code.
3. Never start a new repository or a parallel implementation of an existing
   module. If the request seems to require one, stop and ask Bill,
   referencing this charter.
4. Bill is not a software developer and relies on the model for
   architectural judgment. Exercising it — asking "where should this live?"
   — is part of every task.
