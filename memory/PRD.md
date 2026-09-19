# ARMENTA OS — Product Requirements Document

## Business Context
ARMENTA'S MOTORS is a Mexican mobile automotive service company (Ciudad Juárez). Field technicians drive an equipped mobile unit to clients (individuals, companies, fleets, auction lots) to perform diagnostics, tuneups, mechanical repairs, engine & transmission service, pre-purchase inspections, and recurring preventive maintenance.

ARMENTA OS is the operating system of the business. It must eventually control the full flow:
CLIENT → VEHICLE → DIAGNOSTIC → QUOTE → APPROVAL → PARTS → WORK ORDER → SERVICE → EVIDENCE → PAYMENT → PROFIT → FOLLOW-UP → NEXT SERVICE.

## User Personas
- **Admin / Owner** (Adrian Armenta): full control, finances, billing, customer master.
- **Manager**: schedules, quotations, receivables.
- **Field Technician**: works on-site with phone in hand, needs one-handed mobile UX.
- **Assistant**: data entry, follow-ups.
- **Viewer**: read-only access (partners, accountants).

## Core Non-Functional Requirements
- Mobile-first, single-handed operation with gloved hands.
- Bilingual ES/EN.
- Dark obsidian + metallic gold aesthetic. Premium automotive, sober, industrial.
- Zero fake functionality. Unimplemented features must show "Próximamente".
- Architecture ready for API + DB + real auth + roles from day one.

## Phase 1 — Núcleo Funcional (COMPLETED — 2026-02)
Implemented end-to-end:
- **Backend** (`/app/backend/server.py`)
  - FastAPI + Motor (MongoDB).
  - `POST /api/auth/login` (identifier = username or email + password) → JWT (7d TTL).
  - `GET  /api/auth/me` (Bearer).
  - `POST /api/auth/logout`.
  - `GET  /api/dashboard/summary` (returns real zeroes — no fake data).
  - `GET  /api/health`.
  - bcrypt password hashing, unique indexes on users.username / users.email, idempotent admin seed on startup pulled from `.env` (`ADMIN_USERNAME=admin`, `ADMIN_EMAIL=adrianarmentona31@gmail.com`, `ADMIN_PASSWORD=armenta123`).
  - Roles enum: admin, manager, technician, assistant, viewer (ready for RBAC).
- **Frontend** (`/app/frontend/src/`)
  - React 19 + react-router-dom v7.
  - `context/AuthContext` (initializing / authenticated / anonymous states, rehydrates from localStorage then verifies with `/auth/me`).
  - `context/I18nContext` (ES default, EN toggle, persisted).
  - `lib/storage` — thin abstraction ready to swap for cookie-based store.
  - `lib/api` — axios instance with bearer interceptor and FastAPI detail normalizer.
  - Pages: `Login`, `Dashboard` (Control), `ModulePlaceholder` (all future modules).
  - `AppShell` with sticky header (session badge, ES/EN toggle, user badge, logout) + desktop `Sidebar` + mobile `BottomNav`.
  - Full data-testid coverage per design guidelines.
- **Design**: obsidian #070707 / #101010 / #161616, gold #C9A45C accent, Barlow Condensed headings, Inter body, JetBrains Mono for tactical labels, pulse-dot session indicator, gold-glow CTAs, mobile bottom nav ≥48px tap targets.
- **Session persistence**: localStorage key `armenta_os_session_v1` — survives full browser restart. Session verified against backend on load.

## Data Model (scaffolded conceptually, tables to be created per phase)
- User (implemented)
- Client (particular / empresa / lote)
- Vehicle (year, make, model, engine, VIN, plates, mileage, drive, nextServiceDate/Km)
- Service (states: lead / diagnostic / quoted / approved / scheduled / in_progress / completed / delivered / cancelled)
- Quote (states: draft / sent / approved / rejected / expired)
- Payment (cash / transfer / card / other)
- Company (with paymentTerms + creditLimit)
- Technician (with commissionType/value)
- Part (with cost, salePrice, stock, minimumStock)

## Phase 2+ Backlog (prioritized)
- **P0 · Fase 2** Clients module (CRUD, particular/empresa/lote types, contact info).
- **P0 · Fase 3** Vehicles module (bound to client, VIN, mileage log — foundation for "kilometraje inteligente").
- **P0 · Fase 4** Services (work orders, technician assignment, status machine, evidence uploads).
- **P1 · Fase 5** Quotations (line items, tax breakdown, PDF export).
- **P1 · Fase 6** Payments & receivables.
- **P1 · Fase 7** Finance & profit reports (part cost vs. sale price margin).
- **P2 · Fase 8** Technicians & commissions.
- **P2 · Fase 9** Companies / fleets consolidation by RFC (multi-vehicle rollup).
- **P2 · Fase 10** WhatsApp reminders, AI predictive maintenance, campaigns.

## Testing
Admin auto-seeded, verified end-to-end via curl: login OK, login bad-credentials 401, login by email, /auth/me with Bearer, /dashboard/summary, unauthenticated /me returns 401.

## Credentials
See `/app/memory/test_credentials.md`.
